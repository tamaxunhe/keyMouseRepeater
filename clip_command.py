# clip_command.py
from abc import ABC, abstractmethod

class ClipCommand(ABC):
    """剪辑操作命令基类，支持execute/undo，实现撤销重做"""
    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def undo(self):
        pass


class DeleteRangeCommand(ClipCommand):
    """删除一段动作区间"""
    def __init__(self, track, start_idx: int, end_idx: int):
        self.track = track
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.saved_segment = None

    def execute(self):
        self.saved_segment = self.track.actions[self.start_idx:self.end_idx+1]
        del self.track.actions[self.start_idx:self.end_idx+1]

    def undo(self):
        self.track.actions[self.start_idx:self.start_idx] = self.saved_segment


class CutRangeCommand(ClipCommand):
    """剪切区间，存入剪贴板"""
    def __init__(self, track, start_idx: int, end_idx: int, clipboard):
        self.track = track
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.clipboard = clipboard
        self.saved_segment = None

    def execute(self):
        self.saved_segment = self.track.actions[self.start_idx:self.end_idx+1]
        self.clipboard.clear()
        self.clipboard.extend(self.saved_segment)
        del self.track.actions[self.start_idx:self.end_idx+1]

    def undo(self):
        self.track.actions[self.start_idx:self.start_idx] = self.saved_segment


class PasteCommand(ClipCommand):
    """在指定位置粘贴剪贴板内容"""
    def __init__(self, track, insert_pos: int, clip_data):
        self.track = track
        self.insert_pos = insert_pos
        self.clip_data = clip_data.copy()
        self.insert_len = len(clip_data)

    def execute(self):
        self.track.actions[self.insert_pos:self.insert_pos] = self.clip_data

    def undo(self):
        del self.track.actions[self.insert_pos:self.insert_pos+self.insert_len]


class MergeTrackCommand(ClipCommand):
    """合并两条轨道，source合并至target尾部"""
    def __init__(self, target_track, source_track):
        self.target_track = target_track
        self.source_track = source_track
        self.original_len = len(target_track.actions)
        self.merge_data = source_track.actions.copy()

    def execute(self):
        self.target_track.actions.extend(self.merge_data)

    def undo(self):
        del self.target_track.actions[self.original_len:]