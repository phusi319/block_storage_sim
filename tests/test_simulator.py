import struct
import time

from block_storage_simulator.ads_protocol import (
    ADSCOMMAND_READ,
    ADSCOMMAND_READWRITE,
    ADSCOMMAND_WRITE,
    ADSIGRP_SYM_HNDBYNAME,
    ADSIGRP_SYM_VALBYHND,
    ADST_BIT,
    ADST_INT16,
    ADST_REAL64,
)
from block_storage_simulator.ads_server import AdsRequestHandler
from block_storage_simulator.constants import ConveyorState, TRANSFER_SLOT_CENTER_X, TRANSFER_SLOT_CENTER_Y
from block_storage_simulator.models import StackPosition, TransferCommand
from block_storage_simulator.simulator import BlockStorageSimulator
from block_storage_simulator import AdsServer
from py_ads_client import ADSClient, ADSSymbol, BOOL, INT, LREAL


def build_request(command_id: int, payload: bytes) -> bytes:
    ams_header = b"".join(
        (
            b"\x7f\x00\x00\x01\x01\x01",
            struct.pack("<H", 851),
            b"\x7f\x00\x00\x01\x01\x02",
            struct.pack("<H", 32905),
            struct.pack("<H", command_id),
            struct.pack("<H", 0x0004),
            struct.pack("<I", len(payload)),
            b"\x00" * 4,
            struct.pack("<I", 1),
            payload,
        )
    )
    return b"\x00\x00" + struct.pack("<I", len(ams_header)) + ams_header


def extract_payload(response: bytes) -> bytes:
    data = response[38:]
    assert data[:4] == b"\x00" * 4
    return data[4:]


def get_handle(handler: AdsRequestHandler, name: str) -> int:
    payload = struct.pack("<IIII", ADSIGRP_SYM_HNDBYNAME, 0, 4, len(name) + 1) + name.encode() + b"\x00"
    response = handler.handle(build_request(ADSCOMMAND_READWRITE, payload))
    result = extract_payload(response)
    length = struct.unpack("<I", result[:4])[0]
    assert length == 4
    return struct.unpack("<I", result[4:8])[0]


def write_by_handle(handler: AdsRequestHandler, handle: int, ads_type: int, value: object) -> None:
    if ads_type == ADST_BIT:
        encoded = struct.pack("<?", bool(value))
    elif ads_type == ADST_INT16:
        encoded = struct.pack("<h", int(value))
    elif ads_type == ADST_REAL64:
        encoded = struct.pack("<d", float(value))
    else:
        raise AssertionError(f"Unsupported test datatype {ads_type}")
    payload = struct.pack("<III", ADSIGRP_SYM_VALBYHND, handle, len(encoded)) + encoded
    handler.handle(build_request(ADSCOMMAND_WRITE, payload))


def read_by_handle(handler: AdsRequestHandler, handle: int, fmt: str) -> object:
    payload = struct.pack("<III", ADSIGRP_SYM_VALBYHND, handle, struct.calcsize(fmt))
    response = handler.handle(build_request(ADSCOMMAND_READ, payload))
    result = extract_payload(response)
    length = struct.unpack("<I", result[:4])[0]
    value = result[4 : 4 + length]
    return struct.unpack(fmt, value)[0]


def test_simulator_initializes_to_home_state() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.state.conveyor_state == ConveyorState.WAITING_AT_HOME


def test_send_pallet_requires_home_state() -> None:
    simulator = BlockStorageSimulator()
    simulator.state.conveyor_state = ConveyorState.IMAGING
    assert simulator.send_pallet() is False
    assert simulator.state.last_error is not None


def test_manual_pallet_editing_requires_home_state() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.add_block_to_home_pallet() is True
    assert simulator.state.pallet_relative_blocks == {StackPosition(0.0, 0.0): [1]}
    simulator.state.conveyor_state = ConveyorState.IMAGING
    assert simulator.add_block_to_home_pallet() is False
    simulator.state.conveyor_state = ConveyorState.WAITING_AT_HOME
    assert simulator.remove_block_from_home_pallet() is True


def test_transfer_requires_existing_source() -> None:
    simulator = BlockStorageSimulator()
    result = simulator.transfer_item(
        TransferCommand(src_x=10.0, src_y=10.0, dst_x=100.0, dst_y=100.0)
    )
    assert result is False
    assert simulator.state.last_error == "source point does not refer to an existing block"


def test_transfer_moves_block_from_storage_to_storage() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.add_storage_block(100.0, 100.0) is True
    result = simulator.transfer_item(
        TransferCommand(src_x=100.0, src_y=100.0, dst_x=200.0, dst_y=100.0)
    )
    assert result is True
    assert (100.0, 100.0) != (200.0, 100.0)
    assert len(simulator.state.storage_blocks) == 1


def test_offset_pick_inside_block_is_allowed_with_warning() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.add_storage_block(100.0, 100.0) is True
    result = simulator.transfer_item(
        TransferCommand(src_x=110.0, src_y=95.0, dst_x=200.0, dst_y=100.0)
    )
    assert result is True
    assert simulator.state.diagnostics[-1] == "WARNING: source pick point is offset from the block center"
    assert simulator.state.storage_blocks == {StackPosition(200.0, 100.0): [1]}


