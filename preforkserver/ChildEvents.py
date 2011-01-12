"""
This is just a file defining the child state events
"""
# Sent from child: Child is waiting for a connection
WAITING = 1
# Sent from child: Child is busy handling a connection
BUSY = 2
# Sent from child: Child is exiting due to an error
EXITING_ERROR = 4
# Sent from child: Child is exiting due to processing max requests
EXITING_MAX = 8
EXITING = EXITING_ERROR | EXITING_MAX
# Sent from manager (parent): Tell the child to exit after handling it's
# current request
CLOSE = 16

# A dictionary to map the event numbers to strings
STRMAP = {
    WAITING: 'WAITING' ,
    BUSY: 'BUSY' ,
    EXITING_ERROR: 'EXITING_ERROR' ,
    EXITING_MAX: 'EXITING_MAX' ,
    EXITING: 'EXITING' ,
    CLOSE: 'CLOSE' ,
}
