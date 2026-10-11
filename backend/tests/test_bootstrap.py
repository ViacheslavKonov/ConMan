"""Run against a development PostgreSQL database; each test uses a private schema."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base, get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.core import AppSetting
from app.models.session import AuthSession
from app.models.user import User
from app.security import hash_password, verify_password


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.schema = f"bootstrap_test_{uuid4().hex}"
        self.admin_engine = create_engine(get_settings().database_url)
        with self.admin_engine.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_engine(
            get_settings().database_url,
            connect_args={"options": f"-csearch_path={self.schema}"},
        )
        Base.metadata.create_all(self.engine, tables=[
            User.__table__, AuthSession.__table__, AuditLog.__table__, AppSetting.__table__,
        ])
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

        def test_db():
            with self.sessions() as db:
                yield db

        self.previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app, raise_server_exceptions=False)
        self.payload = {
            "email": "FIRST@Example.com",
            "display_name": "  Administrator  ",
            "password": "first-admin-test-password",
        }

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)
        self.engine.dispose()
        with self.admin_engine.begin() as db:
            db.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.admin_engine.dispose()

    def test_first_admin_is_signed_in_and_setup_closes(self):
        status = self.client.get('/api/auth/bootstrap')
        self.assertEqual(status.json(), {"required": True})
        self.assertEqual(status.headers['cache-control'], 'no-store')
        response = self.client.post('/api/auth/bootstrap', json=self.payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['role'], 'ADMIN')
        self.assertEqual(response.json()['email'], 'first@example.com')
        self.assertEqual(response.json()['display_name'], 'Administrator')
        self.assertEqual(self.client.get('/api/auth/me').json(), response.json())
        self.assertIn('HttpOnly', response.headers.get_list('set-cookie')[0])
        with self.sessions() as db:
            user = db.scalar(select(User))
            self.assertTrue(user.active)
            self.assertNotEqual(user.password_hash, self.payload['password'])
            self.assertTrue(verify_password(self.payload['password'], user.password_hash))
            entry = db.scalar(select(AuditLog))
            self.assertEqual(entry.metadata_json, {"source": "INITIAL_SETUP"})
            self.assertNotIn('password', entry.after_data)
        self.assertEqual(self.client.get('/api/auth/bootstrap').json(), {"required": False})
        self.assertEqual(self.client.post('/api/auth/bootstrap', json=self.payload).status_code, 409)
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 403)
        csrf = self.client.cookies['conman_csrf']
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf}).status_code, 204)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={
            'email': self.payload['email'], 'password': self.payload['password'],
        }).status_code, 200)

    def test_existing_inactive_non_admin_also_blocks_setup(self):
        with self.sessions() as db:
            db.add(User(email='existing@example.com', display_name='Existing',
                        password_hash=hash_password('existing-test-password'),
                        role='VIEWER', active=False))
            db.commit()
        self.assertEqual(self.client.get('/api/auth/bootstrap').json(), {"required": False})
        self.assertEqual(self.client.post('/api/auth/bootstrap', json=self.payload).status_code, 409)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 1)

    def test_invalid_input_leaves_setup_available(self):
        for change in ({'password': 'short'}, {'display_name': '   '},
                       {'email': 'invalid'}, {'password': 'x' * 201},
                       {'display_name': 'x' * 201}):
            with self.subTest(change=tuple(change)):
                self.assertEqual(self.client.post('/api/auth/bootstrap',
                    json={**self.payload, **change}).status_code, 422)
        self.assertEqual(self.client.get('/api/auth/bootstrap').json(), {"required": True})

    def test_completion_survives_user_removal(self):
        self.assertEqual(self.client.post('/api/auth/bootstrap', json=self.payload).status_code, 201)
        with self.sessions() as db:
            db.execute(delete(User))
            db.commit()
        self.assertEqual(self.client.get('/api/auth/bootstrap').json(), {"required": False})
        self.assertEqual(self.client.post('/api/auth/bootstrap', json=self.payload).status_code, 409)

    def test_session_failure_rolls_back_account_and_completion(self):
        with patch('app.routers.auth.create_session', side_effect=RuntimeError('test failure')):
            self.assertEqual(self.client.post('/api/auth/bootstrap', json=self.payload).status_code, 500)
        self.assertEqual(self.client.get('/api/auth/bootstrap').json(), {"required": True})
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditLog)), 0)
        self.assertEqual(self.client.post('/api/auth/bootstrap', json=self.payload).status_code, 201)

    def test_concurrent_requests_create_only_one_admin(self):
        barrier = Barrier(2)

        def create(index):
            with TestClient(app) as client:
                barrier.wait(timeout=10)
                return client.post('/api/auth/bootstrap', json={
                    **self.payload, 'email': f'admin{index}@example.com',
                }).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create, range(2)))
        self.assertEqual(sorted(outcomes), [201, 409])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuthSession)), 1)


if __name__ == '__main__':
    unittest.main()
