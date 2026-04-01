# Block Storage Simulator Specification

## 1. Purpose

This project provides a block storage simulator for students developing block storage manager software in Python.

Students should be able to:

- Connect their Python application to the simulator using the same communication protocol as the real device.
- Develop and test their storage manager logic before using the physical block storage system.
- Validate command sequencing, device-state handling, and storage placement rules in a deterministic environment.

The long-term goal is that software that works correctly with the simulator should require minimal changes when moved to the real device.

## 2. Communication Interface

### 2.1 Protocol Choice

The simulator should use Beckhoff ADS as its primary external interface.

Using ADS for both:

- the simulator, and
- the student-developed Python application

is acceptable and preferred for simplicity, because it keeps the simulator close to the real device interface.

Python applications are expected to communicate with the simulator using ADS from Python.

The file `simple_interface_tester.py` in this repository is a known-working reference client for the simulator-side ADS interface and should remain close to the interaction pattern used later against the real device.

Simulation mode should not require TwinCAT or the Beckhoff ADS runtime on the same machine.

### 2.2 Design Intent

The simulator should present an ADS-facing variable interface that mimics the real system as closely as practical for student use.

This means the simulator should expose:

- remote command variables,
- coordinate variables, and
- status variables

through ADS symbols or an equivalent ADS-backed variable model.

The ADS interface should remain deliberately minimal and match the real device behavior as closely as practical.

## 3. System Overview

The device has two main modules:

1. A conveyor module that moves pallets between fixed stations.
2. A lifter module that picks and places blocks within the transfer area.

The simulator should model both modules at a behavioral level sufficient for students to develop and test their control software.

At any given time, there is only one pallet in the system.

The simulator may maintain internal block positions for its own logic and GUI, but it must not expose block locations through ADS. The student application is responsible for tracking block locations.

The GUI is not the student control application. It is a local observer tool for the backend simulator state.

For visualization, each simulated block may have a unique internal identifier. These identifiers are for GUI observation only and are not part of the ADS interface.

## 4. Conveyor Module

### 4.1 Conveyor Topology

The conveyor is oval shaped and moves in only one direction.

It has three stopping stations:

1. Home slot
2. Imaging slot
3. Transfer slot

Commands do not send the pallet to an arbitrary station. Instead, each conveyor command advances the pallet to the next relevant station in the cycle.

### 4.2 Station Meanings

#### Home Slot

The home slot corresponds to conveyor state `101` (`s101_waiting_at_home`).

This is the station where:

- blocks enter the system, or
- blocks exit the system.

At the home slot, blocks may be placed on the pallet or removed from the pallet.

For the simulator GUI tool, manual add/remove at the home slot operates on the pallet center position.

#### Imaging Slot

The imaging slot corresponds to conveyor state `120` (`s120_imaging`).

At the moment, the imaging slot performs no active operation, but the pallet still stops there on every cycle.

#### Transfer Slot

The transfer slot corresponds to conveyor state `140` (`s140_waiting_in_slot`).

This slot is inside the transfer area and is accessible by the lifter.

The center point of the conveyor transfer slot is:

- `(160, 410)` in millimeters

## 5. Lifter Module

### 5.1 Lifter Capability

The lifter can freely roam inside the transfer area, subject to area occupancy and stack-height constraints defined in this specification.

The lifter is responsible for transferring blocks between:

- the pallet position in the transfer slot, and
- storage positions inside the allowed storage area.

### 5.2 Transfer Coordinates

The `transfer_item` command uses source and destination coordinates.

Coordinates are expressed in millimeters.

The simulator should interpret these coordinates in the same global coordinate system used to describe the transfer area.

The coordinates represent item center points.

For placements, the destination coordinates must identify the intended block center position.

For picks, the source coordinates may be anywhere inside the footprint of the source block. If the source point is not exactly at the block center but still lies within the block footprint, the pick is accepted and recorded as a warning.

## 6. Physical Area Model

### 6.1 Global Bounds

The whole modeled area is:

- from `(0, 0)` to `(400, 430)` millimeters

The coordinate system is defined with the origin at the top-right corner of the modeled area.

- `x` increases when moving left
- `y` increases when moving down

### 6.2 Conveyor-Reserved Area

The conveyor reserves the rectangular area:

- from `(0, 300)` to `(400, 430)` millimeters

It is possible to move a block over this area during a transfer.

However, placing a block in the conveyor-reserved area is considered an error, except when placing to the pallet if the pallet is present in the transfer slot.

### 6.3 Storage Area

The remaining area outside the conveyor-reserved region is used for block storage.

This means the primary storage area is effectively:

- from `(0, 0)` to `(400, 300)` millimeters

subject to the block size and placement rules in this spec.

## 7. Item Geometry and Placement Rules

### 7.1 Dimensions

The simulator should model the following object sizes:

