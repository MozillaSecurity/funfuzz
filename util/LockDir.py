import os

class LockDir():
    '''
    Creates a filesystem-based lock while in scope.
    Use:
        with LockDir(path):
            # No other code is concurrently using LockDir(path)
    '''
    def __init__(self, d):
        self.d = d
    def __enter__(self):
        try:
            os.mkdir(self.d)
        except OSError:
            print "Lock file exists: " + self.d
            raise
    def __exit__(self, exc_type, exc_val, exc_tb):
        os.rmdir(self.d)
