"""Fake native module: records every call. `lit_method` says which LED
method really lights the LED (what the user would answer in LED setup)."""
calls = []
targets = 0x3            # display + keypad
state = {"cam": 0, "polls": 0, "api": None, "flash": 0, "vf": 0, "opens": 0}
cam_fail = [0]


def version():
    return 1


def log():
    return "light init 0 3\n"


def light_targets():
    return targets


def light_on(t, intensity=0, duration=0, fade=0):
    calls.append(("on", t, intensity))
    return 0


def light_off(t, fade=0):
    calls.append(("off", t))
    return 0


def light_blink(*a):
    calls.append(("blink",) + a)
    return 0


def light_status(t):
    return 0


def light_reserve(t, on=1):
    return 0


def cam_count():
    return 1


def cam_open(index=0, api=2):
    state["cam"] = 1
    state["polls"] = 0
    state["api"] = api
    state["opens"] += 1
    calls.append(("cam_open", api))
    return 0


def cam_state():
    if state["cam"] in (1, 2):
        state["polls"] += 1
        if cam_fail[0]:
            if state["polls"] > 2:
                state["cam"] = 4
        elif state["polls"] > 2:
            state["cam"] = 3
    err = 0
    if state["cam"] == 4:
        err = -14
    return (state["cam"], err, 0x0F, 0x8F, 0)


def cam_flash(mode, method=0):
    if state["cam"] != 3:
        return -18
    state["flash"] = mode
    calls.append(("flash", mode, method))
    return 0


def cam_flash_mode():
    return state["flash"]


def cam_viewfinder(on):
    state["vf"] = on
    calls.append(("vf", on))
    return 0


def cam_video(level):
    state["video"] = level
    calls.append(("video", level))
    return 0


def cam_close():
    state["cam"] = 0
    state["flash"] = 0
    calls.append(("cam_close",))


def close():
    calls.append(("close",))
