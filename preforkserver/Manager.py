from LockingFile import LockingFile

class Manager(object):
    """
    This class manages all the child processes.
    """
    def __init__(self , childClass , maxServers=20 , minServers=5 , 
            minSpareServers=2 , maxSpareServers=10 , maxRequests=0 ,  
            bindIp='127.0.0.1' , port=10000 , proto='tcp' , listen=5 ,
            lockfile='/var/tmp/pyprefork.lock'):
        """
        childClass<BaseChild>       : An implentation of BaseChild to define
                                      the child processes
        maxServers<int>             : Maximum number of children to have
        minServers<int>             : Minimum number of children to have
        minSpareServers<int>        : Minimum number of spare children to have
        maxSpareServers<int>        : Maximum number of spare children to have
        maxRequests<int>            : Maximum number of requests each child
                                      should handle.  Zero is unlimited
        bindIp<str>                 : The IP address to bind to
        port<int>                   : The port that the server should listen on
        proto<str>                  : The protocol to use (tcp or udp)
        listen<int>                 : Listen backlog
        lockfile<str>               : Path to a file to use for locking and 
                                      communication
        """
        self.childClass = childClass
        self.maxServers = int(maxServers)
        self.minServers = int(minServers)
        self.minSpare = int(minSpareServers)
        self.maxSpare = int(maxSpareServers)
        self.maxReqs = int(maxRequests)
        self.bindIp = bindIp
        self.port = int(port)
        self.proto = proto
        self.listen = int(listen)
        self.lockfile = lockfile

    def serve_forever(self):
        pass
