"""CLI entry point for the simulator."""

from __future__ import annotations

from .gui import SimulatorApp
from .simulator import BlockStorageSimulator


def main() -> None:
    simulator = BlockStorageSimulator()
    app = SimulatorApp(simulator)
    app.run()


if __name__ == "__main__":
    main()
