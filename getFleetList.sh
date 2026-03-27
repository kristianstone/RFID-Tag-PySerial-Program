#!/usr/bin/bash
# -vx
# bash script to collect the current version of fleet_list.csv

# http://100.85.208.50/rfid/fleet/      where the fleet_list.csv is stored
# http://100.85.208.50/rfid/dev/        where to find the source code
# http://100.85.208.50/rfid/logs/       where logs can be uploaded

echo "Fleet List Update Started"
echo "Generate sha1 of local fleet_list.csv"
/usr/bin/sha1sum /home/pi/rfid/fleet_list.csv > /home/pi/rfid/fleet_list.local.sha1

echo "Get sha1 of the hosts fleet_list.csv"
/usr/bin/rm /home/pi/rfid/fleet_list.host.sha1
# /usr/bin/scp -o ConnectionAttempts=3 fms2@100.83.58.53:/Users/FMS2/Documents/RFID-Dev/04_DATA/fleet_list.host.sha1  /home/pi/rfid/fleet_list.host.sha1
# --tries=0 --read-timeout=20 --timeout=15 --retry-connrefused
 wget --tries=3 -O ~/rfid/fleet_list.host.sha1 http://100.85.208.50/rfid/fleet/fleet_list.host.sha1

# if fail to copy host sha1 exit
if [ $? -ne 0 ]; then
    echo "Failed to Get SHA1 of the new Fleet List"
    exit 1
fi

FILE1=/home/pi/rfid/fleet_list.host.sha1
FILE2=/home/pi/rfid/fleet_list.local.sha1

touch "$FILE1"      # incase file does not exist
touch "$FILE2"

# sha1 is first string in file
WORD1=$(head -n 1 "$FILE1" | cut -d ' ' -f 1)
WORD2=$(head -n 1 "$FILE2" | cut -d ' ' -f 1)

# Compare the two sha1
if [[ "$WORD1" == "$WORD2" ]]; then
    echo "Fleet List unchanged. $WORD1"
else
    echo "Update Fleet List! Local:<$WORD1> vs Host:<$WORD2>"
    /usr/bin/cp /home/pi/rfid/fleet_list.csv /home/pi/rfid/"fleet_list_$(date +%Y-%m-%d_%H).csv" || true
#    /usr/bin/scp -o ConnectionAttempts=3 fms2@100.83.58.53:/Users/FMS2/Documents/RFID-Dev/04_DATA/fleet_list.csv  /home/pi/rfid/fleet_list.csv.new
    wget --tries=3 -O ~/rfid/fleet_list.csv.new http://100.85.208.50/rfid/fleet/fleet_list.csv

    # if fail to get new csv file exit
    if [ $? -ne 0 ]; then
        echo "Failed to Get the new Fleet List"
        exit 2
    else
        /usr/bin/cat /home/pi/rfid/fleet_list.csv.new > /home/pi/rfid/fleet_list.csv
    fi
fi
echo "Fleet List Update Complete"
#eof


