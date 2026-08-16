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
        "--debug", action="store_true", help="enable debug mode (no-op)"
    )
    args = parser.parse_args()

    if args.gui:
        from src.gui.app import run as run_gui

        run_gui(args.map)
        return

    raise SystemExit("simulation run not implemented yet")


if __name__ == "__main__":
    main()
