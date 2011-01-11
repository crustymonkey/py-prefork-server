
import fcntl , os

class LockingFile(object):
    """
    This is a simple locking file implementation for use in place of a 
    semaphore primitive where it isn't available (See FreeBSD)
    """
    def __init__(self , filename):
        self.filename = filename
        self.fh = self._openfile()
        self.read = self.fh.read
        self.seek = self.fh.seek
        self.readline = self.fh.readline
        self.readlines = self.fh.readlines
        self.flush = self.fh.flush
        self.close = self.fh.close
        self.tell = self.fh.tell

    def _openfile(self):
        fd = os.open(self.filename , os.O_CREAT | os.O_RDWR)
        fcntl.lockf(fd , fcntl.LOCK_SH)
        return os.fdopen(fd)

    def write(self , buf):
        fcntl.lockf(self.fh.fileno() , fcntl.LOCK_EX)
        self.fh.write(buf)
        fcntl.lockf(self.fh.fileno() , fcntl.LOCK_SH)

    def writelines(self , seq):
        fcntl.lockf(self.fh.fileno() , fcntl.LOCK_EX)
        for l in seq:
            self.fh.write(l)
        fcntl.lockf(self.fh.fileno() , fcntl.LOCK_SH)
