#!/usr/bin/env python3
"""
web/manage_users.py — CLI User Management for SAGE Viewer.

Usage:
  python web/manage_users.py add <email> <role> [--password <pwd>]
  python web/manage_users.py list
  python web/manage_users.py remove <email>
  python web/manage_users.py passwd <email> [--password <pwd>]
  python web/manage_users.py seed
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web.auth import (
    load_users,
    add_user,
    remove_user,
    set_user_password,
    seed_default_user_if_needed,
    VALID_ROLES
)


def main():
    parser = argparse.ArgumentParser(description="Manage SAGE Viewer Users")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Add
    parser_add = subparsers.add_parser("add", help="Add a new user")
    parser_add.add_argument("email", help="User email address")
    parser_add.add_argument("role", choices=VALID_ROLES, help="User role (viewer, operator, admin)")
    parser_add.add_argument("--password", "-p", help="Optional password (generated if omitted)")

    # List
    subparsers.add_parser("list", help="List all users")

    # Remove
    parser_rm = subparsers.add_parser("remove", help="Remove a user")
    parser_rm.add_argument("email", help="User email to remove")

    # Passwd
    parser_pwd = subparsers.add_parser("passwd", help="Change user password")
    parser_pwd.add_argument("email", help="User email")
    parser_pwd.add_argument("--password", "-p", help="Optional new password")

    # Seed
    subparsers.add_parser("seed", help="Seed default admin user if not present")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "add":
        ok, msg, pwd = add_user(args.email, args.role, args.password)
        if ok:
            print(f"[SUCCESS] {msg}")
            if not args.password:
                print(f"[CREDENTIALS] Generated password for {args.email}: {pwd}")
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        users = load_users()
        if not users:
            print("No users found. Run 'python web/manage_users.py seed' to seed default admin.")
            return
        print(f"{'Email':<35} {'Role':<12} {'Created At'}")
        print("-" * 65)
        for email, info in sorted(users.items()):
            role = info.get("role", "viewer")
            created = info.get("created_at", "—")[:19]
            print(f"{email:<35} {role:<12} {created}")

    elif args.command == "remove":
        ok, msg = remove_user(args.email)
        if ok:
            print(f"[SUCCESS] {msg}")
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "passwd":
        ok, msg, pwd = set_user_password(args.email, args.password)
        if ok:
            print(f"[SUCCESS] {msg}")
            if not args.password:
                print(f"[CREDENTIALS] New password for {args.email}: {pwd}")
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "seed":
        email, pwd = seed_default_user_if_needed()
        if pwd:
            print(f"[SUCCESS] Seeded default admin: {email} (Password: {pwd})")
        else:
            print(f"[INFO] Default admin {email} already exists.")


if __name__ == "__main__":
    main()
