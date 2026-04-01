from block_storage_simulator.constants import ConveyorState
from block_storage_simulator.models import TransferCommand
from block_storage_simulator.simulator import BlockStorageSimulator


def test_startup_reaches_home_state() -> None:
    simulator = BlockStorageSimulator()
    simulator.startup()
    assert simulator.state.conveyor_state == ConveyorState.WAITING_AT_HOME


def test_send_pallet_requires_home_state() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.send_pallet() is False
    assert simulator.state.last_error is not None


def test_transfer_rejects_reserved_area_destination() -> None:
    simulator = BlockStorageSimulator()
    result = simulator.transfer_item(
        TransferCommand(src_x=10.0, src_y=10.0, dst_x=100.0, dst_y=350.0)
    )
    assert result is False


def test_valid_transfer_creates_stack_entry() -> None:
    simulator = BlockStorageSimulator()
    result = simulator.transfer_item(
        TransferCommand(src_x=10.0, src_y=10.0, dst_x=100.0, dst_y=100.0)
    )
    assert result is True
    assert simulator.state.blocks_by_center[(100.0, 100.0)] == 1