def test_block_id_is_preserved_when_block_moves() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.add_storage_block(100.0, 100.0) is True
    original_id = simulator.state.storage_blocks[StackPosition(100.0, 100.0)][0]
    assert simulator.transfer_item(
        TransferCommand(src_x=100.0, src_y=100.0, dst_x=200.0, dst_y=100.0)
    )
    assert simulator.state.storage_blocks[StackPosition(200.0, 100.0)] == [original_id]


def test_transfer_to_reserved_area_only_allowed_on_pallet() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.add_storage_block(100.0, 100.0) is True
    result = simulator.transfer_item(
        TransferCommand(src_x=100.0, src_y=100.0, dst_x=100.0, dst_y=350.0)
    )
    assert result is False


def test_transfer_to_pallet_requires_pallet_in_transfer_slot() -> None:
    simulator = BlockStorageSimulator()
    assert simulator.add_storage_block(100.0, 100.0) is True
    result = simulator.transfer_item(
        TransferCommand(
            src_x=100.0,
            src_y=100.0,
            dst_x=TRANSFER_SLOT_CENTER_X,
            dst_y=TRANSFER_SLOT_CENTER_Y,
        )
    )
    assert result is False


def test_transfer_to_pallet_succeeds_when_slot_is_active() -> None:
    simulator = BlockStorageSimulator()
    simulator.send_pallet()
    simulator.release_from_imaging()
    assert simulator.add_storage_block(100.0, 100.0) is True
    result = simulator.transfer_item(
        TransferCommand(
            src_x=100.0,
            src_y=100.0,
            dst_x=TRANSFER_SLOT_CENTER_X,
            dst_y=TRANSFER_SLOT_CENTER_Y,
        )
    )
    assert result is True
    assert simulator.state.pallet_stack_count == 1


def test_ads_command_write_triggers_and_resets_edge_command() -> None:
    simulator = BlockStorageSimulator()
    handler = AdsRequestHandler(simulator)

    handle = get_handle(handler, "Remote.send_pallet")
    write_by_handle(handler, handle, ADST_BIT, True)

    command_handle = get_handle(handler, "Remote.send_pallet")
    state_handle = get_handle(handler, "StatusVars.ConveyorState")

    assert read_by_handle(handler, command_handle, "<?") is False
    assert read_by_handle(handler, state_handle, "<h") == ConveyorState.IMAGING


def test_ads_coordinates_drive_transfer_symbol_cycle() -> None:
    simulator = BlockStorageSimulator()
    simulator.send_pallet()
    simulator.release_from_imaging()
    simulator.add_storage_block(100.0, 100.0)
    handler = AdsRequestHandler(simulator)

    write_by_handle(handler, get_handle(handler, "Remote.src_x"), ADST_REAL64, 100.0)
    write_by_handle(handler, get_handle(handler, "Remote.src_y"), ADST_REAL64, 100.0)
    write_by_handle(handler, get_handle(handler, "Remote.dst_x"), ADST_REAL64, TRANSFER_SLOT_CENTER_X)
    write_by_handle(handler, get_handle(handler, "Remote.dst_y"), ADST_REAL64, TRANSFER_SLOT_CENTER_Y)
    write_by_handle(handler, get_handle(handler, "Remote.transfer_item"), ADST_BIT, True)

    assert simulator.state.pallet_stack_count == 1
    assert simulator.state.storage_stack_count == 0


def test_py_ads_client_can_drive_local_ads_server() -> None:
    test_ip = "127.0.0.2"
    server = AdsServer(ip_address=test_ip)
    server.simulator.send_pallet()
    server.simulator.release_from_imaging()
    server.simulator.add_storage_block(100.0, 100.0)
    client = ADSClient(local_ams_net_id="127.0.0.2.1.2")

    try:
        server.start()
        time.sleep(0.05)
        client.open(target_ip=test_ip, target_ams_net_id="127.0.0.2.1.1", target_ams_port=851)

        assert client.read_symbol(ADSSymbol("StatusVars.ConveyorState", INT)) == ConveyorState.WAITING_IN_SLOT

        client.write_symbol(ADSSymbol("Remote.src_x", LREAL), 100.0)
        client.write_symbol(ADSSymbol("Remote.src_y", LREAL), 100.0)
        client.write_symbol(ADSSymbol("Remote.dst_x", LREAL), TRANSFER_SLOT_CENTER_X)
        client.write_symbol(ADSSymbol("Remote.dst_y", LREAL), TRANSFER_SLOT_CENTER_Y)
        client.write_symbol(ADSSymbol("Remote.transfer_item", BOOL), True)

        assert client.read_symbol(ADSSymbol("StatusVars.LifterState", INT)) == 0
        assert server.simulator.state.pallet_stack_count == 1
        assert server.simulator.state.storage_stack_count == 0
    finally:
        client.close()
        server.stop()
