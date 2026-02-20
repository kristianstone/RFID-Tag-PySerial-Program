###############
# UPS Variables
###############
SHUTDOWN_COUNT_DOWN:int = 10

####################
# Relay Output Value
####################
LED_OFF:int = 0
LED_ON:int  = 1

Q_EMPTY:int     = 0         # nothing on the Q for enough reads to declare Lane is Empty
Q_POLLING:int   = -1        # nothing on the Q just now - need to poll a few times to establis lane is empty
Q_READY:int     = 1         # something on the Q  to be read

MSG_INIT:str    =   "INIT"
MSG_EMPTY:str   =   "EMPTY"
MSG_POLLING:str =   "POLLING"

STD_MSG_LEN             = len("0-BBT1234,12345678\r\n")
VID_MSG_MISSING_ODO_LEN = len("0-BBT1234")