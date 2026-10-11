import argparse
import getpass
import json
import sys

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.models.user import User, UserRole
from app.security import hash_password
from app.services.demo_data import load_demo_dataset, preview_demo_dataset


def create_admin(args: argparse.Namespace) -> int:
    email = args.email.strip().lower()
    display_name = (args.name or email).strip()
    password = args.password

    if not password:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Repeat password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 2

    if len(password) < 10:
        print(
            "Password must contain at least 10 characters.",
            file=sys.stderr,
        )
        return 2

    with SessionLocal() as db:
        existing = db.scalar(
            select(User).where(func.lower(User.email) == email)
        )
        if existing:
            print(
                f"User already exists: {existing.email} / {existing.role}"
            )
            return 1

        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"Created ADMIN: {user.email} / {user.id}")

    return 0


def list_users(_: argparse.Namespace) -> int:
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.email)).all()
        for user in users:
            print(
                f"{user.id}  {user.email:<35} "
                f"{user.role:<13} active={user.active}"
            )
    return 0


def load_demo(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.yes:
        print("Use --dry-run to preview, or --yes to load the synthetic demo dataset.", file=sys.stderr)
        return 2
    try:
        with SessionLocal() as db:
            if args.dry_run:
                result = preview_demo_dataset(db)
                result["dry_run"] = True
                result["would_change_current_event"] = args.make_current and result["status"] == "ready"
                db.rollback()
            else:
                result = load_demo_dataset(db, make_current=args.make_current)
                db.commit()
    except (ValueError, OSError) as exc:
        print(f"Demo import failed: {exc}", file=sys.stderr)
        return 1
    except HTTPException as exc:
        print(f"Demo import failed: {exc.detail}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Demo import failed: database error. Transaction rolled back; check connection and migrations.",
              file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="conman-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser(
        "create-admin",
        help="Create the first ADMIN user",
    )
    create.add_argument("--email", required=True)
    create.add_argument("--name")
    create.add_argument("--password")
    create.set_defaults(func=create_admin)

    users = sub.add_parser(
        "list-users",
        help="List users",
    )
    users.set_defaults(func=list_users)

    demo = sub.add_parser("load-demo", help="Load the bundled synthetic dataset once, without overwriting data")
    demo.add_argument("--dry-run", action="store_true", help="Validate the dataset and check collisions without writing")
    demo.add_argument("--yes", action="store_true", help="Confirm adding demo records to this database")
    demo.add_argument("--make-current", action="store_true", help="Select the primary demo event on the first import")
    demo.set_defaults(func=load_demo)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
