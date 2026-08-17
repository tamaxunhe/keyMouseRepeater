# config.py
from pynput.keyboard import Key
class AppConfig:
    FILE_SUFFIX = ".json"
    MODE_FULL = "full"
    MODE_SIMPLE = "simple"
    START_HOTKEY = Key.f1      # 改为 F1
    EXIT_HOTKEY = Key.f2       # 改为 F2
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
    # 双击判定配置
    DOUBLE_CLICK_MS = 300
    DOUBLE_CLICK_POS_TOLERANCE = 5
    # 修饰键列表
    MODIFIER_KEYS = {
        Key.ctrl, Key.ctrl_l, Key.ctrl_r,
        Key.shift, Key.shift_l, Key.shift_r,
        Key.alt, Key.alt_l, Key.alt_r,
        Key.cmd, Key.cmd_l, Key.cmd_r
    }
    # 偏移文件配置
    OFFSET_FILE_EXT = ".txt"
    OFFSET_LINE_SPLIT = ","