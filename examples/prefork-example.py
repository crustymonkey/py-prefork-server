#!/usr/bin/env python

#
# This is a simple example of how to use the prefork server library.
# The basic idea here is to create a subclass of "BaseChild" and override
# the hooks you wish to implement.  Then, you create a "Manager and run it.
# 

import preforkserver as pfs
import os


class TestChild(pfs.BaseChild):
    """
    You have a number of instance variables in the clas that you have access
    to.  They are as follows:

    self.proto =>       This will be either tcp or udp
    self.reqsHandled => This is the number of requests this child has handled
    self.conn =>        The socket object if this is a tcp server, otherwise
 -                       this will be the actual payload of the udp packet
    self.addr =>        An address tuple containing (ip , port)
    self.closed =>      A boolean, mainly for internal use, which says whether
                        this child has been set to be closed
    self.error =>       A string error message, if set
    """

    def initialize(self, *args, **kwargs):
        """
        Rather than reimplementing __init__, which you can do instead, you
        can just override this and setup and variables and such that you need
        to set up.  This is the recommended approach.
        """
        self.myInstanceVar = kwargs.get('my_var', None)
        self.blacklist = set('10.0.0.1')

    def post_accept(self):
        """
        self.conn and self.addr are set before this is called as a new
        connection has been established.  You can make any modifications/setup
        before "processRequest" is called.
        """
        self.ip, self.port = self.address

    def allow_deny(self):
        """
        You can use this hook to refuse the connection based on the self.conn
        and self.addr variables that have been set.  Return True (default)
        here to accept the connection and False to deny it and close the 
        connection
        """
        if self.ip in self.blacklist:
            return False
        return True

    def request_denied(self):
        """
        If you deny the connection in allowDeny(), you can send a message 
        using this callback before the connection is closed.
        """
        self.conn.sendall('I don\'t like your ip\r\n')

    def process_request(self):
        """
        This is where you are processing the actual request.  You should use
        your self.conn socket to send and receive data from your client in 
        this hook.  
        
        Remember, if this is a udp server, self.conn will be a string with 
        the actual packet payload.  If you have a udp server, and you wish
        to respond, you can use the resp_to() method to do so
        """
        self.conn.sendall('220 Go Ahead\r\n')
        fromClient = self.conn.recv(4096)
        self.conn.sendall('Thank you for your info\r\n')
        print fromClient
        # For UDP connections, you would do something like this
        # data = self.conn
        # self.resp_to('Got data: %s\r\n' % data.strip())
        # When this function exits, the connection is automatically closed

    def post_process_request(self):
        """
        This is called after the connection is closed.  You can perform any
        maintenance/cleanup or post connection processing here.
        """
        print 'Connection is closed, bye %s:%s' % (self.ip, self.port)

    def shutdown(self):
        """
        This is called when the child is exiting.  This can be because it
        has served its maximum number of requests, the parent was told
        to close, or an error has occured.  If an error has occured, 
        self.error will be set.

        Use this to do an pre-close cleanup, like possibly closing open
        files or a database connection.
        """
        print 'Shutting down child %d' % os.getpid()


#
# Now, if you have no special setup needs for your Manager, you can just
# use a basic preforkserver.Manager and get rolling.  There are a number
# of different hooks that can be overridden in the Manager class as well
# that I will show you here.  However, in most cases, you will probably
# just want to use the basic Manager
#

class MyManager(pfs.Manager):
    def pre_bind(self):
        """
        This hook is called before the main socket is created and bound
        to the ip:port.  This is similar to the initialize() hook in the
        child class.  You can use this to set up global variables, etc.
        """
        print 'preBind() called in manager'

    def post_bind(self):
        """
        As you might have guessed, this is called right after the accept()
        socket has been created and bound.
        """
        print 'postBind() called in manager'

    def pre_signal_setup(self):
        """
        This is called before the signal handlers are set up
        """
        print 'preSignalSetup() called in manager'

    def post_signal_setup(self):
        """
        This is called after the signal handlers have been set.  You can
        override the default signal handlers if you like.  More on that below.
        """
        print 'postSignalSetup() called in manager'

    def pre_init_children(self):
        """
        This is called before the child processes are initialized
        """
        print 'preInitChildren() called in manager'

    def post_init_children(self):
        """
        This is called after the child processes are initialized
        """
        print 'postInitChildren() called in manager'

    def pre_loop(self):
        """
        This is the last hook before the main server loop takes over.  
        Any last minute setup items you wish to do should be done here
        """
        print 'preLoop() called in manager'

    def pre_server_close(self):
        """
        This is called before the server shuts down.  Any cleanup you wish
        to take care of before termination should be done here.
        """
        print 'preServerClose() called in manager'

    # Signal handlers can also be overridden in the subclass of the manager.
    # I will just show you what the default implementation looks like
    # here.  If you do override intHandler or termHandler, make sure you
    # call the super() method
    def hup_handler(self, frame, num):
        """
        This handles a SIGHUP.  If you have a config for your server, you
        could reload that here.  By default, this just ignores the signal.
        """
        return

    def int_handler(self, frame, num):
        """
        This handles a SIGINT.  The default is set an internal "stop" event
        to gracefully shutdown.  If you override this, call the super() so
        the graceful shutdown happens
        """
        self._stop.set()

    def term_handler(self, frame, num):
        """
        This handles a SIGTERM.  This does the same thing as intHandler()
        """
        self._stop.set()


def main():
    """
    All of the hard work should be done by this point, so all we have to do
    is init MyManager and call its run() method.  The signature for 
    the base Manager __init__ looks like this:

        def __init__(self , child_class , max_servers=20 , min_servers=5 ,
            min_spare_servers=2 , max_spare_servers=10 , max_requests=0 ,
            bind_ip='127.0.0.1' , port=10000 , protocol='tcp' , listen=5 ,
            reuse_port=False):

    The definition of those variables are:

        child_class<BaseChild>      : An implentation of BaseChild to define
                                      the child processes
        max_servers<int>            : Maximum number of children to have
        min_servers<int>            : Minimum number of children to have
        min_spare_servers<int>      : Minimum number of spare children to have
        max_spare_servers<int>      : Maximum number of spare children to have
        max_requests<int>           : Maximum number of requests each child
                                      should handle.  Zero is unlimited and
                                      default
        bind_ip<str>                : The IP address to bind to
        port<int>                   : The port that the server should listen on
        protocol<str>               : The protocol to use (tcp or udp)
        listen<int>                 : Listen backlog
        reuse_port<bool>            : Use SO_REUSEPORT (if available)

    This is the same info that is available via a
    "pydoc preforkserver.Manager"
    """
    manager = MyManager(TestChild, child_kwargs={'my_var': 'value'})
    manager.run()


if __name__ == '__main__':
    main()
