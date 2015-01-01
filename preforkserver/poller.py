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

#
# This module contains a generic interface to the various polling options
# supported on various systems.  The idea is to make a simple, standardized
# API that will automatically use the best implementation for the system
# this is running on.  This will be not be comprehensive, in terms of
# functional support, but instead just be a fairly rigid implementation
# for the purposes of this library
#

from preforkserver.exceptions import EventMaskError
import select
import sys

# This is a hack to make this work on systems where POLLIN and 
# POLLPRI (OS X, apparently...) are not defined in the select module
if not hasattr(select , 'POLLIN') or not hasattr(select , 'POLLPRI') or not \
        hasattr(select , 'POLLOUT'):
    setattr(select , 'POLLIN' , 1)
    setattr(select , 'POLLPRI' , 2)
    setattr(select , 'POLLOUT' , 4)
    setattr(select , 'POLLERR' , 8)

def get_poller(def_ev_mask=None):
    """
    This will return the appropriate poller based on the system this
    is running on.  If you know what poller you would like to use,
    you can instantiate that directly

    def_ev_mask:int     The default event mask to set for all sockets that
                        are registered later with the poller.  You can
                        only use select.POLLIN and select.POLLOUT for
                        complete compatibility as not all pollers support
                        polling for things outside of read and write
    """
    p = sys.platform
    if p.startswith('win') or p.startswith('cygwin'):
        # I have no clue if this will work...  My advice is simply to
        # never use windows for anything of this nature
        return Select(def_ev_mask)
    elif ( 'bsd' in p or p.startswith('darwin') ) and \
            hasattr(select , 'KQ_FILTER_READ'):
        return Kqueue(def_ev_mask)
    elif p.startswith('linux') and hasattr(select , 'EPOLLIN'):
        return Epoll(def_ev_mask)
    elif p.startswith('linux') and hasattr(select , 'POLLIN'):
        return Poll(def_ev_mask)
    else: 
        # Fall back to the worst option
        return Select(def_ev_mask)

class BasePoller(object):
    """
    This defines the API for all concrete classes to use 
    """
    
    def __init__(self , def_ev_mask=None):
        """

        def_ev_mask:int         The default event mask to be used for
                                registering new file descriptors.  If no
                                default is set, calls to register MUST
                                include the mask
        """
        self.def_ev_mask = def_ev_mask
        self._sock_map = {}

    def register(self , sock , event_mask=None):
        """
        sock:socket.socket      A socket object to register
        event_mask:int          The event mask to register this with
        """
        raise NotImplementedError('You must implement the register() method')

    def unregister(self , sock):
        """
        sock:socket.socket      A socket object to register
        """
        raise NotImplementedError('You must implement the unregister() method')

    def poll(self , timeout=None , max_events=None):
        """
        timeout:float           The timeout for the poll() call
        max_events:int          The maximum number of events to return
        """
        raise NotImplementedError('You must implement the poll() method')

    def modify(self , sock , event_mask):
        """
        sock:socket.socket      A socket object to register
        event_mask:int          The event mask to register this with
        """
        raise NotImplementedError('You must implement the modify() method')

    def close(self):
        raise NotImplementedError('You must implement the modify() method')

class Poll(BasePoller):

    def __init__(self , def_ev_mask=None):
        BasePoller.__init__(self , def_ev_mask)
        self._poll = select.poll()

    def register(self , sock , event_mask=None):
        if self.def_ev_mask is None and event_mask is None:
            raise EventMaskError('You must specify an event mask for this '
                'descriptor, or specify a default')
        ev_mask = event_mask if event_mask else self.def_ev_mask
        self._poll.register(sock , ev_mask)
        self._sock_map[sock.fileno()] = sock

    def unregister(self , sock):
        self._poll.unregister(sock)
        del self._sock_map[sock.fileno()]

    def modify(self , sock , event_mask):
        self._poll.modify(sock , event_mask)

    def poll(self , timeout=None , max_events=None):
        """
        I'm actually making this a little more convenient here by using a
        socket map to return the socket itself instead of just the
        file descriptor int
        """
        ret = []
        for fd , ev in self._poll(timeout=timeout):
            ret.append( (self._sock_map[fd] , ev) )
        return ret

    def close(self):
        return

