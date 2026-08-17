# config.py
from pynput.keyboard import Key

class AppConfig:
    FILE_SUFFIX = ".json"
    MODE_FULL = "full"
    MODE_SIMPLE = "simple"
    
    # 默认快捷键配置（使用字符串表示，便于序列化）
    DEFAULT_HOTKEYS = {
        "start_record": "f1",
        "stop_record": "f2", 
        "play_last": "f5",
        "pause_record": "f9"
    }
    
    # 运行时快捷键（将从配置文件加载）
    HOTKEYS = DEFAULT_HOTKEYS.copy()
    
    # 快捷键映射表（字符串 -> Key对象）
    KEY_MAP = {
        "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
        "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
        "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
        "enter": Key.enter, "esc": Key.esc, "space": Key.space,
        "tab": Key.tab, "backspace": Key.backspace, "delete": Key.delete,
        "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        "home": Key.home, "end": Key.end, "page_up": Key.page_up, "page_down": Key.page_down,
        "ctrl": Key.ctrl, "ctrl_l": Key.ctrl_l, "ctrl_r": Key.ctrl_r,
        "shift": Key.shift, "shift_l": Key.shift_l, "shift_r": Key.shift_r,
        "alt": Key.alt, "alt_l": Key.alt_l, "alt_r": Key.alt_r,
        "cmd": Key.cmd, "cmd_l": Key.cmd_l, "cmd_r": Key.cmd_r,
        "caps_lock": Key.caps_lock, "num_lock": Key.num_lock, "scroll_lock": Key.scroll_lock,
        "insert": Key.insert, "pause": Key.pause, "print_screen": Key.print_screen,
    }
    
    # 快捷键显示名称映射
    KEY_DISPLAY_MAP = {
        "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4",
        "f5": "F5", "f6": "F6", "f7": "F7", "f8": "F8",
        "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
        "enter": "Enter", "esc": "ESC", "space": "Space",
        "tab": "Tab", "backspace": "Backspace", "delete": "Delete",
        "up": "↑", "down": "↓", "left": "←", "right": "→",
        "home": "Home", "end": "End", "page_up": "PageUp", "page_down": "PageDown",
        "ctrl": "Ctrl", "ctrl_l": "Ctrl(L)", "ctrl_r": "Ctrl(R)",
        "shift": "Shift", "shift_l": "Shift(L)", "shift_r": "Shift(R)",
        "alt": "Alt", "alt_l": "Alt(L)", "alt_r": "Alt(R)",
        "cmd": "Cmd", "cmd_l": "Cmd(L)", "cmd_r": "Cmd(R)",
        "caps_lock": "CapsLock", "num_lock": "NumLock", "scroll_lock": "ScrollLock",
        "insert": "Insert", "pause": "Pause", "print_screen": "PrintScreen",
    }
    
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
    
    # 配置文件路径
    CONFIG_FILE = "macro_config.json"
    
    @classmethod
    def get_key(cls, key_name: str) -> Key:
        """根据字符串获取Key对象"""
        return cls.KEY_MAP.get(key_name.lower(), Key.f1)
    
    @classmethod
    def get_display_name(cls, key_name: str) -> str:
        """获取快捷键的显示名称"""
        return cls.KEY_DISPLAY_MAP.get(key_name.lower(), key_name.upper())
    
    @classmethod
    def load_hotkeys(cls):
        """从配置文件加载快捷键"""
        import json
        import os
        try:
            if os.path.exists(cls.CONFIG_FILE):
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "hotkeys" in config:
                        cls.HOTKEYS.update(config["hotkeys"])
        except Exception:
            pass
    
    @classmethod
    def save_hotkeys(cls):
        """保存快捷键到配置文件"""
        import json
        try:
            with open(cls.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"hotkeys": cls.HOTKEYS}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    @classmethod
    def reset_hotkeys(cls):
        """重置快捷键为默认值"""
        cls.HOTKEYS = cls.DEFAULT_HOTKEYS.copy()
        cls.save_hotkeys()
        AppConfig.load_hotkeys()