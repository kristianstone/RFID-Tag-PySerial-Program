#!/usr/bin/bash
# -vx
# bash script to collect the current version of fleet_list.csv

/usr/bin/sha1sum /home/pi/rfid/fleet_list.csv > /home/pi/rfid/fleet_list.local.sha1
/usr/bin/scp fms2@100.83.58.53:/Users/FMS2/Documents/RFID-Dev/04_DATA/fleet_list.host.sha1  /home/pi/rfid/fleet_list.host.sha1

FILE1=/home/pi/rfid/fleet_list.host.sha1
FILE2=/home/pi/rfid/fleet_list.local.sha1

touch "$FILE1"      # incase file does not exist
touch "$FILE1"

# sha1 is first string in file
WORD1=$(head -n 1 "$FILE1" | cut -d ' ' -f 1)
WORD2=$(head -n 1 "$FILE2" | cut -d ' ' -f 1)

# Compare the two sha1
if [[ "$WORD1" == "$WORD2" ]]; then
    echo "Fleet List unchanged. $WORD1"
else
    echo "Update Fleet List! $WORD1 vs $WORD2"
    /usr/bin/mv /home/pi/rfid/fleet_list.csv /home/pi/rfid/"fleet_list_$(date +%Y-%m-%d_%H).csv" || true
    /usr/bin/scp fms2@100.83.58.53:/Users/FMS2/Documents/RFID-Dev/04_DATA/fleet_list.csv  /home/pi/rfid/fleet_list.csv
fi


