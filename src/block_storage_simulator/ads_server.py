"""Local ADS-facing server for the simulator."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import socket
import struct
import threading
from typing import Any

from .ads_protocol import (
    ADS_TCP_PORT,
    ADSCOMMAND_READ,
    ADSCOMMAND_READDEVICEINFO,
    ADSCOMMAND_READSTATE,
    ADSCOMMAND_READWRITE,
    ADSCOMMAND_WRITE,
    ADSCOMMAND_WRITECTRL,
    ADSIGRP_SYM_HNDBYNAME,
    ADSIGRP_SYM_INFOBYNAMEEX,
    ADSIGRP_SYM_RELEASEHND,
    ADSIGRP_SYM_UPLOAD,
    ADSIGRP_SYM_UPLOADINFO2,
    ADSIGRP_SYM_VALBYHND,
    ADSSTATE_RUN,
    ADST_BIT,
    ADST_INT16,
    ADST_REAL64,
    build_response,
    parse_packet,
)
from .simulator import BlockStorageSimulator

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AdsSymbol:
    name: str
    ads_type: int
    symbol_type: str
    handle: int
    index_group: int
    index_offset: int
    value: bytes
    comment: str = ""

    @property
    def size(self) -> int:
        return len(self.value)

    def packed_info(self) -> bytes:
        name_bytes = self.name.encode("utf-8")
        type_bytes = self.symbol_type.encode("utf-8")
        comment_bytes = self.comment.encode("utf-8")
        entry_length = (
            6 * 4
            + 3 * 2
            + len(name_bytes)
            + 1
            + len(type_bytes)
            + 1
            + len(comment_bytes)
        )
        return (
            struct.pack(
                "<IIIIIIHHH",
                entry_length,
                self.index_group,
                self.index_offset,
                self.size,
                self.ads_type,
                0,
                len(name_bytes),
                len(type_bytes),
                len(comment_bytes),
            )
            + name_bytes
            + b"\x00"
            + type_bytes
            + b"\x00"
            + comment_bytes
        )


class AdsSymbolTable:
    """Maps the simulator state onto ADS symbol names and binary values."""

    SYMBOL_INDEX_GROUP = 0xF005
    SYMBOL_INDEX_OFFSET_BASE = 10_000
    HANDLE_BASE = 20_000

    def __init__(self, simulator: BlockStorageSimulator) -> None:
        self.simulator = simulator
        self._symbols_by_name: dict[str, AdsSymbol] = {}
        self._symbols_by_handle: dict[int, AdsSymbol] = {}
        self._next_handle = self.HANDLE_BASE
        self._register_symbols()
        self.refresh_status_symbols()

    def refresh_status_symbols(self) -> None:
        self._set_python_value("StatusVars.ConveyorState", int(self.simulator.state.conveyor_state))
        self._set_python_value("StatusVars.LifterState", int(self.simulator.state.lifter_state))

    def read_by_name(self, name: str) -> bytes:
        self.refresh_status_symbols()
        return self._symbols_by_name[name].value

    def read_by_handle(self, handle: int) -> bytes:
        self.refresh_status_symbols()
        return self._symbols_by_handle[handle].value

    def write_by_name(self, name: str, value: bytes) -> None:
        symbol = self._symbols_by_name[name]
        self._write_symbol(symbol, value)

    def write_by_handle(self, handle: int, value: bytes) -> None:
        symbol = self._symbols_by_handle[handle]
        self._write_symbol(symbol, value)

    def get_by_name(self, name: str) -> AdsSymbol:
        return self._symbols_by_name[name]

    def all_symbols(self) -> list[AdsSymbol]:
        return list(self._symbols_by_name.values())

    def _register_symbols(self) -> None:
        self._add_symbol("StatusVars.ConveyorState", ADST_INT16, "INT", 0)
        self._add_symbol("StatusVars.LifterState", ADST_INT16, "INT", 0)
        self._add_symbol("Remote.send_pallet", ADST_BIT, "BOOL", False)
        self._add_symbol("Remote.release_from_imaging", ADST_BIT, "BOOL", False)
        self._add_symbol("Remote.return_pallet", ADST_BIT, "BOOL", False)
        self._add_symbol("Remote.transfer_item", ADST_BIT, "BOOL", False)
        self._add_symbol("Remote.src_x", ADST_REAL64, "LREAL", 0.0)
        self._add_symbol("Remote.src_y", ADST_REAL64, "LREAL", 0.0)
        self._add_symbol("Remote.dst_x", ADST_REAL64, "LREAL", 0.0)
        self._add_symbol("Remote.dst_y", ADST_REAL64, "LREAL", 0.0)

    def _add_symbol(self, name: str, ads_type: int, symbol_type: str, initial_value: Any) -> None:
        handle = self._next_handle
        self._next_handle += 1
        index_offset = self.SYMBOL_INDEX_OFFSET_BASE + handle
        symbol = AdsSymbol(
            name=name,
            ads_type=ads_type,
            symbol_type=symbol_type,
            handle=handle,
            index_group=self.SYMBOL_INDEX_GROUP,
            index_offset=index_offset,
            value=self._pack_value(ads_type, initial_value),
        )
        self._symbols_by_name[name] = symbol
        self._symbols_by_handle[handle] = symbol

    def _set_python_value(self, name: str, value: Any) -> None:
        symbol = self._symbols_by_name[name]
        symbol.value = self._pack_value(symbol.ads_type, value)

    def _write_symbol(self, symbol: AdsSymbol, value: bytes) -> None:
        symbol.value = value
        if symbol.name == "Remote.send_pallet":
            self.simulator.symbols.remote_send_pallet = self._unpack_bool(value)
        elif symbol.name == "Remote.release_from_imaging":
            self.simulator.symbols.remote_release_from_imaging = self._unpack_bool(value)
        elif symbol.name == "Remote.return_pallet":
            self.simulator.symbols.remote_return_pallet = self._unpack_bool(value)
        elif symbol.name == "Remote.transfer_item":
            self.simulator.symbols.remote_transfer_item = self._unpack_bool(value)
        elif symbol.name == "Remote.src_x":
            self.simulator.symbols.remote_src_x = self._unpack_lreal(value)
        elif symbol.name == "Remote.src_y":
            self.simulator.symbols.remote_src_y = self._unpack_lreal(value)
        elif symbol.name == "Remote.dst_x":
            self.simulator.symbols.remote_dst_x = self._unpack_lreal(value)
        elif symbol.name == "Remote.dst_y":
            self.simulator.symbols.remote_dst_y = self._unpack_lreal(value)

        command_was_triggered = symbol.name.startswith("Remote.") and symbol.ads_type == ADST_BIT and self._unpack_bool(value)
        if command_was_triggered:
            self.simulator.consume_edge_triggered_commands()
            self._reset_remote_commands()

        self.refresh_status_symbols()

    def _reset_remote_commands(self) -> None:
        command_names = (
            "Remote.send_pallet",
            "Remote.release_from_imaging",
            "Remote.return_pallet",
            "Remote.transfer_item",
        )
        for name in command_names:
            self._symbols_by_name[name].value = self._pack_value(ADST_BIT, False)

    def _pack_value(self, ads_type: int, value: Any) -> bytes:
        if ads_type == ADST_BIT:
            return struct.pack("<?", bool(value))
        if ads_type == ADST_INT16:
            return struct.pack("<h", int(value))
        if ads_type == ADST_REAL64:
            return struct.pack("<d", float(value))
        raise ValueError(f"Unsupported ADS type: {ads_type}")

    def _unpack_bool(self, value: bytes) -> bool:
        return struct.unpack("<?", value[:1])[0]

    def _unpack_lreal(self, value: bytes) -> float:
        return struct.unpack("<d", value[:8])[0]


class AdsRequestHandler:
    """Handles the subset of ADS commands needed by the student-facing spec."""

    def __init__(self, simulator: BlockStorageSimulator) -> None:
        self.simulator = simulator
        self.symbols = AdsSymbolTable(simulator)

    def handle(self, raw_packet: bytes) -> bytes:
        request = parse_packet(raw_packet)
        payload = self._dispatch(request)
        return build_response(request, payload)

    def _dispatch(self, request: Any) -> bytes:
        if request.command_id == ADSCOMMAND_READDEVICEINFO:
            return b"\x01\x00\x00\x00BlockStorageSim\x00"
        if request.command_id == ADSCOMMAND_READSTATE:
            return struct.pack("<HH", ADSSTATE_RUN, 0)
        if request.command_id == ADSCOMMAND_WRITECTRL:
            return b""
        if request.command_id == ADSCOMMAND_READ:
            return self._handle_read(request.data)
        if request.command_id == ADSCOMMAND_WRITE:
            return self._handle_write(request.data)
        if request.command_id == ADSCOMMAND_READWRITE:
            return self._handle_read_write(request.data)
        raise ValueError(f"Unsupported ADS command {request.command_id}")

    def _handle_read(self, data: bytes) -> bytes:
        index_group, index_offset, length = struct.unpack("<III", data[:12])
        if index_group == ADSIGRP_SYM_VALBYHND:
            value = self.symbols.read_by_handle(index_offset)
        elif index_group == ADSIGRP_SYM_UPLOADINFO2:
            symbols = self.symbols.all_symbols()
            response_length = sum(len(symbol.packed_info()) for symbol in symbols)
            value = struct.pack("<II", len(symbols), response_length)
        elif index_group == ADSIGRP_SYM_UPLOAD:
            value = b"".join(symbol.packed_info() for symbol in self.symbols.all_symbols())
        else:
            symbol = self._symbol_by_indices(index_group, index_offset)
            value = symbol.value[:length]
        return struct.pack("<I", len(value)) + value

    def _handle_write(self, data: bytes) -> bytes:
        index_group, index_offset, length = struct.unpack("<III", data[:12])
        value = data[12 : 12 + length]
        if index_group == ADSIGRP_SYM_RELEASEHND:
            return b""
        if index_group == ADSIGRP_SYM_VALBYHND:
            self.symbols.write_by_handle(index_offset, value)
            return b""
        symbol = self._symbol_by_indices(index_group, index_offset)
        self.symbols.write_by_name(symbol.name, value)
        return b""

    def _handle_read_write(self, data: bytes) -> bytes:
        index_group, index_offset, read_length, write_length = struct.unpack("<IIII", data[:16])
        write_data = data[16 : 16 + write_length]
        if index_group == ADSIGRP_SYM_HNDBYNAME:
            name = write_data.rstrip(b"\x00").decode("utf-8")
            symbol = self.symbols.get_by_name(name)
            value = struct.pack("<I", symbol.handle)
            return struct.pack("<I", len(value)) + value
        if index_group == ADSIGRP_SYM_INFOBYNAMEEX:
            name = write_data.rstrip(b"\x00").decode("utf-8")
            symbol = self.symbols.get_by_name(name)
            info = symbol.packed_info()
            return struct.pack("<I", len(info)) + info

        symbol = self._symbol_by_indices(index_group, index_offset)
        current_value = symbol.value[:read_length]
        self.symbols.write_by_name(symbol.name, write_data)
        return struct.pack("<I", len(current_value)) + current_value

    def _symbol_by_indices(self, index_group: int, index_offset: int) -> AdsSymbol:
        for symbol in self.symbols.all_symbols():
            if symbol.index_group == index_group and symbol.index_offset == index_offset:
                return symbol
        raise KeyError(f"Unknown symbol indices ({index_group}, {index_offset})")


class AdsServer:
    """Tiny ADS TCP server that exposes the simulator symbol surface."""

    def __init__(
        self,
        simulator: BlockStorageSimulator | None = None,
        ip_address: str = "127.0.0.1",
        port: int = ADS_TCP_PORT,
    ) -> None:
        self.simulator = simulator or BlockStorageSimulator()
        self.handler = AdsRequestHandler(self.simulator)
        self.ip_address = ip_address
        self.port = port
        self._server: socket.socket | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.ip_address, self.port))
        self._server.listen(5)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        LOGGER.info("ADS server listening on %s:%s", self.ip_address, self.port)

    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def __enter__(self) -> "AdsServer":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop_event.is_set():
            try:
                client, _ = self._server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _handle_client(self, client: socket.socket) -> None:
        with client:
            while not self._stop_event.is_set():
                try:
                    header = self._recv_exact(client, 6)
                except ConnectionError:
                    break
                packet_length = struct.unpack("<I", header[2:6])[0]
                try:
                    payload = self._recv_exact(client, packet_length)
                except ConnectionError:
                    break
                response = self.handler.handle(header + payload)
                client.sendall(response)

    def _recv_exact(self, client: socket.socket, expected: int) -> bytes:
        buffer = bytearray()
        while len(buffer) < expected:
            chunk = client.recv(expected - len(buffer))
            if not chunk:
                raise ConnectionError("Client disconnected")
            buffer.extend(chunk)
        return bytes(buffer)
