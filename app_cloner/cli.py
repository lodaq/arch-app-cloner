"""Command Line Interface for Arch App Cloner."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from app_cloner.apps import find_app, scan_installed_apps
from app_cloner.manager import CloneManager

# ANSI color codes
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RESET = "\033[0m"


def print_banner() -> None:
    print(f"{BOLD}{CYAN}╭────────────────────────────────────────────────╮{RESET}")
    print(f"{BOLD}{CYAN}│        Arch App Cloner - Multi-Instance        │{RESET}")
    print(f"{BOLD}{CYAN}╰────────────────────────────────────────────────╯{RESET}")


def cmd_list(args: argparse.Namespace, mgr: CloneManager) -> int:
    clones = mgr.list_clones()
    if not clones:
        print(f"{YELLOW}No application clones found.{RESET}")
        print(f"To create one, run: {BOLD}app-cloner create <app-name> --name <clone-name>{RESET}")
        print(f"To find apps, run: {BOLD}app-cloner search <query>{RESET}")
        return 0

    if getattr(args, "json", False):
        output = [
            {
                "id": cfg.id,
                "app_name": cfg.app_name,
                "clone_name": cfg.clone_name,
                "exec": cfg.exec_cmd,
                "badge_color": cfg.badge_color,
                "badge_text": cfg.badge_text,
                "status": status,
            }
            for cfg, status in clones
        ]
        print(json.dumps(output, indent=2))
        return 0

    print(f"\n{BOLD}{'CLONE ID':<22} {'BASE APP':<16} {'CLONE NAME':<22} {'STATUS':<15} {'STORAGE':<10}{RESET}")
    print("─" * 90)

    for cfg, status in clones:
        if status["is_running"]:
            state_str = f"{GREEN}● Running (PID {status['pid']}){RESET}"
        else:
            state_str = f"{DIM}○ Stopped{RESET}"

        print(
            f"{BOLD}{cfg.id:<22}{RESET} "
            f"{cfg.app_name:<16} "
            f"{cfg.clone_name:<22} "
            f"{state_str:<24} "
            f"{status['disk_size']:<10}"
        )

    print(f"\n{DIM}Total: {len(clones)} clone(s){RESET}\n")
    return 0


def cmd_search(args: argparse.Namespace, mgr: CloneManager) -> int:
    apps = scan_installed_apps()
    query = args.query.strip().lower()
    matches = [a for a in apps if query in a.name.lower() or query in a.desktop_id.lower() or query in a.clean_exec.lower()]

    if not matches:
        print(f"{YELLOW}No installed apps matching '{args.query}' found.{RESET}")
        return 1

    print(f"\n{BOLD}Found {len(matches)} matching application(s):{RESET}")
    print(f"{'NAME':<25} {'DESKTOP ID':<35} {'COMMAND':<25}")
    print("─" * 88)
    for a in matches[:30]:
        print(f"{BOLD}{a.name:<25}{RESET} {a.desktop_id:<35} {DIM}{a.clean_exec:<25}{RESET}")

    if len(matches) > 30:
        print(f"\n{DIM}... and {len(matches) - 30} more. Refine your search query.{RESET}")
    print()
    return 0


def cmd_create(args: argparse.Namespace, mgr: CloneManager) -> int:
    app_info = find_app(args.app)
    if not app_info:
        print(f"{RED}Error: Could not find application '{args.app}'.{RESET}")
        print(f"Use {BOLD}app-cloner search {args.app}{RESET} to see available applications.")
        return 1

    clone_name = args.name or f"{app_info.name} (Clone)"
    badge_text = args.badge or (clone_name[:2].upper() if len(clone_name) <= 3 else clone_name[:1].upper())
    badge_color = args.color or "#3b82f6"

    # Parse custom env vars
    custom_env = {}
    if args.env:
        for item in args.env:
            if "=" in item:
                k, v = item.split("=", 1)
                custom_env[k.strip()] = v.strip()

    try:
        cfg = mgr.create_clone(
            app_info=app_info,
            clone_name=clone_name,
            clone_id=args.id,
            badge_color=badge_color,
            badge_text=badge_text,
            share_downloads=args.share_downloads,
            share_documents=args.share_documents,
            share_pictures=args.share_pictures,
            offline_mode=args.offline,
            custom_env=custom_env,
        )
        print(f"\n{GREEN}✔ Clone created successfully!{RESET}")
        print(f"  {BOLD}ID:{RESET}           {cfg.id}")
        print(f"  {BOLD}Name:{RESET}         {cfg.clone_name}")
        print(f"  {BOLD}Base App:{RESET}     {cfg.app_name} ({cfg.desktop_id})")
        print(f"  {BOLD}Badge:{RESET}        {cfg.badge_text} [{cfg.badge_color}]")
        print(f"  {BOLD}Data Dir:{RESET}     {mgr._clone_path(cfg.id) / 'data' / 'home'}")
        print(f"  {BOLD}Desktop File:{RESET} {mgr._desktop_file_path(cfg.id)}")
        print(f"\nTo launch: {BOLD}app-cloner run {cfg.id}{RESET}")
        print(f"Or search for '{cfg.clone_name}' in your application launcher.\n")
        return 0
    except Exception as e:
        print(f"{RED}Error creating clone: {e}{RESET}")
        return 1


def cmd_run(args: argparse.Namespace, mgr: CloneManager) -> int:
    clone_id = args.clone_id
    config = mgr.get_clone(clone_id)
    if not config:
        print(f"{RED}Error: Clone '{clone_id}' does not exist.{RESET}")
        print(f"Run {BOLD}app-cloner list{RESET} to see all existing clones.")
        return 1

    extra_args = args.extra_args if args.extra_args else None
    detach = not args.foreground

    ok, msg, pid = mgr.launch(clone_id, extra_args=extra_args, detach=detach)
    if ok:
        if detach:
            print(f"{GREEN}✔ {msg}{RESET}")
            print(f"{DIM}Log file: {mgr._clone_path(clone_id) / 'launch.log'}{RESET}")
        return 0
    else:
        print(f"{RED}Launch failed: {msg}{RESET}")
        return 1


def cmd_stop(args: argparse.Namespace, mgr: CloneManager) -> int:
    ok, msg = mgr.stop(args.clone_id)
    if ok:
        print(f"{GREEN}✔ {msg}{RESET}")
        return 0
    else:
        print(f"{YELLOW}{msg}{RESET}")
        return 1


def cmd_status(args: argparse.Namespace, mgr: CloneManager) -> int:
    cfg = mgr.get_clone(args.clone_id)
    if not cfg:
        print(f"{RED}Error: Clone '{args.clone_id}' not found.{RESET}")
        return 1

    clone_path = mgr._clone_path(cfg.id)
    pid_file = clone_path / "run.pid"
    pid = mgr._clone_path(cfg.id) / "run.pid"
    from app_cloner.utils import get_directory_size, read_pid_file
    active_pid = read_pid_file(pid_file)
    _, disk_str = get_directory_size(clone_path / "data")

    print(f"\n{BOLD}Clone Details: {cfg.clone_name}{RESET}")
    print(f"  {BOLD}ID:{RESET}           {cfg.id}")
    print(f"  {BOLD}Base App:{RESET}     {cfg.app_name}")
    print(f"  {BOLD}Exec Command:{RESET} {cfg.exec_cmd}")
    print(f"  {BOLD}Status:{RESET}       {GREEN + '● Running (PID ' + str(active_pid) + ')' + RESET if active_pid else DIM + '○ Stopped' + RESET}")
    print(f"  {BOLD}Disk Usage:{RESET}   {disk_str}")
    print(f"  {BOLD}Shared Dirs:{RESET}  Downloads: {cfg.share_downloads}, Documents: {cfg.share_documents}")
    print(f"  {BOLD}Offline Mode:{RESET}{cfg.offline_mode}")
    print(f"  {BOLD}Created At:{RESET}   {cfg.created_at}")
    print(f"  {BOLD}Last Run:{RESET}     {cfg.last_launched or 'Never'}")
    print(f"  {BOLD}Data Path:{RESET}    {clone_path / 'data' / 'home'}")

    log_file = clone_path / "launch.log"
    if log_file.exists():
        print(f"\n{BOLD}Recent Logs (last 10 lines):{RESET}")
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for line in lines[-10:]:
                    print(f"  {DIM}{line.rstrip()}{RESET}")
        except Exception:
            pass
    print()
    return 0


def cmd_reset(args: argparse.Namespace, mgr: CloneManager) -> int:
    cfg = mgr.get_clone(args.clone_id)
    if not cfg:
        print(f"{RED}Error: Clone '{args.clone_id}' not found.{RESET}")
        return 1

    if not args.yes:
        confirm = input(f"{YELLOW}Warning: This will clear all data and credentials for '{cfg.clone_name}'. Continue? [y/N]: {RESET}")
        if confirm.lower() not in ("y", "yes"):
            print("Cancelled.")
            return 0

    ok, msg = mgr.reset_data(args.clone_id)
    if ok:
        print(f"{GREEN}✔ {msg}{RESET}")
        return 0
    else:
        print(f"{RED}Failed: {msg}{RESET}")
        return 1


def cmd_delete(args: argparse.Namespace, mgr: CloneManager) -> int:
    cfg = mgr.get_clone(args.clone_id)
    if not cfg:
        print(f"{RED}Error: Clone '{args.clone_id}' not found.{RESET}")
        return 1

    if not args.yes:
        confirm = input(f"{YELLOW}Are you sure you want to delete '{cfg.clone_name}'? [y/N]: {RESET}")
        if confirm.lower() not in ("y", "yes"):
            print("Cancelled.")
            return 0

    ok, msg = mgr.delete_clone(args.clone_id, keep_data=args.keep_data)
    if ok:
        print(f"{GREEN}✔ {msg}{RESET}")
        return 0
    else:
        print(f"{RED}Failed: {msg}{RESET}")
        return 1


def cmd_export(args: argparse.Namespace, mgr: CloneManager) -> int:
    out_file = args.output or f"{args.clone_id}.tar.gz"
    ok, msg = mgr.export_clone(args.clone_id, Path(out_file))
    if ok:
        print(f"{GREEN}✔ {msg}{RESET}")
        return 0
    else:
        print(f"{RED}Failed: {msg}{RESET}")
        return 1


def cmd_import(args: argparse.Namespace, mgr: CloneManager) -> int:
    ok, msg, cfg = mgr.import_clone(Path(args.archive), new_clone_id=args.id)
    if ok and cfg:
        print(f"{GREEN}✔ {msg}{RESET}")
        print(f"You can now launch it: {BOLD}app-cloner run {cfg.id}{RESET}")
        return 0
    else:
        print(f"{RED}Failed: {msg}{RESET}")
        return 1


def cmd_open(args: argparse.Namespace, mgr: CloneManager) -> int:
    cfg = mgr.get_clone(args.clone_id)
    if not cfg:
        print(f"{RED}Error: Clone '{args.clone_id}' not found.{RESET}")
        return 1
    clone_home = mgr._clone_path(cfg.id) / "data" / "home"
    subprocess.run(["xdg-open", str(clone_home)], check=False)
    return 0


def cmd_gui(args: argparse.Namespace, mgr: CloneManager) -> int:
    from app_cloner.gui import launch_gui
    return launch_gui()


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="app-cloner",
        description="Arch App Cloner: Run multiple isolated instances of applications with separate data and credentials.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Command to run")

    # list
    p_list = subparsers.add_parser("list", aliases=["ls"], help="List all cloned applications")
    p_list.add_argument("--json", action="store_true", help="Output in JSON format")

    # search
    p_search = subparsers.add_parser("search", aliases=["find"], help="Search installed applications available to clone")
    p_search.add_argument("query", help="App name, desktop ID, or command to search")

    # create
    p_create = subparsers.add_parser("create", aliases=["new", "add"], help="Create a new clone for an application")
    p_create.add_argument("app", help="Application name, binary, or .desktop ID to clone")
    p_create.add_argument("--name", "-n", help="Display name for the clone (e.g. 'Discord - Work')")
    p_create.add_argument("--id", help="Custom identifier for the clone folder")
    p_create.add_argument("--color", "-c", default="#3b82f6", help="Badge color hex (e.g. '#3b82f6', '#10b981', '#ef4444')")
    p_create.add_argument("--badge", "-b", help="Short badge label (e.g. 'W', '2', 'DEV')")
    p_create.add_argument("--share-downloads", action="store_true", help="Mount host ~/Downloads into the clone")
    p_create.add_argument("--share-documents", action="store_true", help="Mount host ~/Documents into the clone")
    p_create.add_argument("--share-pictures", action="store_true", help="Mount host ~/Pictures into the clone")
    p_create.add_argument("--offline", action="store_true", help="Disable network access inside the clone")
    p_create.add_argument("--env", "-e", action="append", help="Set environment variable (KEY=VALUE)")

    # run
    p_run = subparsers.add_parser("run", aliases=["launch", "start"], help="Launch a cloned application")
    p_run.add_argument("clone_id", help="Identifier of the clone to run")
    p_run.add_argument("--foreground", "-f", action="store_true", help="Run in foreground instead of detached background")
    p_run.add_argument("extra_args", nargs="*", help="Extra arguments passed to the application")

    # stop
    p_stop = subparsers.add_parser("stop", aliases=["kill"], help="Stop a running clone instance")
    p_stop.add_argument("clone_id", help="Identifier of the clone to stop")

    # status
    p_status = subparsers.add_parser("status", help="Show detailed status and recent logs for a clone")
    p_status.add_argument("clone_id", help="Identifier of the clone")

    # reset
    p_reset = subparsers.add_parser("reset", help="Reset all data/credentials for a clone to empty state")
    p_reset.add_argument("clone_id", help="Identifier of the clone")
    p_reset.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    # delete
    p_delete = subparsers.add_parser("delete", aliases=["rm"], help="Delete a clone and remove its desktop shortcut")
    p_delete.add_argument("clone_id", help="Identifier of the clone to delete")
    p_delete.add_argument("--keep-data", action="store_true", help="Keep the data folder on disk")
    p_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    # export
    p_export = subparsers.add_parser("export", help="Export clone and its data to a portable .tar.gz archive")
    p_export.add_argument("clone_id", help="Identifier of the clone to export")
    p_export.add_argument("output", nargs="?", help="Output file path (default: <clone_id>.tar.gz)")

    # import
    p_import = subparsers.add_parser("import", help="Import clone from a .tar.gz archive")
    p_import.add_argument("archive", help="Path to archive file")
    p_import.add_argument("--id", help="Optional new clone ID")

    # open
    p_open = subparsers.add_parser("open", help="Open clone's data directory in file manager")
    p_open.add_argument("clone_id", help="Identifier of the clone")

    # gui
    subparsers.add_parser("gui", help="Open the graphical user interface")

    if not argv:
        parser.print_help()
        return 0

    parsed = parser.parse_args(argv)
    mgr = CloneManager()

    dispatch = {
        "list": cmd_list,
        "ls": cmd_list,
        "search": cmd_search,
        "find": cmd_search,
        "create": cmd_create,
        "new": cmd_create,
        "add": cmd_create,
        "run": cmd_run,
        "launch": cmd_run,
        "start": cmd_run,
        "stop": cmd_stop,
        "kill": cmd_stop,
        "status": cmd_status,
        "reset": cmd_reset,
        "delete": cmd_delete,
        "rm": cmd_delete,
        "export": cmd_export,
        "import": cmd_import,
        "open": cmd_open,
        "gui": cmd_gui,
    }

    handler = dispatch.get(parsed.subcommand)
    if handler:
        return handler(parsed, mgr)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
