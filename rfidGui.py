# pylint: disable=C0112, C0114, C0115, C0116

import sqlite3
import subprocess
from dash import Dash, html, dcc, callback, Output, Input
import dash_daq as daq


# function to read data from the database
def read_lane_data(cursor, lane):
    cursor.execute('SELECT vid, rfid FROM vid_data WHERE lane=?', (lane,))
    row = cursor.fetchone() # retreives info for the specified lane
    if row:
        vid, rfid = row
        return vid, rfid
    else:
        return None, None


# Initialize the Dash app
app = Dash()

# Connect to the SQLite database
sql3Conn = sqlite3.connect('vid_data.db', check_same_thread=False) # create or connect to the database
sql3Cursor = sql3Conn.cursor() # create a cursor object to execute SQL commands

def update_lane_led(value):
    """
    update_lane_led
    """
    if value == "EMPTY":
        return "0", "#FF0000"  # Red for empty
    return value.split(',')[0][5:], "#00FF00"  # Green for valid VID


def update_lane_indicator(vid, rfid):
    """
    update_lane_indicator
    """
    if vid != '0' and vid == rfid:
        return "#00FF00", "VID == Tag"  # Green for match
    return "#FF0000", "VID != Tag"  # Red for mismatch


app.layout = html.Div([
    html.H1("Fuelbay Bus Identification ",
            style={'textAlign': 'center',
                   'fontFamily': 'Arial, sans-serif'} ),

    # Lane 1 Divider
    html.Div([
        html.H2("Lane 1",
            style={'textAlign': 'center',
                   'fontFamily': 'Arial, sans-serif'} ),

        daq.Indicator(
            id='lane-1-indicator',
            label="VID == Tag", # Match or Mismatch
            color="#FF0000",  # Red for mismatch
            size=30,
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': '20px'}
        ),

        daq.LEDDisplay(
            id='LED-display-VID1',
            label="VID",
            value="1234",
            color="#FF0000",
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': '20px'}
        ),

        daq.LEDDisplay(
            id='LED-display-RFID1',
            label="Lane 1 RFID",
            value="1234",
            color="#FF0000",
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': 20}
        )

    ], style={
            'width': '45%',
            'display': 'inline-block',
            'border': '1px solid black',
            'padding': '10px',
            'margin': '5px'}),

    # Lane 2 Divider
    html.Div([
        html.H2("Lane 2",
            style={'textAlign': 'center',
                   'fontFamily': 'Arial, sans-serif'} ),

        daq.Indicator(
            id='lane-2-indicator',
            label="VID == Tag", # Match or Mismatch
            color="#FF0000",  # Red for mismatch
            size=30,
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': '20px'}
        ),

        daq.LEDDisplay(
            id='LED-display-VID2',
            label="VID",
            value="1234",
            color="#FF0000",
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': '20px'}
        ),

        daq.LEDDisplay(
            id='LED-display-RFID2',
            label="Lane 2 RFID",
            value="1234",
            color="#FF0000",
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': 20}
        )

    ], style={
            'width': '45%',
            'display': 'inline-block',
            'border': '1px solid black',
            'padding': '10px',
            'margin': '5px'}),

    dcc.Interval(
        id='interval-component',
        interval=5*250,  # in milliseconds
        n_intervals=0
    )
])


# Update LED displays and indicators
@callback(
    Output('LED-display-VID1'   , 'value'),
    Output('LED-display-VID1'   , 'color'),
    Output('LED-display-VID2'   , 'value'),
    Output('LED-display-VID2'   , 'color'),
    Output('LED-display-RFID1'  , 'value'),
    Output('LED-display-RFID1'  , 'color'),
    Output('LED-display-RFID2'  , 'value'),
    Output('LED-display-RFID2'  , 'color'),
    Output('lane-1-indicator'   , 'color'),
    Output('lane-1-indicator'   , 'label'),
    Output('lane-2-indicator'   , 'color'),
    Output('lane-2-indicator'   , 'label'),
    Output('LED-display-VID1'   , 'label'),
    Output('LED-display-RFID1'  , 'label'),
    Output('LED-display-VID2'   , 'label'),
    Output('LED-display-RFID2'  , 'label'),
    Input('interval-component'  , 'n_intervals')
)


def update_lanes(n_intervals):
    """
    """
    vid_1, rfid_1           = read_lane_data(sql3Cursor, 1)
    vid_2, rfid_2           = read_lane_data(sql3Cursor, 2)

    vid_1_Val, color1       = update_lane_led(vid_1)
    vid_2_Val, color2       = update_lane_led(vid_2)

    rfid_1_Val, rfidCol1    = update_lane_led(rfid_1)
    rfid_2_Val, rfidCol2    = update_lane_led(rfid_2)

    indicator1, label1      = update_lane_indicator(vid_1_Val, rfid_1_Val)
    indicator2, label2      = update_lane_indicator(vid_2_Val, rfid_2_Val)

    return  vid_1_Val,  color1,                                 \
            vid_2_Val,  color2,                                 \
            rfid_1_Val, rfidCol1,                               \
            rfid_2_Val, rfidCol2,                               \
            indicator1, label1, indicator2, label2,             \
            f"VID(1): {vid_1}", f"Tag(1): {rfid_1}",    \
            f"VID(2): {vid_2}", f"Tag(2): {rfid_2}"


if __name__ == '__main__':

    vpnIP = '127.0.0.1' # default is local network
    result = subprocess.run(['tailscale', 'ip', '-4'], capture_output=True, text=True)

    if result.returncode == 0:
        vpnIP = result.stdout[:-1]
        print(f"VPN IP is: <{vpnIP}>")

    print(f"RFID GUI running on: <{vpnIP}>")

    app.run(debug=True, host=vpnIP, port=8050)

#eof
