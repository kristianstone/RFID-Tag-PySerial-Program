from dash import Dash, html, dcc, callback, Output, Input
import dash_daq as daq
import rfidMainTest


app = Dash()

print(rfidMainTest.currentVID1)

app.layout = html.Div([
    daq.LEDDisplay(
        id='my-LED-display-1',
        label="Default",
        value=6
    ),
    dcc.Slider(
        id='my-LED-display-slider-1',
        min=0,
        max=10,
        step=1,
        value=5
    ),
])

@callback(
    Output('my-LED-display-1', 'value'),
    Input('my-LED-display-slider-1', 'value')
)
def update_output(value):
    return str(value)


if __name__ == '__main__':
    app.run(debug=True)