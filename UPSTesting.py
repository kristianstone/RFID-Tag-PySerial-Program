import revpimodio2
import time
import os

shutdown_countdown = 10 # seconds before shutdown

rpi = revpimodio2.RevPiModIO(autorefresh=True)
#rpi.core.a1green.value = 1 how to change LED (1 on, 0 off)


while True:
    if rpi.io.RevPiStatus.value & (1<<6):
        for i in range(shutdown_countdown, 0, -1):
            time.sleep(1)
            if (rpi.io.RevPiStatus.value & (1<<6)):
                print("Shutdown aborted!")
                time.sleep(1)
                break
            print(f"Shutting down in {i} seconds...")
        else:
            print("Shutting down now...")
            os.system("sudo shutdown now")
    else:
        print("low")
        time.sleep(1)