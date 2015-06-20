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

from preforkserver.exceptions import ManagerError
from preforkserver.poller import get_poller
import preforkserver.events as pfe
import multiprocessing as mp
import select
import threading
import weakref
import signal
import socket
import os

__all__ = ['Manager']


class ManagerChild(object):
    """
    Class to represent a child in the Manager
    """

    def __init__(self, pid, parent_conn):
        self.pid = pid
        self.conn = parent_conn
        self.current_state = pfe.WAITING
        self.total_processed = 0

    def close(self):
        self.conn.close()


class Manager(object):
    """
    This class manages all the child processes.
    """
    validProtocols = ('udp', 'tcp')

    def __init__(self, child_class, child_args=None, child_kwargs=None, 
            max_servers=20, min_servers=5,
            min_spare_servers=2, max_spare_servers=10, max_requests=0, 
            bind_ip='127.0.0.1', port=10000, protocol='tcp', listen=5 ,
            reuse_port=False):
        """
        child_class<BaseChild>       : An implentation of BaseChild to define
                                       the child processes
        child_args<list_type>        : The argument list to pass into the
                                       child initialize() method
        child_kwargs<list_type>      : The argument dict to pass into the
                                       child initialize() method
        max_servers<int>             : Maximum number of children to have
        min_servers<int>             : Minimum number of children to have
        min_spare_servers<int>       : Minimum number of spare children to have
        max_spare_servers<int>       : Maximum number of spare children to have
        max_requests<int>            : Maximum number of requests each child
                                      should handle.  Zero is unlimited and
                                      default
        bind_ip<str>                 : The IP address to bind to
        port<int>                    : The port that the server should listen on
        protocol<str>                  : The protocol to use (tcp or udp)
        listen<int>                  : Listen backlog
        reuse_port<bool>             : This will use SO_REUSEPORT and create
                                       the listen sock in each child rather
                                       than in the parent process.  
                                       SO_REUSEPORT will result in a much more
                                       balanced distribution of connections
                                       and it is highly recommended that
                                       you turn this on if available
        """
        if not child_args:
            child_args = []
        if not child_kwargs:
            child_kwargs = {}
        self._ChildClass = child_class
        # Check for proper typing of child args
        if not isinstance(child_args, (tuple, list)):
            raise TypeError('child_args must be a tuple or list type')
        if not isinstance(child_kwargs , dict):
            raise TypeError('child_kwargs must be a dict type')
        self._child_args = child_args
        self._child_kwargs = child_kwargs
        self.max_servers = int(max_servers)
        self.min_servers = int(min_servers)
        if self.min_servers > self.max_servers:
            raise ManagerError('You cannot have minServers '
                '(%d) be larger than maxServers (%d)!' %
                (min_servers, max_servers))
        self.min_spares = int(min_spare_servers)
        self.max_spares = int(max_spare_servers)
        if self.min_spares > self.max_spares:
            raise ManagerError('You cannot have minSpareServers be larger '
                'than maxSpareServers!')
        self.max_requests = int(max_requests)
        self.bind_ip = bind_ip
        self.port = int(port)
        self.protocol = protocol.lower()
        if protocol not in self.validProtocols:
            raise ManagerError('Invalid protocol %s, must be in: %r' %
                (protocol, self.validProtocols))
        self.listen = int(listen)
        self.reuse_port = reuse_port and hasattr(socket , 'SO_REUSEPORT')
        self.server_socket = None
        self._stop = threading.Event()
        self._children = {}
        self._poll = get_poller(select.POLLIN | select.POLLPRI)

        # Bind the socket now so that it can be used before run is called
        # Addresses: https://github.com/crustymonkey/py-prefork-server/pull/3
        if not self.reuse_port:
            self.pre_bind()
            self._bind()
            self.post_bind()

    @property
    def bound_address(self):
        """
        returns the newly bound server address as an (ip, port) tuple
        """
        ret = None 
        if self.server_socket is not None:
            ret = self.server_socket.getsockname()
        return ret

    def _start_child(self):
        """
        Fork off a child and set up communication pipes
        """
        parent_pipe, child_pipe = mp.Pipe()
        self._poll.register(parent_pipe)
        manager = weakref.proxy(self) if self.reuse_port else None
        pid = os.fork()
        if not pid:
            ch = self._ChildClass(self.max_requests , child_pipe , 
                self.protocol , self.server_socket , manager ,
                self._child_args , self._child_kwargs)
            parent_pipe.close()
            ch.run()
        else:
            self._children[parent_pipe.fileno()] = ManagerChild(pid,
                                                                parent_pipe)
            child_pipe.close()
            return

    def _kill_child(self, child, background=True):
        """
        Kill a ManagerChild, child, off.  If background is True, wait for 
        completion in a thread.
        """
        fd = child.conn.fileno()

        try:
            self._poll.unregister(child.conn)
        except:
            pass

        try:
            child.conn.send([pfe.CLOSE, ''])
            child.close()
        except IOError:
            pass

        if fd in self._children:
            del self._children[fd]
        if background:
            t = threading.Thread(target=os.waitpid, args=(child.pid, 0))
            t.daemon = True
            t.start()
        else:
            os.waitpid(child.pid, 0)

    def _handle_child_event(self, child):
        event, msg = child.conn.recv()
        event = int(event)
        if event & pfe.EXITING:
            if event == pfe.EXITING_ERROR:
                self.log('Child %d exited due to error: %s' % (child.pid, msg))
            fd = child.conn.fileno()
            self._poll.unregister(child.conn)
            del self._children[fd]
            child.close()
            os.waitpid(child.pid, 0)
        else:
            child.current_state = int(event)
            child.total_processed = int(msg)

    def _assess_state(self):
        """
        Check the state of all the children and handle startups and shutdowns
        accordingly
        """
        total_busy = 0
        children = self._children.values()
        num_children = len(children)
        for ch in children:
            if ch.current_state & pfe.BUSY:
                total_busy += 1
        spares = num_children - total_busy
        if spares < self.min_spares:
            # We need to fork more children
            diff2max = self.max_servers - num_children
            to_fork = spares
            if diff2max - spares < 0:
                to_fork = diff2max
            for i in xrange(to_fork):
                self._start_child()
        elif spares > self.max_spares + self.min_servers:
            # We have too many spares and need to kill some
            to_kill = spares - self.max_spares
            children = sorted(children,
                cmp=lambda x, y: cmp(x.total_processed, y.total_processed),
                reverse=True)
            # Send closes
            for ch in children[:to_kill]:
                self._kill_child(ch)
        if num_children < self.min_servers:
            for i in xrange(self.min_servers - num_children):
                self._start_child()

    def _init_children(self):
        for i in range(self.min_servers):
            self._start_child()

    def _bind(self):
        """
        Bind the socket
        """
        if self.reuse_port:
            # The socket will be created in the child processes
            return
        address = (self.bind_ip, self.port)
        protocol = socket.SOCK_STREAM
        if self.protocol == 'udp':
            protocol = socket.SOCK_DGRAM
        self.server_socket = socket.socket(socket.AF_INET, protocol)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(address)
        if self.protocol == 'tcp':
            self.server_socket.listen(self.listen)

    def _signal_setup(self):
        # Set the signal handlers
        signal.signal(signal.SIGHUP, self.hup_handler)
        signal.signal(signal.SIGINT, self.int_handler)
        signal.signal(signal.SIGTERM, self.term_handler)

    def _loop(self):
        while True:
            events = []
            if self._stop.isSet():
                break
            try:
                events = self._poll.poll(1 , 10)
            except OSError:
                pass
            except IOError:
                pass
            except select.error:
                # When a signal is received, it can interrupt the system call
                # and break things with an improper exit
                pass
            for sock, e in events:
                fd = sock.fileno()
                if fd in self._children:
                    ch = self._children[fd]
                    self._handle_child_event(ch)
                else:
                    try:
                        self._poll.unregister(sock)
                    except Exception, e:
                        self.log('Error unregistering %d: %s; %s' % (fd, e))
                    try:
                        sock.close()
                    except Exception, e:
                        self.log('Error closing child pipe: %s' % e)
            self._assess_state()

    def _shutdown_server(self):
        self.log('Starting server shutdown')
        children = self._children.values()
        # First loop through and tell the children to close
        for child in children:
            self._kill_child(child, False)
        if self.server_socket:
            self.server_socket.close()
        self.log('Server shutdown completed')

    def run(self):
        self.pre_signal_setup()
        self._signal_setup()
        self.post_signal_setup()
        self.pre_init_children()
        self._init_children()
        self.post_init_children()
        self.pre_loop()
        self._loop()
        self.pre_server_close()
        self._shutdown_server()

    def close(self):
        """
        Stop the server
        """
        self._stop.set()

    # All of the following methods can be overridden in a subclass
    def pre_bind(self):
        """
        This hook is called before the main socket is created and bound
        to the ip:port.  This is similar to the initialize() hook in the
        child class.  You can use this to set up global variables, etc.

        Note that this will NOT be called if reuse_port is set.  Instead,
        this call be overridden in the child, where the bind will occur
        """
        return

    def post_bind(self):
        """
        As you might have guessed, this is called right after the accept()
        socket has been created and bound.

        Note that this will NOT be called if reuse_port is set.  Instead,
        this call be overridden in the child, where the bind will occur
        """
        return

    def pre_signal_setup(self):
        """
        This is called before the signal handlers are set up
        """
        return

    def post_signal_setup(self):
        """
        This is called after the signal handlers have been set.  You can
        override the default signal handlers if you like.  More on that below.
        """
        return

    def pre_init_children(self):
        """
        This is called before the child processes are initialized
        """
        return

    def post_init_children(self):
        """
        This is called after the child processes are initialized
        """
        return

    def pre_loop(self):
        """
        This is the last hook before the main server loop takes over.  
        Any last minute setup items you wish to do should be done here
        """
        return

    def pre_server_close(self):
        """
        This is called before the server shuts down.  Any cleanup you wish
        to take care of before termination should be done here.
        """
        return

    # Signal handling.  These can be overridden in a subclass as well
    def hup_handler(self, frame, num):
        """
        Handle a SIGHUP.  By default, this does nothing
        """
        return

    def int_handler(self, frame, num):
        """
        Handle a SIGINT.  By default, this will stop the server
        """
        self._stop.set()

    def term_handler(self, frame, num):
        """
        Handle a SIGTERM.  By default, this will stop the server
        """
        self._stop.set()

    # Utilities that can be defined
    def log(self, msg):
        """
        You can define a logging method and log internal messages and messages
        you generate.  By default, this does nothing.
        """
        return
