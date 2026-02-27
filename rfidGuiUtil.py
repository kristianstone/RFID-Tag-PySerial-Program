# function to read data from the database
def read_lane_data(cursor, lane):
    cursor.execute('SELECT vid, rfid FROM vid_data WHERE lane=?', (lane,))
    row = cursor.fetchone() # retreives info for the specified lane
    if row:
        vid, rfid = row
        return vid, rfid
    else:
        return None, None