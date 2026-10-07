import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.user import User, UserRole
from app.security import hash_password


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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
