"""Fake e32 for PC tests: timers run on a simulated clock, in order.
Ao_lock.wait() runs due timers until the lock is signalled."""
now = [0.0]
timers = []          # [due, seq, callback, owner]
seq = [0]
inactivity_resets = [0]


def _add(delay, cb, owner):
    seq[0] = seq[0] + 1
    timers.append([now[0] + delay, seq[0], cb, owner])


def run_for(seconds):
    """Runs every timer due within the next `seconds` of simulated time."""
    end = now[0] + seconds
    while 1:
        due = [t for t in timers if t[0] <= end]
        if not due:
            break
        due.sort()
        t = due[0]
        timers.remove(t)
        now[0] = max(now[0], t[0])
        t[2]()
    now[0] = end


class Ao_lock(object):
    def __init__(self):
        self.signalled = 0

    def wait(self):
        guard = 0
        while not self.signalled:
            if not timers:
                raise RuntimeError("Ao_lock.wait() would block forever")
            timers.sort()
            t = timers.pop(0)
            now[0] = max(now[0], t[0])
            t[2]()
            guard += 1
            assert guard < 100000
        self.signalled = 0

    def signal(self):
        self.signalled = 1


class Ao_timer(object):
    def after(self, sec, cb=None):
        assert sec >= 0
        if cb is None:
            now[0] += sec
            return
        self.cancel()
        _add(sec, cb, self)

    def cancel(self):
        for t in timers[:]:
            if t[3] is self:
                timers.remove(t)


def ao_sleep(t, cb=None):
    if cb is None:
        run_for(t)
    else:
        _add(t, cb, None)


def ao_yield():
    pass


def reset_inactivity():
    inactivity_resets[0] += 1


def drive_list():
    return [u'C:', u'E:']


s60_version_info = (3, 2)
pys60_version = '1.4.5 final'