- Block size: `60 mm x 60 mm`
- Pallet size: `120 mm x 120 mm`

### 7.2 Pallet Presence

There is only one pallet in the system at a time.

When the pallet is present in the transfer slot, placements onto the pallet are valid even though that pallet lies inside the conveyor-reserved area.

When a block is manually loaded onto the pallet through the GUI tool, the block center is placed at the pallet center.

### 7.3 Stack Height Rules

Blocks can be stacked with the following rules:

- Stack height of 1 block is valid.
- Stack height of 2 blocks is valid.
- Stack height of 3 or more blocks is considered an error.

The reason for this rule is that while a third block can physically be stacked, the lifter cannot pass such a stack when carrying a block. For the simulator, stacks taller than 2 should therefore be treated as invalid placements.

## 8. Remote Command Interface

### 8.1 Commands

The following remote commands are defined by the current interface.

| Command | Type | Meaning | Acceptance rule |
| --- | --- | --- | --- |
| `Remote.send_pallet` | `BOOL` | Sends the pallet from the home slot to the imaging slot. | Accepted only in conveyor state `s101_waiting_at_home`. |
| `Remote.release_from_imaging` | `BOOL` | Releases the pallet from the imaging slot to the transfer slot. | Accepted only in conveyor state `s120_imaging`. |
| `Remote.return_pallet` | `BOOL` | Returns the pallet from the transfer slot to the home slot. | Accepted only in conveyor state `s140_waiting_in_slot`. |
| `Remote.transfer_item` | `BOOL` | Transfers one block from source (`src`) to destination (`dst`) using the lifter. | Can be sent at any time, subject to transfer validity checks. |

### 8.2 Coordinate Variables

The following coordinate variables are used by `Remote.transfer_item`.

| Variable | Type | Meaning |
| --- | --- | --- |
| `Remote.src_x` | `float` / `LREAL` | Source X coordinate in millimeters. |
| `Remote.src_y` | `float` / `LREAL` | Source Y coordinate in millimeters. |
| `Remote.dst_x` | `float` / `LREAL` | Destination X coordinate in millimeters. |
| `Remote.dst_y` | `float` / `LREAL` | Destination Y coordinate in millimeters. |

### 8.3 Command Triggering

All ADS commands are edge-triggered.

The expected command cycle is:

1. The student application sets a command variable through ADS.
2. The simulator reads the command.
3. The simulator resets the command variable after it has been read.

This behavior should mimic the real device pattern.

### 8.4 Confirmed ADS Symbol Surface

Based on `simple_interface_tester.py`, the simulator should support at least the following ADS symbols and data types:

| Symbol | Type |
| --- | --- |
| `StatusVars.ConveyorState` | `INT` |
| `StatusVars.LifterState` | `INT` |
| `Remote.send_pallet` | `BOOL` |
| `Remote.release_from_imaging` | `BOOL` |
| `Remote.return_pallet` | `BOOL` |
| `Remote.transfer_item` | `BOOL` |
| `Remote.src_x` | `LREAL` |
| `Remote.src_y` | `LREAL` |
| `Remote.dst_x` | `LREAL` |
| `Remote.dst_y` | `LREAL` |

The simulator does not need to expose internal block-location variables through ADS.

## 9. Status Interface

### 9.1 Conveyor State Variable

The simulator must expose `StatusVars.ConveyorState` as an `INT`.

The following values are currently defined:

| Value | Name | Notes |
| --- | --- | --- |
| `0` | `s000_initialize` | Initialization state. |
| `1` | `s001_not_homed` | System not homed. |
| `10` | `s010_homing` | Homing in progress. |
| `100` | `s100_braking` | Braking state. |
| `101` | `s101_waiting_at_home` | Home slot. Only state where `send_pallet` is accepted. |
| `110` | `s110_moving_to_imaging` | Conveyor moving toward imaging slot. |
| `120` | `s120_imaging` | Imaging slot. Only state where `release_from_imaging` is accepted. |
| `130` | `s130_moving_to_slot` | Conveyor moving toward transfer slot. |
| `140` | `s140_waiting_in_slot` | Transfer slot. Only state where `return_pallet` is accepted. |
| `150` | `s150_moving_to_home` | Conveyor moving toward home slot. |

### 9.2 Lifter State Variable

The simulator should expose `StatusVars.LifterState`.

The full real state definition is not yet available, so the simulator should use placeholder states for now:

| Value | Name | Notes |
| --- | --- | --- |
| `0` | `ready` | Lifter is idle and available. |
| `1` | `busy` | Lifter is executing a transfer. |

This section should be updated later when the real lifter states are available.

## 10. Conveyor State Flow

The conveyor follows this high-level state sequence:

