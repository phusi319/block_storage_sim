"""Shared simulator data models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import ConveyorState, LifterState, TRANSFER_SLOT_CENTER_X, TRANSFER_SLOT_CENTER_Y


@dataclass(slots=True)
class TransferCommand:
    src_x: float
    src_y: float
    dst_x: float
    dst_y: float


@dataclass(slots=True)
class SymbolTable:
    """ADS-like symbol values kept intentionally small and close to the spec."""

    remote_send_pallet: bool = False
    remote_release_from_imaging: bool = False
    remote_return_pallet: bool = False
    remote_transfer_item: bool = False
    remote_src_x: float = 0.0
    remote_src_y: float = 0.0
    remote_dst_x: float = 0.0
    remote_dst_y: float = 0.0
    conveyor_state: ConveyorState = ConveyorState.INITIALIZE
    lifter_state: LifterState = LifterState.READY


@dataclass(slots=True)
class SimulatorState:
    conveyor_state: ConveyorState = ConveyorState.INITIALIZE
    lifter_state: LifterState = LifterState.READY
    pallet_loaded: bool = False
    pallet_in_system: bool = True
    pallet_center_x: float = TRANSFER_SLOT_CENTER_X
    pallet_center_y: float = TRANSFER_SLOT_CENTER_Y
    blocks_by_center: dict[tuple[float, float], int] = field(default_factory=dict)
    last_error: str | None = None
