"""Entry point for the Fly-in simulation."""

from __future__ import annotations

import argparse


def main() -> None:
    """Parse command-line arguments and dispatch the requested mode."""
    parser = argparse.ArgumentParser(
        prog="fly-in", description="Drone fleet routing simulation"
    )
    parser.add_argument("map", help="path to the .map file")
    parser.add_argument(
        "--gui", action="store_true", help="render the map in a window"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug mode (conflicts to stderr)",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="disable ANSI color output"
    )
    args = parser.parse_args()

    if args.gui:
        from src.gui.app import run as run_gui

        run_gui(args.map)
        return

    from src.cli import run as run_cli

    run_cli(args.map, debug=args.debug, color=False if args.no_color else None)


if __name__ == "__main__":
    main()
