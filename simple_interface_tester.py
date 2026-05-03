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

# --- Tier 1 additions: bulk stock area constants -----------------------------
# Storage area: x in [0, 400], y in [0, 300]. Pallet slot center: (160, 410),
# half-size 60 mm. Values come from src/block_storage_simulator/constants.py.
STORAGE_MIN_X = 0.0
STORAGE_MAX_X = 400.0
STORAGE_MIN_Y = 0.0
STORAGE_MAX_Y = 300.0
PALLET_CENTER_X = 160.0
PALLET_CENTER_Y = 410.0
PALLET_HALF_SIZE = 60.0
LOW_STOCK_THRESHOLD = 3
# -----------------------------------------------------------------------------

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


# --- Tier 1 additions: bulk stock helpers ------------------------------------
def is_storage_destination(dst_x: float, dst_y: float) -> bool:
    return STORAGE_MIN_X <= dst_x <= STORAGE_MAX_X and STORAGE_MIN_Y <= dst_y <= STORAGE_MAX_Y


def is_pallet_destination(dst_x: float, dst_y: float) -> bool:
    return (
        abs(dst_x - PALLET_CENTER_X) <= PALLET_HALF_SIZE
        and abs(dst_y - PALLET_CENTER_Y) <= PALLET_HALF_SIZE
    )


class Stock:
    """Bulk stock with EMPTY/LOW/OK state."""

    def __init__(self) -> None:
        self._count = 0

    @property
    def state(self) -> str:
        if self._count == 0:
            return "EMPTY"
        if self._count <= LOW_STOCK_THRESHOLD:
            return "LOW"
        return "OK"

    def add(self) -> None:
        self._count += 1
        print(f"Auto-track: into storage, count -> {self._count}")

    def remove(self) -> None:
        if self._count > 0:
            self._count -= 1
            print(f"Auto-track: onto pallet, count -> {self._count}")
        else:
            print("Auto-track warning: pallet destination but count is already 0")

    def show(self) -> None:
        print(f"[Stock] state={self.state}  count={self._count}  item=Block (bulk)")
# -----------------------------------------------------------------------------


# --- Tier 2 additions: FIFO batch model --------------------------------------
class BatchStock(Stock):
    """FIFO batch stock: list of slot coordinates on top of Stock."""

    def __init__(self) -> None:
        super().__init__()
        self._slots: list[tuple[float, float]] = []

    def add(self, dst_x: float, dst_y: float) -> None:
        self._slots.append((dst_x, dst_y))
        super().add()

    def remove(self) -> tuple[float, float] | None:
        if not self._slots:
            print("Stock: empty, nothing to remove")
            return None
        src = self._slots.pop(0)
        super().remove()
        return src

    def show(self) -> None:
        super().show()
        for i, (x, y) in enumerate(self._slots, 1):
            print(f"  slot {i}: ({x:.1f}, {y:.1f})")
# -----------------------------------------------------------------------------


def main() -> None:
    stock = BatchStock()  # Tier 2: FIFO batch model (OOP, extends Tier 1 Stock)
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

            # Tier 1 dashboard: show bulk stock state before the menu.
            stock.show()

            print("1 - Send pallet")
            print("2 - Release pallet from imaging")
            print("3 - Return pallet")
            print("4 - Add to storage  (pallet -> storage slot)")
            print("5 - Remove from storage  (FIFO -> pallet)")
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
                    # Add: pallet (fixed src) -> storage slot (user-chosen dst).
                    dst_x = float(input("Storage slot x-coordinate: "))
                    dst_y = float(input("Storage slot y-coordinate: "))
                    if not is_storage_destination(dst_x, dst_y):
                        print("Storage slot out of range, transfer skipped")
                        continue
                    client.write_symbol(REMOTE_SRC_X, PALLET_CENTER_X)
                    client.write_symbol(REMOTE_SRC_Y, PALLET_CENTER_Y)
                    client.write_symbol(REMOTE_DST_X, dst_x)
                    client.write_symbol(REMOTE_DST_Y, dst_y)
                    sleep(0.1)
                    client.write_symbol(REMOTE_TRANSFER_ITEM, True)
                    stock.add(dst_x, dst_y)
                case 5:
                    # Remove (FIFO): oldest storage slot -> pallet (fixed dst).
                    src = stock.remove()
                    if src is None:
                        continue
                    src_x, src_y = src
                    client.write_symbol(REMOTE_SRC_X, src_x)
                    client.write_symbol(REMOTE_SRC_Y, src_y)
                    client.write_symbol(REMOTE_DST_X, PALLET_CENTER_X)
                    client.write_symbol(REMOTE_DST_Y, PALLET_CENTER_Y)
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
