from dash import Dash, html, dcc, callback, Output, Input
import dash_daq as daq
from rfidUtilTesting import read_lane_data
import sqlite3

# Initialize the Dash app
app = Dash()

# Connect to the SQLite database
conn = sqlite3.connect('vid_data.db', check_same_thread=False) # create or connect to the database
cursor = conn.cursor() # create a cursor object to execute SQL commands

def update_lane_led(value):
    if value == "empty":
        return "0", "#FF0000"  # Red for empty
    else:
        return value.split(',')[0][5:], "#00FF00"  # Green for valid VID

def update_lane_indicator(vid, rfid):
    if vid != '0' and vid == rfid:
        return "#00FF00", "Match"  # Green for match
    else:
        return "#FF0000", "Mismatch"  # Red for mismatch

app.layout = html.Div([
    html.H1("TBG Fuelbay Bus Identification System",
            style={'textAlign': 'center',
                   'fontFamily': 'Arial, sans-serif'} ),
    
    # Lane 1 Divider 
    html.Div([
        html.H2("Lane 1 Data",
            style={'textAlign': 'center',
                   'fontFamily': 'Arial, sans-serif'} ),

        daq.Indicator(
            id='lane-1-indicator',
            label="Mismatch", # Match or Mismatch
            color="#FF0000",  # Red for mismatch
            size=30,
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': '20px'}
        ),

        daq.LEDDisplay(
            id='LED-display-VID1',
            label="Lane 1 VID",
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
        html.H2("Lane 2 Data",
            style={'textAlign': 'center',
                   'fontFamily': 'Arial, sans-serif'} ),

        daq.Indicator(
            id='lane-2-indicator',
            label="Mismatch", # Match or Mismatch
            color="#FF0000",  # Red for mismatch
            size=30,
            style={'fontFamily': 'Arial, sans-serif',
                   'marginBottom': '20px'}
        ),

        daq.LEDDisplay(
            id='LED-display-VID2',
            label="Lane 2 VID",
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
        interval=1*1000,  # in milliseconds
        n_intervals=0
    )
])

# Update LED displays and indicators
@callback(
    Output('LED-display-VID1', 'value'),
    Output('LED-display-VID1', 'color'),
    Output('LED-display-VID2', 'value'),
    Output('LED-display-VID2', 'color'),
    Output('LED-display-RFID1', 'value'),
    Output('LED-display-RFID1', 'color'),
    Output('LED-display-RFID2', 'value'),
    Output('LED-display-RFID2', 'color'),
    Output('lane-1-indicator', 'color'),
    Output('lane-1-indicator', 'label'),
    Output('lane-2-indicator', 'color'),
    Output('lane-2-indicator', 'label'),
    Output('LED-display-VID1', 'label'),
    Output('LED-display-RFID1', 'label'),
    Output('LED-display-VID2', 'label'),
    Output('LED-display-RFID2', 'label'),
    Input('interval-component', 'n_intervals')
)

def update_lanes(n_intervals):
    vid1, rfid1 = read_lane_data(cursor, 1)
    vid2, rfid2 = read_lane_data(cursor, 2)
    
    vid1Val, color = update_lane_led(vid1)
    vid2Val, color2 = update_lane_led(vid2)
    
    rfid1Val, rfidCol1 = update_lane_led(rfid1)
    rfid2Val, rfidCol2 = update_lane_led(rfid2)

    indicator1, label1 = update_lane_indicator(vid1Val, rfid1Val)
    indicator2, label2 = update_lane_indicator(vid2Val, rfid2Val)
        
    return vid1Val, color, vid2Val, color2, rfid1Val, rfidCol1, \
        rfid2Val, rfidCol2, indicator1, label1, indicator2, label2, \
        f"Lane 1 VID: {vid1}", f"Lane 1 RFID: {rfid1}", \
        f"Lane 2 VID: {vid2}", f"Lane 2 RFID: {rfid2}"

if __name__ == '__main__':
    app.run(debug=True)