"""Core simulator behavior."""

from __future__ import annotations

from dataclasses import asdict

from .constants import (
    AREA_MAX_X,
    AREA_MAX_Y,
    AREA_MIN_X,
    AREA_MIN_Y,
    CONVEYOR_RESERVED_MAX_X,
    CONVEYOR_RESERVED_MAX_Y,
    CONVEYOR_RESERVED_MIN_X,
    CONVEYOR_RESERVED_MIN_Y,
    MAX_STACK_HEIGHT,
    ConveyorState,
    LifterState,
)
from .models import SimulatorState, SymbolTable, TransferCommand


class BlockStorageSimulator:
    """Simple deterministic simulator core with an ADS-oriented symbol model."""

    def __init__(self) -> None:
        self.state = SimulatorState()
        self.symbols = SymbolTable()
        self._sync_status_symbols()

    def startup(self) -> None:
        self.state.conveyor_state = ConveyorState.NOT_HOMED
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.HOMING
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.BRAKING
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.WAITING_AT_HOME
        self._sync_status_symbols()

    def reset(self) -> None:
        self.state = SimulatorState()
        self.symbols = SymbolTable()
        self._sync_status_symbols()

    def send_pallet(self) -> bool:
        if self.state.conveyor_state != ConveyorState.WAITING_AT_HOME:
            return self._fail("send_pallet is only valid at home")
        self.state.conveyor_state = ConveyorState.MOVING_TO_IMAGING
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.IMAGING
        self._sync_status_symbols()
        return True

    def release_from_imaging(self) -> bool:
        if self.state.conveyor_state != ConveyorState.IMAGING:
            return self._fail("release_from_imaging is only valid at imaging")
        self.state.conveyor_state = ConveyorState.MOVING_TO_SLOT
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.WAITING_IN_SLOT
        self._sync_status_symbols()
        return True

    def return_pallet(self) -> bool:
        if self.state.conveyor_state != ConveyorState.WAITING_IN_SLOT:
            return self._fail("return_pallet is only valid at transfer slot")
        self.state.conveyor_state = ConveyorState.MOVING_TO_HOME
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.WAITING_AT_HOME
        self._sync_status_symbols()
        return True

    def transfer_item(self, command: TransferCommand) -> bool:
        if not self._point_in_bounds(command.src_x, command.src_y):
            return self._fail("source point is outside the modeled area")
        if not self._point_in_bounds(command.dst_x, command.dst_y):
            return self._fail("destination point is outside the modeled area")
        if self._is_reserved_area(command.dst_x, command.dst_y):
            return self._fail("destination is inside the conveyor reserved area")

        dst = (command.dst_x, command.dst_y)
        current_height = self.state.blocks_by_center.get(dst, 0)
        if current_height >= MAX_STACK_HEIGHT:
            return self._fail("destination stack would exceed maximum height")

        self.state.lifter_state = LifterState.BUSY
        self._sync_status_symbols()
        self.state.blocks_by_center[dst] = current_height + 1
        self.state.lifter_state = LifterState.READY
        self.state.last_error = None
        self._sync_status_symbols()
        return True

    def consume_edge_triggered_commands(self) -> list[str]:
        """Consume command symbols as an ADS-style edge-triggered cycle."""

        events: list[str] = []
        if self.symbols.remote_send_pallet:
            self.symbols.remote_send_pallet = False
            self.send_pallet()
            events.append("Remote.send_pallet")
        if self.symbols.remote_release_from_imaging:
            self.symbols.remote_release_from_imaging = False
            self.release_from_imaging()
            events.append("Remote.release_from_imaging")
        if self.symbols.remote_return_pallet:
            self.symbols.remote_return_pallet = False
            self.return_pallet()
            events.append("Remote.return_pallet")
        if self.symbols.remote_transfer_item:
            self.symbols.remote_transfer_item = False
            self.transfer_item(
                TransferCommand(
                    src_x=self.symbols.remote_src_x,
                    src_y=self.symbols.remote_src_y,
                    dst_x=self.symbols.remote_dst_x,
                    dst_y=self.symbols.remote_dst_y,
                )
            )
            events.append("Remote.transfer_item")
        return events

    def snapshot(self) -> dict[str, object]:
        data = asdict(self.state)
        data["conveyor_state"] = self.state.conveyor_state.name
        data["lifter_state"] = self.state.lifter_state.name
        return data

    def _sync_status_symbols(self) -> None:
        self.symbols.conveyor_state = self.state.conveyor_state
        self.symbols.lifter_state = self.state.lifter_state

    def _point_in_bounds(self, x: float, y: float) -> bool:
        return AREA_MIN_X <= x <= AREA_MAX_X and AREA_MIN_Y <= y <= AREA_MAX_Y

    def _is_reserved_area(self, x: float, y: float) -> bool:
        return (
            CONVEYOR_RESERVED_MIN_X <= x <= CONVEYOR_RESERVED_MAX_X
            and CONVEYOR_RESERVED_MIN_Y <= y <= CONVEYOR_RESERVED_MAX_Y
        )

    def _fail(self, message: str) -> bool:
        self.state.last_error = message
        self.state.lifter_state = LifterState.READY
        self._sync_status_symbols()
        return False
