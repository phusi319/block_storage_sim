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
