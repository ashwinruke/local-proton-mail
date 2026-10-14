"""Command line entry point: python -m pmail <command>"""

import argparse
import getpass

from pmail import bridge, config


def cmd_setup(args: argparse.Namespace) -> int:
    print("Find these in Proton Mail Bridge: click your account, then 'Mailbox details' (IMAP).")
    username = input("Bridge IMAP username: ").strip()
    password = getpass.getpass("Bridge IMAP password (not your Proton password): ")
    config.save_credentials(username, password)
    print("Saved to this device's keychain. Next: python -m pmail check")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    with bridge.connect() as client:
        total = 0
        print(f"{'Folder':40} Messages")
        for _flags, _delim, name in client.list_folders():
            count = client.folder_status(name, ["MESSAGES"])[b"MESSAGES"]
            total += count
            print(f"{name:40} {count}")
        print(f"\nConnected. {total} messages across all folders (labels count each copy).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pmail", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="save Bridge credentials to this device's keychain").set_defaults(func=cmd_setup)
    sub.add_parser("check", help="connect to Bridge and list folders").set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    return args.func(args)
