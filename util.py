# util.py
import ctypes
import json
from datetime import datetime
from pynput.mouse import Button
from config import AppConfig
from timeline_clip_model import Track


class ScreenUtil:
    @staticmethod
    def get_all_monitors():
        monitors = []
        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long)]

        def enum_monitor_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            r = ctypes.cast(lprcMonitor, ctypes.POINTER(RECT)).contents
            monitors.append((r.left, r.top, r.right, r.bottom))
            return 1

        MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                             ctypes.POINTER(RECT), ctypes.c_uint)
        callback = MONITORENUMPROC(enum_monitor_callback)
        user32.EnumDisplayMonitors(0, None, callback, 0)
        return monitors

    @staticmethod
    def get_cursor_screen_index(x: int, y: int, monitor_list):
        for idx, (left, top, right, bottom) in enumerate(monitor_list):
            if left <= x < right and top <= y < bottom:
                return idx + 1
        return -1


class FileUtil:
    @staticmethod
    def get_time_stamp_filename() -> str:
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{time_str}{AppConfig.FILE_SUFFIX}"

    @staticmethod
    def save_recording(file_name: str, action_data: list):
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(action_data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_recording(file_name: str) -> list:
        fix_name = file_name if file_name.endswith(AppConfig.FILE_SUFFIX) else f"{file_name}{AppConfig.FILE_SUFFIX}"
        with open(fix_name, "r", encoding="utf-8") as f:
            raw = json.load(f)
        accum = 0.0
        for act in raw:
            if "abs_time" not in act:
                act["abs_time"] = accum
            accum += act["delay"]
        return raw

    @staticmethod
    def track_from_json(file_path: str, track_name: str = None, color="#66aaff") -> Track:
        """从json录制文件新建轨道，用于【导入时间轨道】功能"""
        actions = FileUtil.load_recording(file_path)
        if track_name is None:
            track_name = file_path.split("/")[-1].split("\\")[-1]
        track = Track(name=track_name, color=color)
        track.actions = actions
        return track

    @staticmethod
    def track_save_json(track: Track, save_path: str):
        """将一条轨道导出为录制json文件"""
        FileUtil.save_recording(save_path, track.actions)


class ActionConverter:
    @staticmethod
    def mouse_btn_to_str(btn: Button) -> str:
        mapping = {
            Button.left: "left",
            Button.right: "right",
            Button.middle: "middle",
            Button.x1: "x1",
            Button.x2: "x2"
        }
        return mapping.get(btn, str(btn))

    @staticmethod
    def str_to_mouse_btn(btn_str: str) -> Button:
        mapping = {
            "left": Button.left,
            "right": Button.right,
            "middle": Button.middle,
            "x1": Button.x1,
            "x2": Button.x2
        }
        return mapping.get(btn_str, Button.left)


def parse_number_set(expr: str) -> set[int]:
    """
    解析 "1-5,7,10" 格式字符串，返回整数集合
    空字符串返回空集合
    """
    result = set()
    if not expr.strip():
        return result
    parts = expr.strip().split(",")
    for p in parts:
        seg = p.strip()
        if not seg:
            continue
        if "-" in seg:
            a_str, b_str = seg.split("-", 1)
            a = int(a_str.strip())
            b = int(b_str.strip())
            start = min(a, b)
            end = max(a, b)
            for num in range(start, end + 1):
                result.add(num)
        else:
            num = int(seg.strip())
            result.add(num)
    return result