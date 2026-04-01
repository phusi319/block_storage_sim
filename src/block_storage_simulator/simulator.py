"""Core simulator behavior."""

from __future__ import annotations

from dataclasses import asdict

from .constants import (
    AREA_MAX_X,
    AREA_MAX_Y,
    AREA_MIN_X,
    AREA_MIN_Y,
    BLOCK_HALF_SIZE_MM,
    BLOCK_SIZE_MM,
    CONVEYOR_RESERVED_MAX_Y,
    CONVEYOR_RESERVED_MIN_Y,
    MAX_STACK_HEIGHT,
    PALLET_HALF_SIZE_MM,
    STORAGE_MAX_Y,
    TRANSFER_SLOT_CENTER_X,
    TRANSFER_SLOT_CENTER_Y,
    ConveyorState,
    LifterState,
)
from .models import SimulatorState, StackPosition, SymbolTable, TransferCommand


class BlockStorageSimulator:
    """Deterministic simulator core with an ADS-oriented symbol model."""

    MANUAL_PALLET_POSITION = StackPosition(0.0, 0.0)

    def __init__(self) -> None:
        self.state = SimulatorState()
        self.symbols = SymbolTable()
        self.startup()

    def startup(self) -> None:
        self.state.conveyor_state = ConveyorState.NOT_HOMED
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.HOMING
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.BRAKING
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.WAITING_AT_HOME
        self.state.last_error = None
        self._sync_status_symbols()

    def reset(self) -> None:
        self.state = SimulatorState()
        self.symbols = SymbolTable()
        self.startup()

    def add_block_to_pallet(self, x: float = 0.0, y: float = 0.0) -> bool:
        target = StackPosition(x, y)
        if not self._relative_point_on_pallet(target):
            return self._fail("pallet position is outside the pallet footprint")
        if not self._can_place_on_pallet(target):
            return self._fail("pallet placement would overlap another stack")
        return self._add_block_to_stack(self.state.pallet_relative_blocks, target)

    def clear_pallet(self) -> None:
        self.state.pallet_relative_blocks.clear()
        self.state.last_error = None
        self._sync_status_symbols()

    def can_modify_pallet_at_home(self) -> bool:
        return self.state.conveyor_state == ConveyorState.WAITING_AT_HOME

    def add_block_to_home_pallet(self) -> bool:
        if not self.can_modify_pallet_at_home():
            return self._fail("pallet can only be loaded or unloaded at home")
        return self._add_block_to_stack(self.state.pallet_relative_blocks, self.MANUAL_PALLET_POSITION)

    def remove_block_from_home_pallet(self) -> bool:
        if not self.can_modify_pallet_at_home():
            return self._fail("pallet can only be loaded or unloaded at home")
        if len(self.state.pallet_relative_blocks.get(self.MANUAL_PALLET_POSITION, [])) > 0:
            self._remove_block_from_stack(self.state.pallet_relative_blocks, self.MANUAL_PALLET_POSITION)
            self.state.last_error = None
            self._sync_status_symbols()
            return True
        return self._fail("pallet is empty")

    def add_storage_block(self, x: float, y: float) -> bool:
        target = StackPosition(x, y)
        if not self._is_valid_storage_position(target):
            return self._fail("storage position is outside the allowed storage area")
        if not self._can_place_in_storage(target):
            return self._fail("storage placement would overlap another stack")
        return self._add_block_to_stack(self.state.storage_blocks, target)

    def send_pallet(self) -> bool:
        if self.state.conveyor_state != ConveyorState.WAITING_AT_HOME:
            return self._fail("send_pallet is only valid at home")
        self.state.conveyor_state = ConveyorState.MOVING_TO_IMAGING
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.IMAGING
        self.state.last_error = None
        self._sync_status_symbols()
        return True

    def release_from_imaging(self) -> bool:
        if self.state.conveyor_state != ConveyorState.IMAGING:
            return self._fail("release_from_imaging is only valid at imaging")
        self.state.conveyor_state = ConveyorState.MOVING_TO_SLOT
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.WAITING_IN_SLOT
        self.state.last_error = None
        self._sync_status_symbols()
        return True

    def return_pallet(self) -> bool:
        if self.state.conveyor_state != ConveyorState.WAITING_IN_SLOT:
            return self._fail("return_pallet is only valid at transfer slot")
        self.state.conveyor_state = ConveyorState.MOVING_TO_HOME
        self._sync_status_symbols()
        self.state.conveyor_state = ConveyorState.WAITING_AT_HOME
        self.state.last_error = None
        self._sync_status_symbols()
        return True

    def transfer_item(self, command: TransferCommand) -> bool:
        src = StackPosition(command.src_x, command.src_y)
        dst = StackPosition(command.dst_x, command.dst_y)

        if not self._point_in_bounds(src.x, src.y):
            return self._fail("source point is outside the modeled area")
        if not self._point_in_bounds(dst.x, dst.y):
            return self._fail("destination point is outside the modeled area")

        source_info = self._locate_source(src)
        if source_info is None:
            return self._fail("source point does not refer to an existing block")

        source_stack, source_key, source_offset = source_info
        if source_offset:
            self._warn("source pick point is offset from the block center")

        destination_info = self._locate_destination(dst)
        if destination_info is None:
            return self._fail("destination is not a valid storage or pallet position")
        destination_stack, destination_key = destination_info

        if source_stack is destination_stack and source_key == destination_key:
            self.state.last_error = None
            return True

        if destination_stack is self.state.storage_blocks and not self._can_place_in_storage(
            destination_key, ignore=source_key if source_stack is destination_stack else None
        ):
            return self._fail("destination would overlap an existing storage stack")

        if destination_stack is self.state.pallet_relative_blocks and not self._can_place_on_pallet(
            destination_key, ignore=source_key if source_stack is destination_stack else None
        ):
            return self._fail("destination would overlap an existing pallet stack")

        if len(destination_stack.get(destination_key, [])) >= MAX_STACK_HEIGHT:
            return self._fail("destination stack would exceed maximum height")

        self.state.lifter_state = LifterState.BUSY
        self._sync_status_symbols()

        moved_block_id = self._remove_block_from_stack(source_stack, source_key)
        if destination_key not in destination_stack:
            destination_stack[destination_key] = []
        destination_stack[destination_key].append(moved_block_id)

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
        data["pallet_relative_blocks"] = {
            f"({key.x}, {key.y})": value[:] for key, value in self.state.pallet_relative_blocks.items()
        }
        data["storage_blocks"] = {
            f"({key.x}, {key.y})": value[:] for key, value in self.state.storage_blocks.items()
        }
        return data

    def _sync_status_symbols(self) -> None:
        self.symbols.conveyor_state = self.state.conveyor_state
        self.symbols.lifter_state = self.state.lifter_state

    def _add_block_to_stack(self, stack: dict[StackPosition, list[int]], position: StackPosition) -> bool:
        if len(stack.get(position, [])) >= MAX_STACK_HEIGHT:
            return self._fail("destination stack would exceed maximum height")
        if position not in stack:
            stack[position] = []
        stack[position].append(self.state.next_block_id)
        self.state.next_block_id += 1
        self.state.last_error = None
        self._sync_status_symbols()
        return True

    def _remove_block_from_stack(self, stack: dict[StackPosition, list[int]], position: StackPosition) -> int:
        removed_block_id = stack[position].pop()
        if not stack[position]:
            del stack[position]
        return removed_block_id

    def _locate_source(
        self, position: StackPosition
    ) -> tuple[dict[StackPosition, list[int]], StackPosition, bool] | None:
        if self._point_on_active_pallet(position):
            relative = self._to_pallet_relative(position)
            found = self._find_stack_hit(relative, self.state.pallet_relative_blocks)
            if found is not None:
                key, offset = found
                return self.state.pallet_relative_blocks, key, offset
        found = self._find_stack_hit(position, self.state.storage_blocks)
        if found is not None:
            key, offset = found
            return self.state.storage_blocks, key, offset
        return None

    def _locate_destination(
        self, position: StackPosition
    ) -> tuple[dict[StackPosition, list[int]], StackPosition] | None:
        if self._point_on_active_pallet(position):
            relative = self._to_pallet_relative(position)
            if not self._relative_point_on_pallet(relative):
                return None
            return self.state.pallet_relative_blocks, relative
        if self._is_valid_storage_position(position):
            return self.state.storage_blocks, position
        return None

    def _can_place_in_storage(
        self, position: StackPosition, ignore: StackPosition | None = None
    ) -> bool:
        return self._can_place_without_overlap(position, self.state.storage_blocks, ignore)

    def _can_place_on_pallet(
        self, position: StackPosition, ignore: StackPosition | None = None
    ) -> bool:
        return self._can_place_without_overlap(position, self.state.pallet_relative_blocks, ignore)

    def _can_place_without_overlap(
        self,
        position: StackPosition,
        stack_map: dict[StackPosition, list[int]],
        ignore: StackPosition | None = None,
    ) -> bool:
        for existing in stack_map:
            if ignore is not None and existing == ignore:
                continue
            if self._positions_overlap(position, existing):
                return existing == position
        return True

    def _positions_overlap(self, left: StackPosition, right: StackPosition) -> bool:
        return (
            abs(left.x - right.x) < BLOCK_SIZE_MM
            and abs(left.y - right.y) < BLOCK_SIZE_MM
        )

    def _find_stack_hit(
        self,
        position: StackPosition,
        stack_map: dict[StackPosition, list[int]],
    ) -> tuple[StackPosition, bool] | None:
        for existing in stack_map:
            if self._point_within_block(position, existing):
                is_offset = existing != position
                return existing, is_offset
        return None

    def _point_within_block(self, point: StackPosition, center: StackPosition) -> bool:
        return (
            abs(point.x - center.x) <= BLOCK_HALF_SIZE_MM
            and abs(point.y - center.y) <= BLOCK_HALF_SIZE_MM
        )

    def _point_on_active_pallet(self, position: StackPosition) -> bool:
        if self.state.conveyor_state != ConveyorState.WAITING_IN_SLOT:
            return False
        return (
            abs(position.x - TRANSFER_SLOT_CENTER_X) <= PALLET_HALF_SIZE_MM
            and abs(position.y - TRANSFER_SLOT_CENTER_Y) <= PALLET_HALF_SIZE_MM
        )

    def _to_pallet_relative(self, position: StackPosition) -> StackPosition:
        return StackPosition(
            round(position.x - TRANSFER_SLOT_CENTER_X, 6),
            round(position.y - TRANSFER_SLOT_CENTER_Y, 6),
        )

    def _relative_point_on_pallet(self, position: StackPosition) -> bool:
        return (
            abs(position.x) <= PALLET_HALF_SIZE_MM - BLOCK_HALF_SIZE_MM
            and abs(position.y) <= PALLET_HALF_SIZE_MM - BLOCK_HALF_SIZE_MM
        )

    def _is_valid_storage_position(self, position: StackPosition) -> bool:
        return (
            AREA_MIN_X + BLOCK_HALF_SIZE_MM <= position.x <= AREA_MAX_X - BLOCK_HALF_SIZE_MM
            and AREA_MIN_Y + BLOCK_HALF_SIZE_MM <= position.y <= STORAGE_MAX_Y - BLOCK_HALF_SIZE_MM
        )

    def _point_in_bounds(self, x: float, y: float) -> bool:
        return AREA_MIN_X <= x <= AREA_MAX_X and AREA_MIN_Y <= y <= AREA_MAX_Y

    def _is_reserved_area(self, x: float, y: float) -> bool:
        return CONVEYOR_RESERVED_MIN_Y <= y <= CONVEYOR_RESERVED_MAX_Y

    def _fail(self, message: str) -> bool:
        self.state.last_error = message
        self.state.diagnostics.append(f"ALARM: {message}")
        self.state.lifter_state = LifterState.READY
        self._sync_status_symbols()
        return False

    def _warn(self, message: str) -> None:
        self.state.diagnostics.append(f"WARNING: {message}")
