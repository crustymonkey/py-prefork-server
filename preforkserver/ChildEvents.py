"""
This is just a file defining the child state events
"""

# Sent from child: Child is waiting for a connection
WAITING = 1
# Sent from child: Child is busy handling a connection
BUSY = 2
# Sent from child: Child is exiting due to an error or handled max requests
EXITING = 4
# Sent from manager (parent): Tell the child to exit after handling it's
# current request
CLOSE = 8
