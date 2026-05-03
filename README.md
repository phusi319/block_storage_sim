# Block Storage Simulator

Python project scaffold for a student-facing block storage simulator.

The current project includes:

- a simulator core for conveyor and lifter behavior,
- a simple Tkinter GUI for manual testing,
- an ADS-oriented symbol model matching the current spec,
- a local ADS TCP server exposing the `Remote.*` and `StatusVars.*` symbol surface.

## Quick Start

Create a virtual environment and install the project:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Run the simulator GUI:

```powershell
block-storage-sim
```

Run the ADS server only:

```powershell
block-storage-sim --mode ads
```

Run both the GUI and ADS server:

```powershell
block-storage-sim --mode both
```

Run the Tier 1 bulk stock app (CLI):

```powershell
.\.venv\Scripts\python.exe .\simple_interface_tester.py
```

Tier 1 adds bulk stock tracking on top of the teacher's reference
tester (`simple_interface_tester.py`):

- storage/pallet area constants and a low-stock threshold,
- `is_storage_destination(...)` and `is_pallet_destination(...)` helpers
  that classify a transfer destination,
- a `Stock` class encapsulating the bulk count and the
  EMPTY / LOW / OK state (`Stock.add()`, `Stock.remove()`,
  `Stock.show()`, `Stock.state`),
- a stock dashboard line printed before the menu (`stock.show()`),
- an auto-track block inside transfer case 4 that calls `stock.add()`
  or `stock.remove()` based on the destination of the transfer.

The original 5-item menu (1 Send pallet / 2 Release / 3 Return /
4 Transfer / 9 Quit), the conveyor poll loop, and the ADS symbol
layout are unchanged.

## ADS Smoke Test

The simulator ADS server binds to `127.0.0.1:48898` by default and exposes these symbols:

- `StatusVars.ConveyorState`
- `StatusVars.LifterState`
- `Remote.send_pallet`
- `Remote.release_from_imaging`
- `Remote.return_pallet`
- `Remote.transfer_item`
- `Remote.src_x`
- `Remote.src_y`
- `Remote.dst_x`
- `Remote.dst_y`

For `simple_interface_tester.py`, use local connection parameters such as:

```python
PLC_IP = "127.0.0.1"
PLC_NET_ID = "127.0.0.1.1.1"
PLC_PORT = 851
LOCAL_NET_ID = "127.0.0.1.1.2"
```

The included tester now uses the pure-Python `py-ads-client` package, so simulation mode does not require the Beckhoff runtime or TwinCAT on the same machine.

For a simulator-only local workflow:

1. Start the simulator ADS server with `block-storage-sim --mode ads` or `block-storage-sim --mode both`.
2. Run `.\.venv\Scripts\python.exe .\simple_interface_tester.py`.
3. The tester will connect to `127.0.0.1:48898` using ADS over TCP.

For a real Beckhoff PLC later, keep the same ADS command flow and symbol names, then replace the IP and AMS Net IDs with the real target values.

## Current Status

The current implementation focuses on:

- deterministic conveyor state transitions,
- transfer validation for storage and pallet positions,
- edge-triggered remote commands,
- a lightweight GUI and a local ADS-compatible server for student testing.