1. `s000_initialize`
2. `s001_not_homed`
3. `s010_homing`
4. `s100_braking`
5. `s101_waiting_at_home`
6. `s110_moving_to_imaging`
7. `s120_imaging`
8. `s130_moving_to_slot`
9. `s140_waiting_in_slot`
10. `s150_moving_to_home`
11. Back to `s101_waiting_at_home`

The current command-to-state relationships are:

- Initialization enters the startup path automatically without a separate client command.
- `Remote.send_pallet` advances the pallet from home toward imaging.
- `Remote.release_from_imaging` advances the pallet from imaging toward the transfer slot.
- `Remote.return_pallet` advances the pallet from the transfer slot back toward home.

The pallet stops at the imaging slot on every cycle, even though imaging currently has no active behavior.

## 11. Transfer Rules

The simulator should validate `Remote.transfer_item` requests against the physical model.

The source and destination coordinates refer to block center points.

At minimum, a transfer should be considered invalid if:

- the source coordinate does not refer to a valid block location,
- the destination coordinate is outside the modeled area,
- the destination would place a block in the conveyor-reserved area and not on the pallet,
- the destination would create a stack taller than 2 blocks,
- the transfer would otherwise violate the modeled occupancy rules.

The simulator may allow transfers to be commanded at any time, but the result of the transfer must still be validated against geometry and placement constraints.

If the source point lies inside the source block but not exactly at its center, the transfer should still be accepted, but the simulator should record a warning.

## 12. Simulator Requirements

The simulator should:

- expose the ADS variable interface described in this specification,
- allow Python student applications to connect through an ADS-capable Python client,
- keep the ADS interface minimal and close to the real device,
- avoid exposing block locations through ADS,
- enforce conveyor command acceptance rules based on conveyor state,
- simulate conveyor state transitions through the three stations,
- simulate lifter transfers using the shared coordinate system,
- enforce area, occupancy, and stack-height rules,
- allow students to test both valid and invalid command timing,
- provide deterministic behavior by default so student software is easy to debug.

The simulator should also be usable with the included `simple_interface_tester.py` after only small changes to ADS connection parameters such as AMS Net ID and port.

### 12.1 GUI Role

The GUI is a backend visualization and reset tool.

The GUI should:

- show the current pallet position,
- visualize stored blocks and stack heights,
- show the center coordinates of visible blocks,
- show a unique identifier for each visible block,
- show the pallet center coordinates,
- show the current backend status values,
- show accumulated warnings and alarms,
- provide a reset action for starting over,
- allow adding a block to the pallet only when the pallet is at the home slot,
- allow removing a block from the pallet only when the pallet is at the home slot.

The GUI should not:

- send conveyor commands,
- send lifter transfer commands,
- act as an alternative student client.

The home slot and imaging slot visualizations should be shown outside the modeled transfer area view. The transfer slot should be shown inside the transfer area view at `(160, 410)`.
Coordinates should be shown for objects inside the transfer area view, but not for objects outside the transfer area view.

The transfer area visualization should preserve the modeled area proportions. The GUI should not compress the transfer area width in a way that distorts the geometry.

Students are expected to create the client application that drives the conveyor and lifter through ADS. The included `simple_interface_tester.py` is only a basic reference client for smoke testing.

## 13. Recommended Non-Functional Behavior

To support teaching and testing, the simulator should eventually support:

- resetting the simulator to a known initial state,
- configurable timing for state transitions,
- logging of received commands, rejected commands, transfers, and state changes,
- accumulation of warnings and alarms for later inspection,
- simple local startup for students on their own machines,
- a very simple GUI for backend observation,
- a GUI that is easy to understand, easy to use, and easy to start,
- optional visualization of pallet position, block positions, and stack heights.

These items are recommended design goals for the simulator project.

## 14. Reference Client Behavior

The file `simple_interface_tester.py` shows the expected client interaction pattern:

- connect to ADS with a Python ADS client,
- read `StatusVars.ConveyorState` repeatedly,
- wait until the conveyor reaches one of the command-accepting states `101`, `120`, or `140`,
- write command booleans to `Remote.*`,
- for `Remote.transfer_item`, write the four coordinate values first and then trigger the command,
- use `LREAL` for coordinates and `BOOL` for commands.

This script should be treated as an early smoke test for simulator compatibility.

## 15. Open Questions

The following details are still not fully defined and should be clarified before implementation is finalized:

- What exact response should occur when a command is issued in the wrong state?
- Should invalid transfers raise an explicit error status, be rejected silently, or set a diagnostic variable?
- How should collision and path-blocking behavior be modeled for the lifter beyond the stack-height rule?
- Does the real system expose additional lifter status variables, error codes, or acknowledgements?
- What timing behavior should be simulated for conveyor motion and transfer operations?

## 16. Source

This draft is based on:

- the PowerPoint `Storage Command structure.pptx`, and
- the additional system description provided in this conversation on 2026-04-01,
- the file `simple_interface_tester.py`.
