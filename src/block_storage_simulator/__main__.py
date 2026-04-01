"""CLI entry point for the simulator."""

from __future__ import annotations

import argparse
import time

from .ads_server import AdsServer
from .gui import SimulatorApp
from .simulator import BlockStorageSimulator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Block storage simulator")
    parser.add_argument(
        "--mode",
        choices=("gui", "ads", "both"),
        default="gui",
        help="Run the local GUI, the ADS server, or both.",
    )
    parser.add_argument(
        "--bind",
        default="127.0.0.1",
        help="IP address to bind the ADS server to when ADS mode is enabled.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=48898,
        help="TCP port for the ADS server.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    simulator = BlockStorageSimulator()
    server: AdsServer | None = None

    if args.mode in {"ads", "both"}:
        server = AdsServer(simulator=simulator, ip_address=args.bind, port=args.port)
        server.start()

    if args.mode in {"gui", "both"}:
        app = SimulatorApp(simulator)
        try:
            app.run()
        finally:
            if server is not None:
                server.stop()
        return

    try:
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        if server is not None:
            server.stop()


if __name__ == "__main__":
    main()
