"""Simple Tkinter GUI for simulator observation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .constants import (
    AREA_MAX_X,
    AREA_MAX_Y,
    BLOCK_SIZE_MM,
    CONVEYOR_RESERVED_MIN_Y,
    PALLET_SIZE_MM,
    TRANSFER_SLOT_CENTER_X,
    TRANSFER_SLOT_CENTER_Y,
    ConveyorState,
)
from .models import StackPosition
from .simulator import BlockStorageSimulator


class SimulatorApp:
    """Observer-oriented GUI for backend state and storage visualization."""

    HOME_SLOT_CENTER = StackPosition(420.0, 520.0)
    IMAGING_SLOT_CENTER = StackPosition(90.0, TRANSFER_SLOT_CENTER_Y)
    REFRESH_MS = 250
    CANVAS_PADDING = 16
    AREA_LEFT = 220.0
    SLOT_BOX_SIZE = PALLET_SIZE_MM + 20.0

    def __init__(self, simulator: BlockStorageSimulator) -> None:
        self.simulator = simulator
        self.root = tk.Tk()
        self.root.title("Block Storage Simulator")
        self.root.geometry("920x700")

        self.status_text = tk.StringVar()
        self.error_text = tk.StringVar()

        self._build_layout()
        self.refresh()
        self.root.after(self.REFRESH_MS, self._poll_refresh)

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Block Storage Simulator", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(
            container,
            text="Backend observer for pallet position and stored blocks. Conveyor and lifter actions come from the ADS client side.",
        ).pack(anchor=tk.W, pady=(4, 12))

        status_frame = ttk.LabelFrame(container, text="Status", padding=12)
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, textvariable=self.status_text, justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Label(status_frame, textvariable=self.error_text, foreground="#9a1b1b").pack(anchor=tk.W, pady=(8, 0))

        controls_frame = ttk.LabelFrame(container, text="Manual Tools", padding=12)
        controls_frame.pack(fill=tk.X, pady=(12, 0))
        self.add_button = ttk.Button(controls_frame, text="Add Block To Home Pallet", command=self._add_home_pallet_block)
        self.add_button.pack(side=tk.LEFT, padx=(0, 8))
        self.remove_button = ttk.Button(
            controls_frame,
            text="Remove Block From Home Pallet",
            command=self._remove_home_pallet_block,
        )
        self.remove_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(controls_frame, text="Reset", command=self._reset).pack(side=tk.LEFT)

        diagram_frame = ttk.LabelFrame(container, text="Storage View", padding=12)
        diagram_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.canvas = tk.Canvas(diagram_frame, width=760, height=620, bg="#fbfaf6", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        diagnostics_frame = ttk.LabelFrame(container, text="Warnings And Alarms", padding=12)
        diagnostics_frame.pack(fill=tk.BOTH, expand=False, pady=(12, 0))
        self.diagnostics_list = tk.Listbox(diagnostics_frame, height=6)
        diagnostics_scroll = ttk.Scrollbar(diagnostics_frame, orient=tk.VERTICAL, command=self.diagnostics_list.yview)
        self.diagnostics_list.configure(yscrollcommand=diagnostics_scroll.set)
        self.diagnostics_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        diagnostics_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        notes_frame = ttk.LabelFrame(container, text="Notes", padding=12)
        notes_frame.pack(fill=tk.X, pady=(12, 0))
        notes = (
            "- The GUI does not drive conveyor or lifter commands.\n"
            "- Reset returns the simulator to a fresh state.\n"
            "- Blocks can only be added to or removed from the pallet when it is at home."
        )
        ttk.Label(notes_frame, text=notes, justify=tk.LEFT).pack(anchor=tk.W)

    def _reset(self) -> None:
        self.simulator.reset()
        self.refresh()

    def _add_home_pallet_block(self) -> None:
        self.simulator.add_block_to_home_pallet()
        self.refresh()

    def _remove_home_pallet_block(self) -> None:
        self.simulator.remove_block_from_home_pallet()
        self.refresh()

    def _poll_refresh(self) -> None:
        self.refresh()
        self.root.after(self.REFRESH_MS, self._poll_refresh)

    def refresh(self) -> None:
        state = self.simulator.state
        self.status_text.set(
            "\n".join(
                [
                    f"ConveyorState: {state.conveyor_state.value} ({state.conveyor_state.name})",
                    f"LifterState: {state.lifter_state.value} ({state.lifter_state.name})",
                    f"Pallet blocks: {state.pallet_stack_count}",
                    f"Storage stacks: {state.storage_stack_count}",
                ]
            )
        )
        self.error_text.set(f"Last error: {state.last_error or '-'}")
        self._refresh_diagnostics()

        can_modify_home_pallet = self.simulator.can_modify_pallet_at_home()
        if can_modify_home_pallet:
            self.add_button.state(["!disabled"])
            self.remove_button.state(["!disabled"])
        else:
            self.add_button.state(["disabled"])
            self.remove_button.state(["disabled"])

        self._draw_scene()

    def _draw_scene(self) -> None:
        self.canvas.delete("all")

        pad = self.CANVAS_PADDING
        left = pad + self.AREA_LEFT
        top = pad
        right = left + AREA_MAX_X
        bottom = pad + AREA_MAX_Y
        reserved_top = pad + CONVEYOR_RESERVED_MIN_Y

        self.canvas.create_rectangle(left, top, right, bottom, fill="#f7f4ee", outline="#9d907d", width=2)
        self.canvas.create_rectangle(left, top, right, reserved_top, fill="#fdfcf8", outline="")
        self.canvas.create_rectangle(left, reserved_top, right, bottom, fill="#ece3d3", outline="")

        self.canvas.create_text(left + 8, top + 8, anchor="nw", text="Storage area (x grows left)", fill="#544b3d")
        self.canvas.create_text(left + 8, reserved_top + 8, anchor="nw", text="Transfer area (x grows left)", fill="#544b3d")

        self._draw_station("Home", self.HOME_SLOT_CENTER, in_area=False, show_coords=False)
        self._draw_station("Imaging", self.IMAGING_SLOT_CENTER, in_area=False, show_coords=False)
        self._draw_station("Transfer", StackPosition(TRANSFER_SLOT_CENTER_X, TRANSFER_SLOT_CENTER_Y), in_area=True, show_coords=True)

        for position, block_ids in self.simulator.state.storage_blocks.items():
            self._draw_block_stack(position, block_ids, pallet_relative=False, in_area=True, show_coords=True)

        pallet_center = self._current_pallet_center()
        if pallet_center is not None:
            pallet_in_area = pallet_center == StackPosition(TRANSFER_SLOT_CENTER_X, TRANSFER_SLOT_CENTER_Y)
            self._draw_pallet(pallet_center, in_area=pallet_in_area, show_coords=pallet_in_area)
            for relative_position, block_ids in self.simulator.state.pallet_relative_blocks.items():
                absolute_position = StackPosition(
                    pallet_center.x + relative_position.x,
                    pallet_center.y + relative_position.y,
                )
                self._draw_block_stack(absolute_position, block_ids, pallet_relative=True, in_area=pallet_in_area, show_coords=pallet_in_area)

    def _draw_station(self, label: str, position: StackPosition, in_area: bool, show_coords: bool) -> None:
        x = self._canvas_x(position.x, in_area=in_area)
        y = self.CANVAS_PADDING + position.y
        if label == "Transfer":
            slot_half = self.SLOT_BOX_SIZE / 2.0
            self.canvas.create_rectangle(
                x - slot_half,
                y - slot_half,
                x + slot_half,
                y + slot_half,
                outline="#8b7c69",
                width=2,
                dash=(4, 2),
            )
        self.canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill="#7f705e", outline="")
        self.canvas.create_text(x, y - 18, text=label, fill="#544b3d")
        if show_coords:
            self.canvas.create_text(x, y + 18, text=self._format_coords(position), fill="#544b3d")

    def _draw_pallet(self, center: StackPosition, in_area: bool, show_coords: bool) -> None:
        half = PALLET_SIZE_MM / 2.0
        x0 = self._canvas_x(center.x, in_area=in_area) - half
        y0 = self.CANVAS_PADDING + center.y - half
        x1 = self._canvas_x(center.x, in_area=in_area) + half
        y1 = self.CANVAS_PADDING + center.y + half
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="#cbb48a", outline="#7b6540", width=2)
        if show_coords:
            self.canvas.create_text(self._canvas_x(center.x, in_area=in_area), y0 - 12, text=f"Pallet {self._format_coords(center)}", fill="#7b6540")
        else:
            self.canvas.create_text(self._canvas_x(center.x, in_area=in_area), y0 - 12, text="Pallet", fill="#7b6540")

    def _draw_block_stack(
        self,
        center: StackPosition,
        block_ids: list[int],
        pallet_relative: bool,
        in_area: bool,
        show_coords: bool,
    ) -> None:
        half = BLOCK_SIZE_MM / 2.0
        x0 = self._canvas_x(center.x, in_area=in_area) - half
        y0 = self.CANVAS_PADDING + center.y - half
        x1 = self._canvas_x(center.x, in_area=in_area) + half
        y1 = self.CANVAS_PADDING + center.y + half
        fill = "#6f90c8" if pallet_relative else "#799f73"
        outline = "#2e3b55" if pallet_relative else "#355333"
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=2)
        top_block_id = block_ids[-1]
        label = f"#{top_block_id}"
        if len(block_ids) > 1:
            label = f"#{top_block_id} ({len(block_ids)})"
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        self.canvas.create_text(center_x, center_y - 10, text=label, fill="white")
        if show_coords:
            self.canvas.create_text(center_x, center_y + 10, text=self._format_coords(center), fill="white")

    def _current_pallet_center(self) -> StackPosition | None:
        state = self.simulator.state.conveyor_state
        if state in {ConveyorState.WAITING_AT_HOME, ConveyorState.MOVING_TO_HOME}:
            return self.HOME_SLOT_CENTER
        if state in {ConveyorState.IMAGING, ConveyorState.MOVING_TO_IMAGING}:
            return self.IMAGING_SLOT_CENTER
        if state in {ConveyorState.WAITING_IN_SLOT, ConveyorState.MOVING_TO_SLOT}:
            return StackPosition(TRANSFER_SLOT_CENTER_X, TRANSFER_SLOT_CENTER_Y)
        return None

    def _refresh_diagnostics(self) -> None:
        self.diagnostics_list.delete(0, tk.END)
        for entry in self.simulator.state.diagnostics:
            self.diagnostics_list.insert(tk.END, entry)

    def _canvas_x(self, x: float, in_area: bool) -> float:
        if in_area:
            return self.CANVAS_PADDING + self.AREA_LEFT + (AREA_MAX_X - x)
        return self.CANVAS_PADDING + x

    def _format_coords(self, position: StackPosition) -> str:
        return f"({position.x:.0f}, {position.y:.0f})"

    def run(self) -> None:
        self.root.mainloop()
