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

import preforkserver.events as pfe
from time import sleep
import select
import socket
import os

__all__ = ['BaseChild']


class BaseChild(object):
    """
    Defines the base child that should be inherited and the hooks should
    be overriden for use within the Manager
    """

    def __init__(self, server_socket, max_requests, child_conn, protocol):
        """
        Initialize the passed in child info and call the initialize() hook
        """
        self._server_socket = server_socket
        self._max_requests = max_requests
        self._child_conn = child_conn
        self._poll = select.poll()
        self._poll_mask = select.POLLIN | select.POLLPRI
        self._poll.register(self._server_socket.fileno(), self._poll_mask)
        self._poll.register(self._child_conn.fileno(), self._poll_mask)
        self.protocol = protocol
        self.requests_handled = 0
        # The "conn" will be a socket connection object if this is a tcp 
        # server, and will actually be the payload if this is a udp server
        self.conn = None
        self.address = None
        self.closed = False
        self.error = None
        self.initialize()

    def _close_conn(self):
        if self.conn and isinstance(self.conn, socket.SocketType):
            self.conn.close()

    def _waiting(self):
        self._child_conn.send([pfe.WAITING, self.requests_handled])

    def _busy(self):
        self._child_conn.send([pfe.BUSY, self.requests_handled])

    def _error(self, msg=None):
        self.error = msg
        self._child_conn.send([pfe.EXITING_ERROR, str(msg)])

    def _handled_max_requests(self):
        self._child_conn.send([pfe.EXITING_MAX, ''])

    def _handle_parent_event(self):
        """
        Handle an event sent from the parent
        """
        event, msg = self._child_conn.recv()
        event = int(event)
        if event & pfe.CLOSE:
            self.closed = True

    def _handle_connection(self):
        """
        This is the workhorse that actually accepts the connection
        and calls all the hooks
        """
        if self.protocol == 'tcp':
            try:
                self.conn, self.address = self._server_socket.accept()
            except socket.error:
                # There is a condition where more than 1 process can end up here
                # on a single connection.  The second one (this one, if we get 
                # here) will timeout
                return
        else:
            try:
                self.conn, self.address = self._server_socket.recvfrom(8192)
            except socket.error:
                # There is a condition where more than 1 process can end up 
                # here on a single connection.  The second one (this one, 
                # if we get here) will timeout
                return
        self._busy()
        self.post_accept()
        if self.allow_deny():
            self.process_request()
        else:
            self.request_denied()
        self._close_conn()
        self.post_process_request()
        self._waiting()

    def _loop(self):
        while True:
            events = []
            try:
                events = self._poll.poll()
            except select.error, e:
                # This happens when the system call is interrupted
                pass
            for fd, e in events:
                if fd == self._server_socket.fileno():
                    try:
                        self._handle_connection()
                    except Exception, e:
                        self._error(e)
                        self._shutdown(1)
                    self.requests_handled += 1
                elif fd == self._child_conn.fileno():
                    self._handle_parent_event()
            if self.closed:
                self._shutdown()
            if 0 < self._max_requests <= self.requests_handled:
                self._handled_max_requests()
                self._shutdown()

    def _shutdown(self, status=0):
        self._poll.unregister(self._child_conn.fileno())
        self._poll.unregister(self._server_socket.fileno())
        self._child_conn.close()
        self._server_socket.close()
        self.shutdown()
        sleep(0.1)
        os._exit(status)

    def run(self):
        self._loop()

    # Hooks to be overridden
    def initialize(self):
        """
        This is called at the end of __init__().  Any additional initialization
        should be done here
        """
        return

    def post_accept(self):
        """
        self.conn and self.addr are initialized here since a new connection
        has been established.  You can make any modifications/setup needed 
        before handleRequest is called here.
        """
        return

    def allow_deny(self):
        """
        Return True (default) from this hook to allow the connection and False
        to close the socket
        """
        return True

    def request_denied(self):
        """
        This hook is called on a denied connection.  If you wish to send
        a message to the client before the socket is closed, do so here.
        """
        return

    def process_request(self):
        """
        This hook is called for an allowed connection.  Use self.conn here to
        send and receive info from the client
        """
        return

    def post_process_request(self):
        """
        This hook is called after the connection has been processed and the
        socket closed.  You can do any maintainance/cleanup here.
        """
        return

    def shutdown(self):
        """
        This hook is called only when the child is exiting for some reason.
        self.error will be set to an Exception object if there was an error
        condition which caused this shutdown.

        You can do any additional child cleanup in this hook.
        """
        return
