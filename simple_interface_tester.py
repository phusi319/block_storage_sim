"""Simple interactive ADS tester for the simulator or a real PLC."""

from __future__ import annotations

import sys
from time import sleep

try:
    from py_ads_client import ADSClient, ADSSymbol, BOOL, INT, LREAL
except ModuleNotFoundError as exc:
    if exc.name != "py_ads_client":
        raise

    print("Missing dependency: py_ads_client")
    print("Run the tester with the project virtual environment:")
    print(r"  .\.venv\Scripts\python.exe .\simple_interface_tester.py")
    print("If needed, install dependencies first:")
    print(r"  .\.venv\Scripts\python.exe -m pip install -e .[dev]")
    sys.exit(1)


PLC_IP = "127.0.0.1"
PLC_NET_ID = "127.0.0.1.1.1"
PLC_PORT = 851
LOCAL_NET_ID = "127.0.0.1.1.2"

CONVEYOR_STATE = ADSSymbol("StatusVars.ConveyorState", INT)
REMOTE_SEND_PALLET = ADSSymbol("Remote.send_pallet", BOOL)
REMOTE_RELEASE_FROM_IMAGING = ADSSymbol("Remote.release_from_imaging", BOOL)
REMOTE_RETURN_PALLET = ADSSymbol("Remote.return_pallet", BOOL)
REMOTE_TRANSFER_ITEM = ADSSymbol("Remote.transfer_item", BOOL)
REMOTE_SRC_X = ADSSymbol("Remote.src_x", LREAL)
REMOTE_SRC_Y = ADSSymbol("Remote.src_y", LREAL)
REMOTE_DST_X = ADSSymbol("Remote.dst_x", LREAL)
REMOTE_DST_Y = ADSSymbol("Remote.dst_y", LREAL)


def print_state(state: int) -> None:
    match state:
        case 0:
            print("s000_initialize")
        case 1:
            print("s001_not_homed")
        case 10:
            print("s010_homing")
        case 100:
            print("s100_braking")
        case 101:
            print("s101_waiting_at_home")
        case 110:
            print("s110_moving_to_imaging")
        case 120:
            print("s120_imaging")
        case 130:
            print("s130_moving_to_slot")
        case 140:
            print("s140_waiting_in_slot")
        case 150:
            print("s150_moving_to_home")
        case _:
            print("Unknown state")


def main() -> None:
    client = ADSClient(local_ams_net_id=LOCAL_NET_ID)
    try:
        client.open(target_ip=PLC_IP, target_ams_net_id=PLC_NET_ID, target_ams_port=PLC_PORT)
        device_info = client.read_device_info()
        print(f"Connected to: {device_info.device_name} ({device_info.major_version}.{device_info.minor_version}.{device_info.build_version})")

        state_prev: int | None = None

        while True:
            print("Waiting...")
            sleep(1)
            while True:
                state = client.read_symbol(CONVEYOR_STATE)
                if state != state_prev:
                    print_state(state)
                    state_prev = state

                if state in [101, 120, 140]:
                    break

                sleep(0.2)

            print("1 - Send pallet")
            print("2 - Release pallet from imaging")
            print("3 - Return pallet")
            print("4 - Transfer item")
            print("9 - Quit")

            sel = int(input("Select: "))

            match sel:
                case 1:
                    client.write_symbol(REMOTE_SEND_PALLET, True)
                case 2:
                    client.write_symbol(REMOTE_RELEASE_FROM_IMAGING, True)
                case 3:
                    client.write_symbol(REMOTE_RETURN_PALLET, True)
                case 4:
                    src_x = float(input("Source x-coordinate: "))
                    src_y = float(input("Source y-coordinate: "))
                    dst_x = float(input("Destination x-coordinate: "))
                    dst_y = float(input("Destination y-coordinate: "))
                    client.write_symbol(REMOTE_SRC_X, src_x)
                    client.write_symbol(REMOTE_SRC_Y, src_y)
                    client.write_symbol(REMOTE_DST_X, dst_x)
                    client.write_symbol(REMOTE_DST_Y, dst_y)
                    sleep(0.1)
                    client.write_symbol(REMOTE_TRANSFER_ITEM, True)
                case 9:
                    break
                case _:
                    print("Invalid selection")

    except Exception as exc:
        print(f"Error: {exc}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
