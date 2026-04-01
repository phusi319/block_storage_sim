import pyads
from time import sleep

# 1. Define Connection Parameters
# Replace with your PLC's actual AMS NetID
PLC_NET_ID = '5.46.196.64.1.1' 
PLC_PORT = pyads.PORT_TC3PLC1  # Constant for 851

def print_state(state):

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

def main():
    # 2. Establish Connection
    # The 'with' statement ensures the connection is closed automatically
    try:
        with pyads.Connection(PLC_NET_ID, PLC_PORT) as plc:
            print(f"Connecting to PLC at {PLC_NET_ID}...")
            
            # Check if the PLC is actually reachable
            if plc.is_open:

                # 3. Read Device Info
                device_name, version = plc.read_device_info()
                print(f"Connected to: {device_name} (Version: {version})")

                state_prev = 0

                while True:


                    print("Waiting...")
                    sleep(1)
                    while True:
                        state = plc.read_by_name("StatusVars.ConveyorState", pyads.PLCTYPE_INT)
                        if state != state_prev:
                            print_state(state)
                        state_prev = state

                        if state in [101, 120, 140]:
                            break   
                    
                    print("1 - Send pallet")
                    print("2 - Release pallet from imaging")
                    print("3 - Return pallet")
                    print("4 - Transfer item")
                    print("9 - Quit")

                    sel = int(input("Select: "))

                    match sel:
                        case 1:
                            plc.write_by_name("Remote.send_pallet", True, pyads.PLCTYPE_BOOL)

                        case 2:
                            plc.write_by_name("Remote.release_from_imaging", True, pyads.PLCTYPE_BOOL)

                        case 3:
                            plc.write_by_name("Remote.return_pallet", True, pyads.PLCTYPE_BOOL)

                        case 4:
                            src_x = float(input("Source x-coordinate: "))
                            src_y = float(input("Source y-coordinate: "))
                            dst_x = float(input("Destination x-coordinate: "))
                            dst_y = float(input("Destination y-coordinate: "))
                            plc.write_by_name("Remote.src_x", src_x, pyads.PLCTYPE_LREAL)
                            plc.write_by_name("Remote.src_y", src_y, pyads.PLCTYPE_LREAL)
                            plc.write_by_name("Remote.dst_x", dst_x, pyads.PLCTYPE_LREAL)
                            plc.write_by_name("Remote.dst_y", dst_y, pyads.PLCTYPE_LREAL)
                            sleep(1) # Making sure coordinates are written
                            plc.write_by_name("Remote.transfer_item", True, pyads.PLCTYPE_BOOL)

                        case 9:
                            break

                        case _:
                            print("Invalid selection")


        
                    

    except pyads.ADSError as e:
        print(f"ADS Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()





