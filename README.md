# Block Storage Simulator

Python project scaffold for a student-facing block storage simulator.

The current project includes:

- a simulator core for conveyor and lifter behavior,
- a simple Tkinter GUI for manual testing,
- an ADS-oriented symbol model matching the current spec,
- a package layout ready for later ADS integration work.

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

## Current Status

This first scaffold focuses on:

- clean project structure,
- deterministic simulator state transitions,
- a lightweight manual test GUI.

The actual ADS server binding is not implemented yet. The included `simple_interface_tester.py` remains the compatibility target for a later ADS adapter.
