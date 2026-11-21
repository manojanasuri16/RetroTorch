"""Fake appuifw for PC tests: scripted answers, recorded notes."""
notes = []
answers = []          # queue for query() / popup_menu()


class _App(object):
    def __init__(self):
        self.title = u''
        self.body = None
        self.menu = []
        self.exit_key_handler = None
        self.screen = 'normal'
        self.exited = 0

    def set_exit(self):
        self.exited = 1


app = _App()


def note(text, kind="info"):
    assert isinstance(text, unicode), repr(text)
    notes.append((kind, text))


def _answer(kind, prompt):
    assert isinstance(prompt, unicode), repr(prompt)
    if not answers:
        raise AssertionError("unexpected %s: %r" % (kind, prompt))
    a = answers.pop(0)
    if callable(a):
        return a(prompt)
    return a


def query(prompt, kind, initial=None):
    return _answer("query", prompt)


def popup_menu(items, title=u""):
    for i in items:
        assert isinstance(i, unicode), repr(i)
    return _answer("popup_menu", title)


class Canvas(object):
    def __init__(self, redraw_callback=None, event_callback=None):
        self.keys = {}
        self.blits = 0
        self.last = None

    @property
    def size(self):
        if app.screen == 'full':
            return (240, 320)
        if app.screen == 'large':
            return (240, 292)
        return (240, 234)

    def bind(self, code, cb):
        self.keys[code] = cb

    def blit(self, img, **k):
        self.blits += 1
        self.last = img


class Text(object):
    def __init__(self):
        self.text = u""

    def set(self, t):
        assert isinstance(t, unicode), repr(t)
        self.text = t
