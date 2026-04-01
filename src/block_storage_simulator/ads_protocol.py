"""Minimal ADS protocol helpers used by the local simulator server."""

from __future__ import annotations

from dataclasses import dataclass
import struct


ADS_TCP_PORT = 48898
ADSSTATE_RUN = 5

ADSCOMMAND_READDEVICEINFO = 0x01
ADSCOMMAND_READ = 0x02
ADSCOMMAND_WRITE = 0x03
ADSCOMMAND_READSTATE = 0x04
ADSCOMMAND_WRITECTRL = 0x05
ADSCOMMAND_READWRITE = 0x09

ADSIGRP_SYM_HNDBYNAME = 0xF003
ADSIGRP_SYM_VALBYHND = 0xF005
ADSIGRP_SYM_RELEASEHND = 0xF006
ADSIGRP_SYM_INFOBYNAMEEX = 0xF009
ADSIGRP_SYM_UPLOAD = 0xF00B
ADSIGRP_SYM_UPLOADINFO2 = 0xF00F

ADST_INT16 = 2
ADST_REAL64 = 5
ADST_BIT = 33


@dataclass(frozen=True, slots=True)
class AmsPacket:
    target_net_id: bytes
    target_port: bytes
    source_net_id: bytes
    source_port: bytes
    command_id: int
    state_flags: int
    error_code: bytes
    invoke_id: bytes
    data: bytes


def parse_packet(data: bytes) -> AmsPacket:
    return AmsPacket(
        target_net_id=data[6:12],
        target_port=data[12:14],
        source_net_id=data[14:20],
        source_port=data[20:22],
        command_id=struct.unpack("<H", data[22:24])[0],
        state_flags=struct.unpack("<H", data[24:26])[0],
        error_code=data[30:34],
        invoke_id=data[34:38],
        data=data[38:],
    )


def build_response(request: AmsPacket, payload: bytes, error_code: bytes = b"\x00" * 4) -> bytes:
    state_flags = struct.pack("<H", request.state_flags | 0x0001)
    response_payload = error_code + payload
    ams_header = b"".join(
        (
            request.source_net_id,
            request.source_port,
            request.target_net_id,
            request.target_port,
            struct.pack("<H", request.command_id),
            state_flags,
            struct.pack("<I", len(response_payload)),
            error_code,
            request.invoke_id,
            response_payload,
        )
    )
    tcp_header = b"\x00\x00" + struct.pack("<I", len(ams_header))
    return tcp_header + ams_header
