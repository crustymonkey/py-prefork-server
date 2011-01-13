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

import ChildEvents as ce
import multiprocessing as mp
import threading , socket , signal , select , os

__all__ = ['Manager']

class ManagerError(Exception):
    pass

class ManagerChild(object):
    """
    Class to represent a child in the Manager
    """
    def __init__(self , pid , parConn):
        self.pid = pid
        self.conn = parConn
        self.curState = ce.WAITING
        self.totalProcessed = 0

    def close(self):
        self.conn.close()

class Manager(object):
    """
    This class manages all the child processes.
    """
    validProtocols = ('udp' , 'tcp')

    def __init__(self , childClass , maxServers=20 , minServers=5 , 
            minSpareServers=2 , maxSpareServers=10 , maxRequests=0 ,  
            bindIp='127.0.0.1' , port=10000 , proto='tcp' , listen=5):
        """
        childClass<BaseChild>       : An implentation of BaseChild to define
                                      the child processes
        maxServers<int>             : Maximum number of children to have
        minServers<int>             : Minimum number of children to have
        minSpareServers<int>        : Minimum number of spare children to have
        maxSpareServers<int>        : Maximum number of spare children to have
        maxRequests<int>            : Maximum number of requests each child
                                      should handle.  Zero is unlimited and
                                      default
        bindIp<str>                 : The IP address to bind to
        port<int>                   : The port that the server should listen on
        proto<str>                  : The protocol to use (tcp or udp)
        listen<int>                 : Listen backlog
        """
        self.childClass = childClass
        self.maxServers = int(maxServers)
        self.minServers = int(minServers)
        self.minSpares = int(minSpareServers)
        self.maxSpares = int(maxSpareServers)
        self.maxReqs = int(maxRequests)
        self.bindIp = bindIp
        self.port = int(port)
        self.proto = proto.lower()
        if proto not in self.validProtocols:
            raise ManagerError('Invalid protocol %s, must be in: %r' % (proto ,
                self.validProtocols))
        self.listen = int(listen)
        self.accSock = None
        self._stop = threading.Event()
        self._children = {}
        self._poll = select.poll()
        self._pollMask = select.POLLIN | select.POLLPRI

    def _startChild(self):
        parPipe , chPipe = mp.Pipe()
        self._poll.register(parPipe.fileno() , self._pollMask)
        pid = os.fork()
        if not pid:
            ch = self.childClass(self.accSock , self.maxReqs , chPipe , 
                self.proto)
            ch.run()
        else:
            self._children[parPipe.fileno()] = ManagerChild(pid , parPipe)
            return

    def _killChild(self , child , background=True):
        """
        Kill a ManagerChild, child, off.  If background is True, wait for 
        completion in a thread.
        """
        fd = child.conn.fileno()
        try:
            child.conn.send([ce.CLOSE , ''])
            child.close()
        except IOError:
            pass
        try:
            self._poll.unregister(fd)
        except:
            pass
        if fd in self._children:
            del self._children[fd]
        if background:
            t = threading.Thread(target=os.waitpid , args=(child.pid , 0))
            t.daemon = True
            t.start()
        else:
            os.waitpid(child.pid , 0)

    def _handleChildEvent(self , child):
        event , msg = child.conn.recv()
        event = int(event)
        if event & ce.EXITING:
            if event == ce.EXITING_ERROR:
                self.log('Child %d exited due to error: %s' % (child.pid , msg))
            fd = child.conn.fileno()
            self._poll.unregister(fd)
            del self._children[fd]
            child.close()
            os.waitpid(child.pid , 0)
        else:
            child.curState = int(event)
            child.totalProcessed = int(msg)

    def _assessState(self):
        """
        Check the state of all the children and handle startups and shutdowns
        accordingly
        """
        totalBusy = 0
        children = self._children.values()
        numChildren = len(children)
        for ch in children:
            if ch.curState & ce.BUSY:
                totalBusy += 1
        spares = numChildren - totalBusy
        if spares < self.minSpares:
            # We need to fork more children
            diff2max = self.maxServers - numChildren
            toFork = spares
            if diff2max - spares < 0:
                toFork = diff2max
            for i in xrange(toFork):
                self._startChild()
        elif spares > self.maxSpares:
            # We have too many spares and need to kill some
            toKill = spares - self.maxSpares
            children = sorted(children ,
                cmp=lambda x,y: cmp(x.totalProcessed , y.totalProcessed) ,
                reverse=True)
            # Send closes
            for ch in children[:toKill]:
                self._killChild(ch)
        if numChildren < self.minServers:
            for i in xrange(self.minServers - numChildren):
                self._startChild()

    def _initChildren(self):
        for i in range(self.minServers):
            self._startChild()

    def _bind(self):
        """
        Bind the socket
        """
        addr = (self.bindIp , self.port)
        proto = socket.SOCK_STREAM
        if self.proto == 'udp':
            proto = socket.SOCK_DGRAM
        self.accSock = socket.socket(socket.AF_INET , proto)
        self.accSock.settimeout(0.01)
        self.accSock.bind(addr)
        if self.proto == 'tcp':
            self.accSock.listen(self.listen)

    def _signalSetup(self):
        # Set the signal handlers
        signal.signal(signal.SIGHUP , self.hupHandler)
        signal.signal(signal.SIGINT , self.intHandler)
        signal.signal(signal.SIGTERM , self.termHandler)

    def _loop(self):
        while True:
            events = []
            if self._stop.isSet():
                break
            try:
                events = self._poll.poll(1)
            except select.error:
                # When a signal is received, it can interrupt the system call
                # and break things with an improper exit
                pass
            for fd , e in events:
                if fd in self._children:
                    ch = self._children[fd]
                    self._handleChildEvent(ch)
                else:
                    try:
                        self._poll.unregister(fd)
                    except Exception , e:
                        self.log('Error unregistering %d: %s; %s' % (fd , e))
                    try:
                        os.close(fd)
                    except Exception , e:
                        self.log('Error closing child pipe: %s' % e)
            self._assessState()
            
    def _shutdownServer(self):
        self.log('Starting server shutdown')
        children = self._children.values()
        # First loop through and tell the children to close
        for ch in children:
            self._killChild(ch , False)
        self.accSock.close()
        self.log('Server shutdown completed')
    
    def run(self):
        self.preBind()
        self._bind()
        self.postBind()
        self.preSignalSetup()
        self._signalSetup()
        self.postSignalSetup()
        self.preInitChildren()
        self._initChildren()
        self.postInitChildren()
        self.preLoop()
        self._loop()
        self.preServerClose()
        self._shutdownServer()

    def close(self):
        """
        Stop the server
        """
        self._stop.set()

    # All of the following methods can be overridden in a subclass
    def preBind(self):
        return

    def postBind(self):
        return

    def preSignalSetup(self):
        return

    def postSignalSetup(self):
        return

    def preInitChildren(self):
        return

    def postInitChildren(self):
        return

    def preLoop(self):
        return

    def preServerClose(self):
        return

    # Signal handling.  These can be overridden in a subclass as well
    def hupHandler(self , frame , num):
        """
        Handle a SIGHUP.  By default, this does nothing
        """
        return

    def intHandler(self , frame , num):
        """
        Handle a SIGINT.  By default, this will stop the server
        """
        self._stop.set()

    def termHandler(self , frame , num):
        """
        Handle a SIGTERM.  By default, this will stop the server
        """
        self._stop.set()

    # Utilities that can be defined
    def log(self , msg):
        """
        You can define a logging method and log internal messages and messages
        you generate.  By default, this does nothing.
        """
        return
