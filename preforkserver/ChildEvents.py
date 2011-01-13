#
#    Author: Jay Deiman
#    Email: admin@splitstreams.com
# 
#    This file is part of py-prefork-server.
#
#    py-prefork-server is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    py-prefork-server is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with py-prefork-server.  If not, see <http://www.gnu.org/licenses/>.
#

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
