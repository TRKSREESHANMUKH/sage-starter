#!/usr/bin/env python3
"""
web/manage_users.py — CLI User Management for SAGE Viewer & Controller.

Usage:
  python -m web.manage_users add <username> <email> <role> [--password <pwd>]
  python -m web.manage_users passwd <username_or_email> [--password <pwd>]
  python -m web.manage_users list
  python -m web.manage_users remove <username_or_email>
  python -m web.manage_users seed
"""

import argparse
import getpass
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
    find_user,
    VALID_ROLES
)


def main():
    parser = argparse.ArgumentParser(description="Manage SAGE Users (Viewer & Controller)")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Add
    parser_add = subparsers.add_parser("add", help="Add a new user")
    parser_add.add_argument("username", help="User username (e.g. admin, operator)")
    parser_add.add_argument("email", help="User email address")
    parser_add.add_argument("role", choices=VALID_ROLES, help="User role (viewer, operator, admin)")
    parser_add.add_argument("--password", "-p", help="Optional password (prompted securely if omitted)")

    # Passwd
    parser_pwd = subparsers.add_parser("passwd", help="Change user password")
    parser_pwd.add_argument("identifier", help="Username or email of user")
    parser_pwd.add_argument("--password", "-p", help="Optional new password (prompted securely if omitted)")

    # List
    subparsers.add_parser("list", help="List all users")

    # Remove
    parser_rm = subparsers.add_parser("remove", help="Remove a user by username or email")
    parser_rm.add_argument("identifier", help="Username or email to remove")

    # Seed
    subparsers.add_parser("seed", help="Seed default admin user if not present")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "add":
        pwd = args.password
        if not pwd:
            if sys.stdin.isatty():
                pwd = getpass.getpass("Enter password for new user: ")
                pwd2 = getpass.getpass("Confirm password: ")
                if pwd != pwd2:
                    print("[ERROR] Passwords do not match.", file=sys.stderr)
                    sys.exit(1)
            else:
                # Fallback to stdin line or generated
                line = sys.stdin.readline().strip()
                pwd = line if line else None

        ok, msg, _ = add_user(args.username, args.email, args.role, pwd)
        if ok:
            print(f"[SUCCESS] {msg}")
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "passwd":
        pwd = args.password
        if not pwd:
            if sys.stdin.isatty():
                pwd = getpass.getpass(f"Enter new password for '{args.identifier}': ")
                pwd2 = getpass.getpass("Confirm new password: ")
                if pwd != pwd2:
                    print("[ERROR] Passwords do not match.", file=sys.stderr)
                    sys.exit(1)
            else:
                line = sys.stdin.readline().strip()
                pwd = line if line else None

        ok, msg, _ = set_user_password(args.identifier, pwd)
        if ok:
            print(f"[SUCCESS] {msg}")
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        users = load_users()
        if not users:
            print("No users found. Run 'python -m web.manage_users seed' to seed default admin.")
            return
        print(f"{'Username':<16} {'Email':<35} {'Role':<10} {'Created At'}")
        print("-" * 75)
        for _, info in sorted(users.items()):
            u_name = info.get("username", "—")
            em = info.get("email", "—")
            role = info.get("role", "viewer")
            created = info.get("created_at", "—")[:19]
            print(f"{u_name:<16} {em:<35} {role:<10} {created}")

    elif args.command == "remove":
        ok, msg = remove_user(args.identifier)
        if ok:
            print(f"[SUCCESS] {msg}")
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "seed":
        email, _ = seed_default_user_if_needed()
        print(f"[SUCCESS] Verified default admin: {email} (username: admin)")


if __name__ == "__main__":
    main()
