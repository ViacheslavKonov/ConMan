"""Demo imports run against private PostgreSQL schemas, never application data."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from io import StringIO
from threading import Barrier
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app import cli
from app.config import get_settings
from app.db import Base, get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.core import (
    AppSetting, Booking, BookingParticipant, Charge, CheckInLog, Event, LayoutTable,
    LayoutZone, Participant, Payment, SeatingAdjacencyPreference, SeatingPreference,
    SeatingTablePreference, SeatingZonePreference, TableAssignment, Tariff, Vendor,
)
from app.models.user import User
from app.schemas.demo_data import DemoDataset
from app.services.codes import SEQUENCES
from app.services.demo_data import (
    DemoDataConflict, dataset_records, load_demo_dataset,
    preview_demo_dataset, read_dataset, record_id,
)


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        self.schema = f"demo_test_{uuid4().hex}"
        self.admin_engine = create_engine(get_settings().database_url)
        with self.admin_engine.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_engine(
            get_settings().database_url,
            connect_args={"options": f"-csearch_path={self.schema}"},
        )
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as db:
            for sequence in SEQUENCES.values():
                db.execute(text(f'CREATE SEQUENCE "{sequence}"'))
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)
        self.dataset = read_dataset()

    def tearDown(self):
        self.engine.dispose()
        with self.admin_engine.begin() as db:
            db.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.admin_engine.dispose()

    def count(self, db, model):
        return db.scalar(select(func.count()).select_from(model))

    def run_cli(self, *arguments):
        stdout, stderr = StringIO(), StringIO()
        with patch.object(cli, "SessionLocal", self.sessions), \
                patch("sys.argv", ["conman-cli", "load-demo", *arguments]), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_preview_and_confirmation_do_not_write(self):
        self.assertEqual(self.run_cli()[0], 2)
        status, output, errors = self.run_cli("--dry-run", "--make-current")
        self.assertEqual((status, errors), (0, ""))
        preview = json.loads(output)
        self.assertEqual(preview["status"], "ready")
        self.assertTrue(preview["would_change_current_event"])
        with self.sessions() as db:
            for model in (Event, Vendor, Booking, Charge, AuditLog, AppSetting, User):
                self.assertEqual(self.count(db, model), 0)
            self.assertEqual(db.scalar(text("SELECT last_value FROM charge_code_seq")), 1)
            self.assertFalse(db.scalar(text("SELECT is_called FROM charge_code_seq")))

    def test_complete_import_has_consistent_finance_seating_and_checkin(self):
        status, output, errors = self.run_cli("--yes", "--make-current")
        self.assertEqual((status, errors), (0, ""))
        result = json.loads(output)
        self.assertEqual(result["status"], "loaded")
        expected = dataset_records(self.dataset)
        models = {
            "events": Event, "vendors": Vendor, "tariffs": Tariff, "participants": Participant,
            "bookings": Booking, "zones": LayoutZone, "tables": LayoutTable,
            "booking_participants": BookingParticipant, "charges": Charge, "payments": Payment,
            "assignments": TableAssignment, "preferences": SeatingPreference,
            "table_preferences": SeatingTablePreference, "zone_preferences": SeatingZonePreference,
            "adjacency_preferences": SeatingAdjacencyPreference, "checkin_logs": CheckInLog,
        }
        with self.sessions() as db:
            for name, model in models.items():
                self.assertEqual(self.count(db, model), expected[name], name)
            self.assertEqual(self.count(db, User), 0)
            self.assertEqual(db.get(AppSetting, "current_event_id").value,
                             str(record_id(Event, self.dataset.primary_event)))
            bookings = {row.code: row for row in db.scalars(select(Booking))}
            self.assertEqual(bookings["DEMO-BKG-01"].payment_status, "PAID")
            self.assertEqual(bookings["DEMO-BKG-01"].checkin_status, "COMPLETE")
            self.assertEqual(bookings["DEMO-BKG-02"].payment_status, "PARTIAL")
            self.assertEqual(bookings["DEMO-BKG-02"].checkin_status, "PARTIAL")
            self.assertEqual(bookings["DEMO-BKG-03"].payment_status, "UNPAID")
            self.assertEqual(bookings["DEMO-BKG-04"].payment_status, "OVERPAID")
            self.assertEqual(bookings["DEMO-BKG-04"].extra_participants_count, 1)
            self.assertEqual(bookings["DEMO-BKG-09"].paid_amount, 0)
            self.assertEqual(bookings["DEMO-BKG-12"].paid_amount, 0)
            self.assertEqual(bookings["DEMO-BKG-10"].final_total, 5700)
            self.assertEqual(bookings["DEMO-BKG-10"].seating_status, "PREFERENCES_SUBMITTED")
            self.assertEqual(bookings["DEMO-BKG-01"].seating_status, "ASSIGNED")
            entry = db.scalar(select(AuditLog))
            self.assertEqual(entry.entity_type, "DEMO_DATASET")
            self.assertEqual(entry.metadata_json["source"], "CLI")
            # Public preferences use fresh opaque tokens, never a password or a fixed token in the fixture.
            for pref in db.scalars(select(SeatingPreference)):
                self.assertGreaterEqual(len(pref.access_token), 48)

    def test_repeated_import_preserves_edits_and_current_event(self):
        with self.sessions.begin() as db:
            real = Event(code="EVT-REAL", event_name="Real event", start_date=date(2026, 10, 1),
                         end_date=date(2026, 10, 2))
            db.add(real)
            db.flush()
            original_id = str(real.id)
            db.add(AppSetting(key="current_event_id", value=original_id))
            load_demo_dataset(db)
            db.get(Vendor, record_id(Vendor, "DEMO-VND-01")).vendor_name = "Edited demo vendor"
        with self.sessions.begin() as db:
            before = self.count(db, Charge)
            result = load_demo_dataset(db, make_current=True)
            self.assertEqual(result["status"], "already_loaded")
            self.assertFalse(result["current_event_changed"])
            self.assertEqual(self.count(db, Charge), before)
            self.assertEqual(db.get(AppSetting, "current_event_id").value, original_id)
            self.assertEqual(db.get(Vendor, record_id(Vendor, "DEMO-VND-01")).vendor_name,
                             "Edited demo vendor")
            self.assertEqual(self.count(db, AuditLog), 1)
            self.assertEqual(preview_demo_dataset(db)["status"], "already_loaded")

    def test_conflict_rejects_import_without_overwriting_existing_data(self):
        with self.sessions.begin() as db:
            db.add(Vendor(code="DEMO-VND-01", vendor_name="Existing vendor", email="real@example.com"))
        for args in (("--dry-run",), ("--yes",)):
            status, _, error = self.run_cli(*args)
            self.assertEqual(status, 1)
            self.assertIn("conflicts", error)
        with self.sessions() as db:
            self.assertEqual(self.count(db, Vendor), 1)
            self.assertEqual(db.scalar(select(Vendor)).vendor_name, "Existing vendor")
            for model in (Event, Booking, Charge, AuditLog, AppSetting):
                self.assertEqual(self.count(db, model), 0)

    def test_failure_rolls_back_all_imported_records_and_marker(self):
        with patch("app.services.demo_data.recalculate_booking", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                with self.sessions.begin() as db:
                    load_demo_dataset(db, make_current=True)
        with self.sessions() as db:
            for model in (Event, Vendor, Participant, Booking, Payment, AuditLog, AppSetting):
                self.assertEqual(self.count(db, model), 0)
        self.assertEqual(self.run_cli("--yes")[0], 0)

    def test_concurrent_imports_add_exactly_one_dataset(self):
        barrier = Barrier(2)

        def load(_):
            with self.sessions.begin() as db:
                barrier.wait(timeout=10)
                return load_demo_dataset(db)["status"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(load, range(2)))
        self.assertEqual(sorted(results), ["already_loaded", "loaded"])
        with self.sessions() as db:
            self.assertEqual(self.count(db, Event), 2)
            self.assertEqual(self.count(db, Booking), 12)
            self.assertEqual(self.count(db, AuditLog), 1)

    def test_invalid_graph_is_rejected_before_loading(self):
        def unknown_ref(data):
            data["bookings"][0]["vendor"] = "DEMO-MISSING"

        def duplicate_code(data):
            data["vendors"][1]["code"] = data["vendors"][0]["code"]

        def overlap(data):
            data["bookings"][9]["assignment"] = {"table": "DEMO-TBL-01", "start_slot": 1}

        def cross_event(data):
            data["tables"][0]["zone"] = "DEMO-ZON-03"

        def unpaid_confirmed(data):
            data["bookings"][0]["payments"] = []

        for change in (unknown_ref, duplicate_code, overlap, cross_event, unpaid_confirmed):
            data = self.dataset.model_dump(mode="json")
            change(data)
            with self.subTest(change=change.__name__), self.assertRaises(ValidationError):
                DemoDataset.model_validate(data)

    def test_changed_bundle_cannot_overwrite_a_completed_import(self):
        self.assertEqual(self.run_cli("--yes")[0], 0)
        changed = self.dataset.model_copy(update={"description": "Changed dataset"})
        with patch("app.services.demo_data.read_dataset", return_value=changed):
            with self.sessions() as db, self.assertRaises(DemoDataConflict):
                load_demo_dataset(db)
        with self.sessions() as db:
            self.assertEqual(self.count(db, Event), 2)
            self.assertEqual(self.count(db, AuditLog), 1)

    def test_imported_data_can_be_read_by_existing_application_routes(self):
        with self.sessions.begin() as db:
            load_demo_dataset(db, make_current=True)

        def test_db():
            with self.sessions() as db:
                yield db

        previous = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = test_db
        try:
            with TestClient(app) as client:
                response = client.post("/api/auth/bootstrap", json={
                    "email": "qa-admin@example.com", "display_name": "QA Admin",
                    "password": "qa-private-schema-password",
                })
                self.assertEqual(response.status_code, 201)
                for path in ("/api/core/dashboard", "/api/events", "/api/admin/data", "/api/applications",
                             "/api/seating/layout", "/api/planning", "/api/checkin"):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, (path, response.text))
                for report in ("vendors", "participants", "seating", "finance", "checkin"):
                    response = client.get(f"/api/reports/{report}")
                    self.assertEqual(response.status_code, 200, (report, response.text))
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)


if __name__ == "__main__":
    unittest.main()