class Epoll(Poll):

    def __init__(self , def_ev_mask=None , sizehint=-1):
        BasePoller.__init__(self , def_ev_mask)
        self._poll = select.epoll(sizehint)

    def poll(self , timeout=-1 , max_events=1):
        ret = []
        for fd , ev in self._poll.poll(timeout=timeout , maxevents=max_events):
            ret.append( (self._sock_map[fd] , ev) )
        return ret

    def close(self):
        self._poll.close()

class Select(BasePoller):
    """
    This is an implementation that strays from the polling norm.  This
    diverges quite a bit from the polling interfaces and will have some
    significant changes to make the interface unified
    """

    def __init__(self , def_ev_mask=None):
        BasePoller.__init__(self , def_ev_mask)
        self._poll = None
        self._rlist = set()
        self._wlist = set()
        self._xlist = set()

    def register(self , sock , event_mask=None):
        if self.def_ev_mask is None and event_mask is None:
            raise EventMaskError('You must specify an event mask for this '
                'descriptor, or specify a default')
        ev_mask = event_mask if event_mask else self.def_ev_mask
        # We add this fd to the appropriate select list(s)
        if ev_mask & select.POLLIN:
            self._rlist.add(sock)
        if ev_mask & select.POLLOUT:
            self._wlist.add(sock)
        if ev_mask & select.POLLERR:
            self._xlist.add(sock)

    def unregister(self , sock):
        """
        Here we just remove the socket from any lists it is in
        """
        for l in (self._rlist , self._wlist , self._xlist):
            l.discard(sock)

    def modify(self , sock , event_mask):
        """
        Here we do a remove and add with the new mask
        """
        self.unregister(sock)
        self.register(sock , event_mask)

    def poll(self , timeout=None , max_events=None):
        ret = []
        rlist , wlist , xlist = select.select(list(self._rlist) , 
            list(self._wlist) , list(self._xlist) , timeout)
        for read in rlist:
            ret.append( (read , select.POLLIN) )
        for write in wlist:
            ret.append( (read , select.POLLOUT) )
        for err in xlist:
            ret.append( (read , select.POLLERR) )
        return ret

    def close(self):
        for l in (self._rlist , self._wlist , self._xlist):
            l.clear()

class Kqueue(BasePoller):
    """
    This is another API that is quite different from the poll API.
    """

    def __init__(self , def_ev_mask=None):
        BasePoller.__init__(self , def_ev_mask)
        self._kev_table = {}
        # We are only going to support a tiny subset of the kevent filters
        # that are available.  This will map standard polling events to
        # kevent filters
        self._event_map = {
            select.POLLIN: select.KQ_FILTER_READ ,
            select.POLLOUT: select.KQ_FILTER_WRITE ,
        }
        self._rev_event_map = {}
        for ev , kev in self._event_map.iteritems():
            self._rev_event_map[kev] = ev
        self._poll = select.kqueue()

    def register(self , sock , event_mask=None):
        if self.def_ev_mask is None and event_mask is None:
            raise EventMaskError('You must specify an event mask for this '
                'descriptor, or specify a default')
        ev_mask = event_mask if event_mask else self.def_ev_mask
        ke = self._get_kevent(sock , ev_mask)
        self._kev_table[sock.fileno()] = ke
        self._sock_map[sock.fileno()] = sock

    def unregister(self , sock):
        del self._kev_table[sock.fileno()]
        del self._sock_map[sock.fileno()]

    def modify(self , sock , event_mask):
        """
        Simply unregister and register this socket
        """
        self.unregister(sock)
        self.register(sock , event_mask)

    def poll(self , timeout=None , max_events=1):
        """
        We have to call kqueue.control() here and modify the results to
        look like the results of the other pollers
        """
        ret = []
        for ev in self._poll.control(self._kev_table.values() , max_events ,
                timeout):
            ret.append( (self._sock_map[ev.ident] , 
                self._rev_event_map[ev.filter]) )
        return ret

    def close(self):
        self._poll.close()

    def _get_kevent(self , sock , mask):
        filt = 0
        for ev , kq_ev in self._event_map.iteritems():
            filt |= kq_ev if ev & mask else 0
        return select.kevent(sock , filt)
