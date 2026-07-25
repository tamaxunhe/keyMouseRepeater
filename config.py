# config.py
from pynput.keyboard import Key

class AppConfig:
    FILE_SUFFIX = ".json"
    MODE_FULL = "full"
    MODE_SIMPLE = "simple"
    START_HOTKEY = Key.enter
    EXIT_HOTKEY = Key.esc
    PLAY_LAST_HOTKEY = Key.f5
    REC_PAUSE_HOTKEY = Key.f9
    TIME_PRECISION = 4
    MAX_COUNTDOWN = 30
    MIN_SPEED = 0.01
    MAX_SPEED = 100.0
    OFFSET_FIXED = "fixed"
    OFFSET_ITER = "iterative"
    CTRL_CHAR_MAP = {
        "\u0003": "c",
        "\u0016": "v"
    }