"""Simple Tkinter GUI for manual simulator testing."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .models import TransferCommand
from .simulator import BlockStorageSimulator


class SimulatorApp:
    def __init__(self, simulator: BlockStorageSimulator) -> None:
        self.simulator = simulator
        self.root = tk.Tk()
        self.root.title("Block Storage Simulator")
        self.root.geometry("760x520")

        self.status_text = tk.StringVar()
        self.error_text = tk.StringVar()
        self.src_x = tk.StringVar(value="100")
        self.src_y = tk.StringVar(value="100")
        self.dst_x = tk.StringVar(value="200")
        self.dst_y = tk.StringVar(value="200")

        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(container, text="Block Storage Simulator", font=("Segoe UI", 16, "bold"))
        header.pack(anchor=tk.W)

        ttk.Label(
            container,
            text="Simple local test GUI for conveyor states and transfer commands.",
        ).pack(anchor=tk.W, pady=(4, 12))

        status_frame = ttk.LabelFrame(container, text="Status", padding=12)
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, textvariable=self.status_text, justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Label(status_frame, textvariable=self.error_text, foreground="#9a1b1b").pack(anchor=tk.W, pady=(8, 0))

        conveyor_frame = ttk.LabelFrame(container, text="Conveyor Commands", padding=12)
        conveyor_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(conveyor_frame, text="Startup", command=self._startup).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(conveyor_frame, text="Send Pallet", command=self._send_pallet).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(conveyor_frame, text="Release From Imaging", command=self._release_from_imaging).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(conveyor_frame, text="Return Pallet", command=self._return_pallet).pack(side=tk.LEFT)

        transfer_frame = ttk.LabelFrame(container, text="Transfer Item", padding=12)
        transfer_frame.pack(fill=tk.X, pady=(12, 0))

        self._coord_entry(transfer_frame, "Source X", self.src_x, 0)
        self._coord_entry(transfer_frame, "Source Y", self.src_y, 1)
        self._coord_entry(transfer_frame, "Destination X", self.dst_x, 2)
        self._coord_entry(transfer_frame, "Destination Y", self.dst_y, 3)

        ttk.Button(transfer_frame, text="Transfer Item", command=self._transfer_item).grid(row=0, column=4, rowspan=2, padx=(12, 0))

        notes_frame = ttk.LabelFrame(container, text="Notes", padding=12)
        notes_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        notes = (
            "- Commands follow the current spec state rules.\n"
            "- Transfer coordinates are treated as center points.\n"
            "- This GUI is local only; ADS transport is a later integration step."
        )
        ttk.Label(notes_frame, text=notes, justify=tk.LEFT).pack(anchor=tk.W)

    def _coord_entry(self, parent: ttk.Widget, label: str, variable: tk.StringVar, column: int) -> None:
        ttk.Label(parent, text=label).grid(row=0, column=column, sticky=tk.W)
        ttk.Entry(parent, textvariable=variable, width=10).grid(row=1, column=column, padx=(0, 8), sticky=tk.W)

    def _startup(self) -> None:
        self.simulator.startup()
        self.refresh()

    def _send_pallet(self) -> None:
        self.simulator.send_pallet()
        self.refresh()

    def _release_from_imaging(self) -> None:
        self.simulator.release_from_imaging()
        self.refresh()

    def _return_pallet(self) -> None:
        self.simulator.return_pallet()
        self.refresh()

    def _transfer_item(self) -> None:
        try:
            command = TransferCommand(
                src_x=float(self.src_x.get()),
                src_y=float(self.src_y.get()),
                dst_x=float(self.dst_x.get()),
                dst_y=float(self.dst_y.get()),
            )
        except ValueError:
            self.simulator.state.last_error = "coordinates must be numeric"
            self.refresh()
            return

        self.simulator.transfer_item(command)
        self.refresh()

    def refresh(self) -> None:
        state = self.simulator.state
        self.status_text.set(
            "\n".join(
                [
                    f"ConveyorState: {state.conveyor_state.value} ({state.conveyor_state.name})",
                    f"LifterState: {state.lifter_state.value} ({state.lifter_state.name})",
                    f"Stored stack locations: {len(state.blocks_by_center)}",
                ]
            )
        )
        self.error_text.set(f"Last error: {state.last_error or '-'}")

    def run(self) -> None:
        self.root.mainloop()
