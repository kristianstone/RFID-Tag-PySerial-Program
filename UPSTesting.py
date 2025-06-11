import revpimodio2
import time
import os

rpi = revpimodio2.RevPiModIO(autorefresh=True)

while True:
    if(rpi.io.RevPiStatus.value & (1<<6)):
        rpi.core.a1green.value = 1
        os.system('sudo shutdown now')
    else:
        os.system('low')
        time.sleep(1)
        rpi.core.a1green.value = 0