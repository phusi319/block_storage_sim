"""Shared simulator data models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import ConveyorState, LifterState


@dataclass(frozen=True, slots=True)
class TransferCommand:
    src_x: float
    src_y: float
    dst_x: float
    dst_y: float


@dataclass(frozen=True, slots=True)
class StackPosition:
    x: float
    y: float


@dataclass(slots=True)
class SymbolTable:
    """ADS-like symbol values kept intentionally close to the exposed spec."""

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
    pallet_in_system: bool = True
    next_block_id: int = 1
    pallet_relative_blocks: dict[StackPosition, list[int]] = field(default_factory=dict)
    storage_blocks: dict[StackPosition, list[int]] = field(default_factory=dict)
    last_error: str | None = None
    diagnostics: list[str] = field(default_factory=list)

    @property
    def pallet_stack_count(self) -> int:
        return sum(len(block_ids) for block_ids in self.pallet_relative_blocks.values())

    @property
    def storage_stack_count(self) -> int:
        return len(self.storage_blocks)
