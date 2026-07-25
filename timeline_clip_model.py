# timeline_clip_model.py
from clip_command import ClipCommand
import uuid


class Track:
    """单条时间轨道模型，存储动作序列、名称、标识色"""
    def __init__(self, name: str, color: str = "#66aaff"):
        self.track_id = str(uuid.uuid4())
        self.name = name
        self.color = color
        self.actions = []  # 动作列表 [{type, x,y,button,pressed,delay,abs_time...}]

    def get_total_time(self) -> float:
        if not self.actions:
            return 0.0
        return max(act["abs_time"] for act in self.actions)

    def slice_range(self, start_idx: int, end_idx: int):
        if start_idx < 0:
            start_idx = 0
        if end_idx >= len(self.actions):
            end_idx = len(self.actions) - 1
        return self.actions[start_idx: end_idx + 1]


class ClipEditor:
    """剪辑核心控制器：多轨道管理、撤销栈、重做栈、剪贴板"""
    def __init__(self):
        self.tracks: list[Track] = []
        self.active_track_id = None
        self.clipboard: list = []
        self.undo_stack: list[ClipCommand] = []
        self.redo_stack: list[ClipCommand] = []
        self.max_stack_size = 100

    def add_track(self, track: Track) -> None:
        self.tracks.append(track)
        if self.active_track_id is None:
            self.active_track_id = track.track_id

    def remove_track(self, track_id: str) -> bool:
        for idx, tr in enumerate(self.tracks):
            if tr.track_id == track_id:
                del self.tracks[idx]
                if self.active_track_id == track_id and self.tracks:
                    self.active_track_id = self.tracks[0].track_id
                elif not self.tracks:
                    self.active_track_id = None
                return True
        return False

    def get_active_track(self) -> Track | None:
        if self.active_track_id is None:
            return None
        for tr in self.tracks:
            if tr.track_id == self.active_track_id:
                return tr
        return None

    def set_active_track_id(self, tid: str):
        self.active_track_id = tid

    def get_track_by_id(self, tid: str) -> Track | None:
        for tr in self.tracks:
            if tr.track_id == tid:
                return tr
        return None

    def execute_command(self, cmd: ClipCommand):
        """执行一条剪辑命令，压入撤销栈，清空重做栈"""
        cmd.execute()
        self.undo_stack.append(cmd)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_stack_size:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.execute()
        self.undo_stack.append(cmd)
        return True

    def copy_range(self, track: Track, start_idx: int, end_idx: int):
        """复制区间至剪贴板（无命令，不支持撤销）"""
        seg = track.slice_range(start_idx, end_idx)
        self.clipboard = seg.copy()

    def clear_clipboard(self):
        self.clipboard.clear()

    def merge_two_tracks(self, target_tid: str, source_tid: str):
        target = self.get_track_by_id(target_tid)
        source = self.get_track_by_id(source_tid)
        if not target or not source:
            return False
        from clip_command import MergeTrackCommand
        cmd = MergeTrackCommand(target, source)
        self.execute_command(cmd)
        return True

    def cut_range(self, track: Track, start_idx: int, end_idx: int):
        from clip_command import CutRangeCommand
        cmd = CutRangeCommand(track, start_idx, end_idx, self.clipboard)
        self.execute_command(cmd)

    def delete_range(self, track: Track, start_idx: int, end_idx: int):
        from clip_command import DeleteRangeCommand
        cmd = DeleteRangeCommand(track, start_idx, end_idx)
        self.execute_command(cmd)

    def paste(self, track: Track, insert_pos: int):
        if not self.clipboard:
            return False
        from clip_command import PasteCommand
        cmd = PasteCommand(track, insert_pos, self.clipboard)
        self.execute_command(cmd)
        return True

    def merge_all_tracks(self) -> Track:
        """合并全部轨道生成一条新轨道，用于回放"""
        all_actions = []
        for tr in self.tracks:
            all_actions.extend(tr.actions)
        # 按照abs_time全局排序
        all_actions.sort(key=lambda x: x["abs_time"])
        new_track = Track(name="合并轨道", color="#dddd44")
        new_track.actions = all_actions
        return new_track