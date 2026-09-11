"""Command-line interface: install, export, check, build, status."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from skeletons.paths import repo_root


def _load_skeleton_builder():
    path = repo_root() / "tools" / "build_skeleton.py"
    spec = importlib.util.spec_from_file_location("skel_build_skeleton", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_paths(_args: argparse.Namespace) -> int:
    from skeletons.config import CONFIG_FILE, load
    from skeletons.export import install_dir, resource_dir

    cfg = load()
    print(f"checkout          {repo_root()}")
    print(f"config            {CONFIG_FILE}")
    print(f"REAPER resource   {resource_dir(cfg)}")
    print(f"REAPER install    {install_dir(cfg)}")
    print(f"HTTP              {cfg['http_host']}:{cfg['http_port']}")
    print(f"OSC send/listen   {cfg['osc_send_port']} / {cfg['osc_listen_port']}")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    from skeletons import SECTION
    from skeletons.bridge.http import HttpBridge
    from skeletons.config import load

    cfg = load()
    http = HttpBridge(str(cfg["http_host"]), int(cfg["http_port"]))
    probe = http.probe()
    if not probe["alive"]:
        print(f"REAPER HTTP  down  ({probe['error'] or 'no TRANSPORT'})")
        return 1
    agent = "up" if probe["agent_alive"] else "down"
    print(
        f"REAPER HTTP  up    {probe['ntrack']} tracks  "
        f"agent {agent}  {SECTION}/agent.alive={probe['agent_value'] or 'empty'}"
    )
    return 0 if probe["agent_alive"] else 2


def cmd_check(_args: argparse.Namespace) -> int:
    from skeletons.doctor import run_check

    return run_check()


def cmd_export(args: argparse.Namespace) -> int:
    from skeletons.config import load
    from skeletons.export import (
        export_resources,
        relative_dest,
        remove_stale_clap,
        remove_stale_jsfx,
    )

    cfg = load()
    results = export_resources(cfg, dry_run=args.dry_run)
    copied = updated = unchanged = missing = 0
    for result in results:
        rel = relative_dest(result.item, cfg)
        if result.status == "unchanged":
            unchanged += 1
            if args.verbose:
                print(f"  =  {rel}")
        elif result.status == "copied":
            copied += 1
            print(f"  +  {rel}")
        elif result.status in ("would-copy", "would-update"):
            updated += 1
            print(f"  ~  {rel}  ({result.status})")
        elif result.status == "missing-src":
            missing += 1
            print(f"  !  missing checkout file {result.item.src}")
    for path in remove_stale_jsfx(cfg, dry_run=args.dry_run):
        print(f"  {'~' if args.dry_run else '-'}  Effects/Skeletons/{path.name}")
    for path in remove_stale_clap(cfg, dry_run=args.dry_run):
        print(f"  {'~' if args.dry_run else '-'}  {path}  (retired CLAP pedal)")
    print(
        f"{copied} copied, {updated} pending, {unchanged} unchanged, {missing} missing source"
        if args.dry_run
        else f"{copied} copied, {unchanged} unchanged, {missing} missing source"
    )
    return 1 if missing else 0


def cmd_build(args: argparse.Namespace) -> int:
    mod = _load_skeleton_builder()
    code = int(mod.main() or 0)
    if code:
        return code
    return cmd_export(args)


def cmd_install(args: argparse.Namespace) -> int:
    from skeletons.config import load, push_to_agent
    from skeletons.export import (
        ensure_csurfaces,
        ensure_startup,
        export_resources,
        prepare_config,
        relative_dest,
        remove_stale_clap,
        remove_stale_jsfx,
        write_desktops,
    )

    dry = args.dry_run
    print("Skeletons install")
    print("================")
    cfg = prepare_config() if not dry else load()
    print(f"resource  {cfg['reaper_resource']}")

    print("\n1. Skeleton templates")
    if dry:
        print("  (skip write in --dry-run)")
    else:
        code = int(_load_skeleton_builder().main() or 0)
        if code:
            return code

    print("\n2. Export Lua / JSFX / OSC / track template")
    results = export_resources(cfg, dry_run=dry)
    for result in results:
        rel = relative_dest(result.item, cfg)
        mark = {"copied": "+", "unchanged": "=", "would-copy": "~", "would-update": "~", "missing-src": "!"}.get(
            result.status, "?"
        )
        print(f"  {mark}  {rel}")
    if any(r.status == "missing-src" for r in results):
        return 1
    stale = remove_stale_jsfx(cfg, dry_run=dry)
    for path in stale:
        print(f"  {'~' if dry else '-'}  Effects/Skeletons/{path.name}  (stale .jsfx ident)")
    for path in remove_stale_clap(cfg, dry_run=dry):
        print(f"  {'~' if dry else '-'}  {path}  (retired CLAP pedal)")

    print("\n3. FXChains library (SkeletonsGuitar/IN … FX)")
    from skeletons.library import seed_example_chains
    from skeletons.paths import repo_root

    if dry:
        print("  (skip seed in --dry-run)")
    else:
        for dest, status in seed_example_chains(cfg, repo_root()):
            rel = str(dest)
            try:
                rel = str(dest.relative_to(Path(cfg["reaper_resource"]).expanduser()))
            except ValueError:
                pass
            mark = {"copied": "+", "unchanged": "="}.get(status, "?")
            print(f"  {mark}  {rel}")

    print("\n4. Agent autoload")
    print(f"  {ensure_startup(cfg, dry_run=dry)}  Scripts/__startup.lua")

    print("\n5. Control surfaces (reaper.ini)")
    print(f"  {ensure_csurfaces(cfg, dry_run=dry)}")

    print("\n6. Desktop launchers")
    for path in write_desktops(cfg, dry_run=dry):
        print(f"  {'~' if dry else '+'}  {path}")

    if not dry:
        err = push_to_agent(cfg)
        print("\n7. Running instance")
        if err:
            print(f"  HTTP not reached ({err})")
            print("  Start REAPER, then restart it once so __startup.lua loads the new agent.")
        else:
            print("  published checkout paths to ExtState (Skeletons)")
            print("  Restart REAPER so it reloads the agent and JSFX.")

    print("\nNext: python3 -m skeletons check")
    print("      python3 -m skeletons status")
    print("      ./launch.sh")
    print("      ./cleanup.sh   # remove leftover ReaperAPP files")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    from skeletons.config import load
    from skeletons.deploy import run_uninstall

    return run_uninstall(load(), dry_run=args.dry_run, purge_config=args.purge_config)


def cmd_cleanup(args: argparse.Namespace) -> int:
    from skeletons.config import load
    from skeletons.deploy import run_cleanup

    return run_cleanup(load(), dry_run=args.dry_run, purge_config=args.purge_config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skeletons",
        description=(
            "Install Skeletons into a REAPER resource folder, verify the GTK 4 "
            "environment, and keep Lua/JSFX/OSC copies in sync with this checkout."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser(
        "install",
        help="build templates, export resources into REAPER, patch startup and surfaces",
    )
    p_install.add_argument("--dry-run", action="store_true", help="print actions without writing")
    p_install.set_defaults(func=cmd_install)

    p_export = sub.add_parser("export", help="copy Lua, JSFX, OSC and the guitar template into REAPER")
    p_export.add_argument("--dry-run", action="store_true")
    p_export.add_argument("-v", "--verbose", action="store_true")
    p_export.set_defaults(func=cmd_export)

    p_build = sub.add_parser("build", help="write Skeletons.RPP / SkeletonsGuitar template, then export")
    p_build.add_argument("--dry-run", action="store_true", help="export dry-run after building")
    p_build.add_argument("-v", "--verbose", action="store_true")
    p_build.set_defaults(func=cmd_build)

    p_check = sub.add_parser("check", help="GTK 4, exported files, HTTP, agent")
    p_check.set_defaults(func=cmd_check)

    p_status = sub.add_parser("status", help="one-line REAPER HTTP + agent probe")
    p_status.set_defaults(func=cmd_status)

    p_paths = sub.add_parser("paths", help="print checkout and REAPER folders")
    p_paths.set_defaults(func=cmd_paths)

    p_un = sub.add_parser(
        "uninstall",
        help="remove Skeletons scripts, JSFX, OSC, templates and desktop launchers",
    )
    p_un.add_argument("--dry-run", action="store_true")
    p_un.add_argument(
        "--purge-config",
        action="store_true",
        help="also delete ~/.config/Skeletons",
    )
    p_un.set_defaults(func=cmd_uninstall)

    p_clean = sub.add_parser(
        "cleanup",
        help="delete leftover ReaperAPP / rapp_* files from REAPER and ~/.local/share/applications",
    )
    p_clean.add_argument("--dry-run", action="store_true")
    p_clean.add_argument(
        "--purge-config",
        action="store_true",
        help="also delete ~/.config/ReaperAPP",
    )
    p_clean.set_defaults(func=cmd_cleanup)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)
