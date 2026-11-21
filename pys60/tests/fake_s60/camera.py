"""Fake PyS60 camera module."""
photos = []


def flash_modes():
    return ['none', 'auto', 'forced', 'fill_in', 'red_eye_reduce']


def image_sizes():
    return [(2592, 1944), (640, 480), (160, 120)]


def image_modes():
    return ['RGB12', 'RGB16', 'RGB']


def take_photo(mode='RGB16', size=(640, 480), flash='none', zoom=0, exposure='auto',
               white_balance='auto', position=0):
    photos.append((mode, size, flash))
    import e32
    e32.now[0] += 1.2           # a photo takes a while


def release():
    pass


def cameras_available():
    return 1
