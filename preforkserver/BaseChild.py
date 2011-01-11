import ChildEvents as ce
import select

__all__ == ['BaseChild']

class BaseChild(object):
    """
    Defines the base child that should be inherited and the hooks should
    be overriden for use within the Manager
    """
    def __init__(self , accSock , maxReqs , chConn):
        """
        Initialize the passed in child info and call the initialize() hook
        """
        self._accSock = accSock
        self._maxReqs = maxReqs
        self._chConn = chConn
        self._poll = select.poll()
        self._pollMask = select.POLLIN | select.POLLPRI
        self._poll.register(self._accSock.fileno() , self._pollMask)
        self._poll.register(self._chConn.fileno() , self._pollMask)
        self.reqsHandled = 0
        self.conn = None
        self.addr = None
        self.closed = False
        self.error = None
        self.initialize()

    def _closeConn(self):
        if self.conn:
            self.conn.close()

    def _waiting(self):
        self._chConn.send([ce.WAITING , self.reqsHandled])

    def _busy(self):
        self._chConn.send([ce.BUSY , self.reqsHandled])

    def _error(self , msg=None):
        self.error = msg
        self._chConn.send([ce.EXITING_ERROR , str(msg)])

    def _handledMaxReqs(self):
        self._chConn.send([ce.EXITING_MAX , ''])

    def _handleParEvent(self):
        """
        Handle an event sent from the parent
        """
        event , msg = self._chConn.recv()
        event = int(event)
        if event & ce.CLOSE:
            self.closed = True

    def _handleConnection(self):
        """
        This is the workhorse that actually accepts the connection
        and calls all the hooks
        """
        self.conn , self.addr = self._accSock.accept()
        self.postAccept()
        if self.allowDeny():
            self.processRequest()
        else:
            self.requestDenied()
        self._closeConn()
        self.postProcessRequest()

    def _loop(self):
        while True:
            events = self._poll.poll()
            for fd , e in events:
                if fd == self._accSock.fileno():
                    try:
                        self._handleConnection()
                    except Exception , e:
                        self._error(e)
                        self._shutdown()
                    self.reqsHandled += 1
                elif fd == self._chConn.fileno():
                    self._handleParEvent()
            if self.closed:
                self._shutdown()
            if self.reqsHandled >= self._maxReqs:
                self._handledMaxReqs()
                self._shutdown()

    def _shutdown(self):
        self._poll.unregister(self._chConn.fileno())
        self._poll.unregister(self._accSock.fileno())
        self._chConn.close()
        self._accSock.close()
        self.shutdown()
        os._exit()
            
    def run(self):
        self._loop()

    # Hooks to be overridden
    def initialize(self):
        """
        This is called at the end of __init__().  Any additional initialization
        should be done here
        """
        return

    def postAccept(self):
        """
        self.conn and self.addr are initialized here since a new connection
        has been established.  You can make any modifications/setup needed 
        before handleRequest is called here.
        """
        return

    def allowDeny(self):
        """
        Return True (default) from this hook to allow the connection and False
        to close the socket
        """
        return True

    def requestDenied(self):
        """
        This hook is called on a denied connection.  If you wish to send
        a message to the client before the socket is closed, do so here.
        """
        return

    def processRequest(self):
        """
        This hook is called for an allowed connection.  Use self.conn here to
        send and receive info from the client
        """
        return

    def postProcessRequest(self):
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
