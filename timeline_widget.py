# timeline_widget.py
import tkinter as tk
from tkinter import ttk

class TimelineWidget(ttk.Frame):
    """
    多轨道时间轴视图组件
    职责：渲染多条轨道、动作圆点、切割标记、平滑播放游标、鼠标框选区间
    向外抛出事件，不持有原始业务数据，解耦
    回调说明：
    on_cut_change：设置切割点
    on_playhead_jump：拖拽游标请求跳转回放
    on_range_select：鼠标框选一段区间 (track_id, start_idx, end_idx)
    on_clip_command：右键菜单剪辑指令
    """
    COLOR_MAP = {
        "mouse_move": "#66aaff",
        "mouse_scroll": "#ffcc66",
        "key_press": "#88ee88",
        "key_release": "#77cc77",
        "mouse_click_left_down": "#ff3333",
        "mouse_click_left_up": "#ff9999",
        "mouse_click_right_down": "#9933ff",
        "mouse_click_right_up": "#ddb8ff",
        "mouse_click_middle_down": "#ffaa22",
        "mouse_click_middle_up": "#ffdd99",
        "mouse_click_x1_down": "#22cccc",
        "mouse_click_x1_up": "#b8eeee",
        "mouse_click_x2_down": "#cc2299",
        "mouse_click_x2_up": "#ffb8dd",
    }

    def __init__(self, master,
                 on_cut_change=None,
                 on_playhead_jump=None,
                 on_range_select=None,
                 on_clip_command=None,
                 **kwargs):
        super().__init__(master, **kwargs)
        self.on_cut_change = on_cut_change
        self.on_playhead_jump = on_playhead_jump
        self.on_range_select = on_range_select
        self.on_clip_command = on_clip_command

        self.tracks_data = []
        self.cut_abs_time: float | None = None
        self.play_abs_time: float | None = None
        self.playhead_dragging = False

        self.select_start_x = None
        self.select_end_x = None
        self.selection_track_id = None
        self.selection_start_idx = None
        self.selection_end_idx = None

        self.filter_vars = {
            "mouse_move": tk.BooleanVar(value=True),
            "mouse_click": tk.BooleanVar(value=True),
            "mouse_scroll": tk.BooleanVar(value=True),
            "key_press": tk.BooleanVar(value=True),
            "key_release": tk.BooleanVar(value=True),
        }

        self.canvas_height_per_track = 110
        self.canvas_width = 0
        self.canvas = None
        self.cut_info_text = tk.StringVar(value="切割位置：未选定")
        self._build_ui()
        self._bind_events()
        self._smooth_render_loop()

    def _build_ui(self):
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=4, pady=(2,4))
        ttk.Label(filter_frame, text="显示筛选：").pack(side=tk.LEFT)
        ttk.Checkbutton(filter_frame, text="鼠标移动(蓝)", variable=self.filter_vars["mouse_move"], command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="鼠标点击(多色)", variable=self.filter_vars["mouse_click"], command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="滚轮(黄)", variable=self.filter_vars["mouse_scroll"], command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="按键按下(绿)", variable=self.filter_vars["key_press"], command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="按键释放(浅绿)", variable=self.filter_vars["key_release"], command=self.redraw).pack(side=tk.LEFT, padx=2)

        self.canvas = tk.Canvas(self, bg="#1e1e1e")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill=tk.X, padx=4, pady=(0,4))
        ttk.Label(ctrl_frame, textvariable=self.cut_info_text).pack(side=tk.LEFT)
        ttk.Button(ctrl_frame, text="从此切割点继续录制", command=self._notify_cut).pack(side=tk.LEFT, padx=10)
        ttk.Button(ctrl_frame, text="清除切割标记", command=self.clear_cut).pack(side=tk.LEFT)
        ttk.Button(ctrl_frame, text="清空视图", command=self.clear_view).pack(side=tk.LEFT, padx=10)

    def _bind_events(self):
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._canvas_left_click)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self.canvas.bind("<Button-3>", self._canvas_right_menu)
        self.canvas.bind("<Motion>", self._canvas_mouse_move)
        self.canvas.bind("<Leave>", self._hide_tip)
        self.hover_tip = None

    def _smooth_render_loop(self):
        self.redraw()
        self.after(30, self._smooth_render_loop)

    def set_tracks(self, track_list):
        self.tracks_data = track_list.copy()
        self.play_abs_time = None
        self.cut_abs_time = None
        self._clear_selection()
        self.redraw()

    def clear_view(self):
        self.tracks_data.clear()
        self.play_abs_time = None
        self.cut_abs_time = None
        self._clear_selection()
        self.cut_info_text.set("切割位置：未选定")
        self.redraw()

    def clear_cut(self):
        self.cut_abs_time = None
        self.cut_info_text.set("切割位置：未选定")

    def _clear_selection(self):
        self.select_start_x = None
        self.select_end_x = None
        self.selection_track_id = None
        self.selection_start_idx = None
        self.selection_end_idx = None

    def _time_to_x(self, abs_time: float, max_global_t: float) -> float:
        if max_global_t <= 0:
            return 10
        usable_w = max(self.canvas_width - 20, 1)
        ratio = abs_time / max_global_t
        return 10 + ratio * usable_w

    def _x_to_time(self, x: float, max_global_t: float) -> float | None:
        if max_global_t <= 0:
            return None
        usable_w = max(self.canvas_width - 20, 1)
        ratio = (x - 10) / usable_w
        ratio = max(min(ratio, 1.0), 0.0)
        return ratio * max_global_t

    def _find_nearest_action_index(self, track_actions, target_t: float):
        if not track_actions:
            return None
        best_idx = 0
        min_diff = abs(track_actions[0]["abs_time"] - target_t)
        for idx, act in enumerate(track_actions):
            diff = abs(act["abs_time"] - target_t)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
        return best_idx

    def _canvas_left_click(self, event):
        self._clear_selection()
        self.select_start_x = event.x

    def _canvas_drag(self, event):
        self.select_end_x = event.x
        self.playhead_dragging = True
        if not self.tracks_data:
            return
        all_times = []
        for tr in self.tracks_data:
            for a in tr.actions:
                all_times.append(a["abs_time"])
        max_t = max(all_times) if all_times else 0
        t = self._x_to_time(event.x, max_t)
        if t is not None:
            self.play_abs_time = t
        self.redraw()

    def _canvas_release(self, event):
        if self.playhead_dragging and self.play_abs_time is not None and self.on_playhead_jump:
            self.on_playhead_jump(self.play_abs_time)
        self.playhead_dragging = False
        if self.select_start_x is not None and self.select_end_x is not None and abs(self.select_start_x - self.select_end_x) > 6:
            all_times = []
            for tr in self.tracks_data:
                for a in tr.actions:
                    all_times.append(a["abs_time"])
            max_t = max(all_times) if all_times else 0
            t_start = self._x_to_time(min(self.select_start_x, self.select_end_x), max_t)
            t_end = self._x_to_time(max(self.select_start_x, self.select_end_x), max_t)
            if t_start is not None and t_end is not None:
                target_track = self.tracks_data[0]
                idx_s = self._find_nearest_action_index(target_track.actions, t_start)
                idx_e = self._find_nearest_action_index(target_track.actions, t_end)
                self.selection_track_id = target_track.track_id
                self.selection_start_idx = min(idx_s, idx_e)
                self.selection_end_idx = max(idx_s, idx_e)
                if self.on_range_select:
                    self.on_range_select(self.selection_track_id, self.selection_start_idx, self.selection_end_idx)
        self.redraw()

    def _canvas_right_menu(self, event):
        menu = tk.Menu(self.canvas, tearoff=False)
        if self.play_abs_time is not None:
            menu.add_command(label="从此处开始回放", command=lambda: self.on_playhead_jump and self.on_playhead_jump(self.play_abs_time))
        if self.selection_track_id is not None:
            menu.add_separator()
            menu.add_command(label="剪切选中片段", command=lambda: self.on_clip_command and self.on_clip_command("cut", self.selection_track_id, self.selection_start_idx, self.selection_end_idx))
            menu.add_command(label="复制选中片段", command=lambda: self.on_clip_command and self.on_clip_command("copy", self.selection_track_id, self.selection_start_idx, self.selection_end_idx))
            menu.add_command(label="删除选中片段", command=lambda: self.on_clip_command and self.on_clip_command("delete", self.selection_track_id, self.selection_start_idx, self.selection_end_idx))
        menu.add_command(label="设置为切割点", command=lambda: self._set_cut_by_x(event.x))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_cut_by_x(self, x):
        if not self.tracks_data:
            return
        all_times = []
        for tr in self.tracks_data:
            for a in tr.actions:
                all_times.append(a["abs_time"])
        max_t = max(all_times) if all_times else 0
        t = self._x_to_time(x, max_t)
        if t is None:
            return
        self.cut_abs_time = t
        ref_track = self.tracks_data[0]
        idx = self._find_nearest_action_index(ref_track.actions, t)
        self.cut_info_text.set(f"切割位置：动作索引 {idx}，时间 {t:.2f}s")

    def _notify_cut(self):
        if self.on_cut_change and self.cut_abs_time is not None:
            ref_track = self.tracks_data[0]
            idx = self._find_nearest_action_index(ref_track.actions, self.cut_abs_time)
            self.on_cut_change(idx)

    def _on_canvas_resize(self, event):
        self.canvas_width = event.width

    def _canvas_mouse_move(self, event):
        self._hide_tip()
        if not self.tracks_data:
            return
        all_times = []
        for tr in self.tracks_data:
            for a in tr.actions:
                all_times.append(a["abs_time"])
        max_t = max(all_times) if all_times else 0
        target_t = self._x_to_time(event.x, max_t)
        if target_t is None:
            return
        best_act = None
        min_gap = 9999
        for track in self.tracks_data:
            for act in track.actions:
                gap = abs(act["abs_time"] - target_t)
                if gap < min_gap and gap < 0.32:
                    min_gap = gap
                    best_act = act
        if best_act:
            tip_text = f"类型:{best_act['type']}\n时间:{best_act['abs_time']:.2f}s"
            if "x" in best_act:
                tip_text += f"\n坐标 X:{best_act['x']} Y:{best_act['y']}"
            if best_act["type"] == "mouse_click":
                tip_text += f"\n按键:{best_act['button']} 【{'按下' if best_act['pressed'] else '抬起'}】"
            if "key" in best_act:
                tip_text += f"\n按键:{best_act['key']}"
            tip_win = tk.Toplevel(self.canvas)
            tip_win.wm_overrideredirect(True)
            tip_win.geometry(f"+{event.x_root+15}+{event.y_root+10}")
            tk.Label(tip_win, text=tip_text, bg="#222222", fg="#ffffff", justify="left", padx=4, pady=3).pack()
            self.hover_tip = tip_win

    def _hide_tip(self, event=None):
        if self.hover_tip:
            self.hover_tip.destroy()
            self.hover_tip = None

    def redraw(self):
        canvas = self.canvas
        canvas.delete(tk.ALL)
        if not self.tracks_data:
            canvas.create_text(self.canvas_width//2, 60, fill="#aaaaaa", text="暂无轨道数据，请导入轨道或完成录制")
            return

        all_times = []
        for tr in self.tracks_data:
            for act in tr.actions:
                all_times.append(act["abs_time"])
        max_global_t = max(all_times) if all_times else 0
        track_offset_y = 20

        for track in self.tracks_data:
            y_base = track_offset_y
            track_offset_y += self.canvas_height_per_track
            canvas.create_line(10, y_base, self.canvas_width-10, y_base, fill="#555555")
            canvas.create_text(12, y_base+18, fill="#dddddd", anchor="nw", text=f"【{track.name}】", font=("Arial",9))

            for idx, act in enumerate(track.actions):
                act_type = act["type"]
                if act_type == "mouse_move" and not self.filter_vars["mouse_move"].get():
                    continue
                if act_type == "mouse_click" and not self.filter_vars["mouse_click"].get():
                    continue
                if act_type == "mouse_scroll" and not self.filter_vars["mouse_scroll"].get():
                    continue
                if act_type == "key_press" and not self.filter_vars["key_press"].get():
                    continue
                if act_type == "key_release" and not self.filter_vars["key_release"].get():
                    continue

                x_pos = self._time_to_x(act["abs_time"], max_global_t)
                dot_y = y_base + 45

                if act_type == "mouse_click":
                    btn = act["button"]
                    pressed = act["pressed"]
                    color_key = f"mouse_click_{btn}_{'down' if pressed else 'up'}"
                    dot_color = self.COLOR_MAP.get(color_key, "#ffffff")
                else:
                    dot_color = self.COLOR_MAP.get(act_type, "#ffffff")
                canvas.create_oval(x_pos-3, dot_y-3, x_pos+3, dot_y+3, fill=dot_color)

            tick_step = max(max_global_t / 10, 0.01)
            cur_t = 0.0
            while cur_t <= max_global_t:
                x = self._time_to_x(cur_t, max_global_t)
                canvas.create_line(x, 10, x, track_offset_y-10, fill="#444444")
                canvas.create_text(x, track_offset_y-14, fill="#aaaaaa", text=f"{cur_t:.1f}s", font=("Arial",8))
                cur_t += tick_step

        if self.cut_abs_time is not None:
            cut_x = self._time_to_x(self.cut_abs_time, max_global_t)
            canvas.create_line(cut_x, 10, cut_x, track_offset_y, fill="#ffdd00", width=2, dash=(4,2))

        if self.play_abs_time is not None:
            play_x = self._time_to_x(self.play_abs_time, max_global_t)
            canvas.create_line(play_x, 10, play_x, track_offset_y, fill="#ff2222", width=2)

        if self.select_start_x is not None and self.select_end_x is not None:
            x1 = min(self.select_start_x, self.select_end_x)
            x2 = max(self.select_start_x, self.select_end_x)
            canvas.create_rectangle(x1,10,x2, track_offset_y, outline="#ffdd00", dash=(2,2))