# timeline_widget.py
import tkinter as tk
from tkinter import ttk
class TimelineWidget(ttk.Frame):
    """独立封装时间轴组件：渲染、悬浮提示、切割点、类型筛选、回放游标、区分左右键按下/抬起、双击展示"""
    COLOR_MAP = {
        "mouse_move": "#66aaff",
        "mouse_scroll": "#ffcc66",
        "key_press": "#88ee88",
        "key_release": "#77cc77",
        "mouse_double_click": "#00ffff",
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
    def __init__(self, master, on_cut_position_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_cut_position_change = on_cut_position_change
        self.action_data = []
        self.cut_pos_x = None
        self.cut_info_text = tk.StringVar(value="切割位置：未选定")
        self.play_action_index: int | None = None
        self.filter_vars = {
            "mouse_move": tk.BooleanVar(value=True),
            "mouse_click": tk.BooleanVar(value=True),
            "mouse_scroll": tk.BooleanVar(value=True),
            "key_press": tk.BooleanVar(value=True),
            "key_release": tk.BooleanVar(value=True),
            "mouse_double_click": tk.BooleanVar(value=True),
        }
        self.canvas_height = 140
        self.canvas_width = 0
        self.hover_tip = None
        self._build_widgets()
        self._bind_events()
    def _build_widgets(self):
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=4, pady=(2,4))
        ttk.Label(filter_frame, text="显示筛选：").pack(side=tk.LEFT)
        ttk.Checkbutton(filter_frame, text="鼠标移动(蓝)", variable=self.filter_vars["mouse_move"],
                        command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="鼠标点击(多色区分)", variable=self.filter_vars["mouse_click"],
                        command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="鼠标滚轮(黄)", variable=self.filter_vars["mouse_scroll"],
                        command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="按键按下(绿)", variable=self.filter_vars["key_press"],
                        command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="按键释放(浅绿)", variable=self.filter_vars["key_release"],
                        command=self.redraw).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(filter_frame, text="鼠标双击(青)", variable=self.filter_vars["mouse_double_click"],
                        command=self.redraw).pack(side=tk.LEFT, padx=2)
        self.canvas = tk.Canvas(self, bg="#222222", height=self.canvas_height)
        self.canvas.pack(fill=tk.X, padx=4, pady=4)
        # ctrl_frame = ttk.Frame(self)
        # ctrl_frame.pack(fill=tk.X, padx=4, pady=(0,4))
        # ttk.Label(ctrl_frame, textvariable=self.cut_info_text).pack(side=tk.LEFT)
        # ttk.Button(ctrl_frame, text="从此切割点继续录制", command=self._notify_cut).pack(side=tk.LEFT, padx=10)
        # ttk.Button(ctrl_frame, text="清除切割点", command=self.clear_cut).pack(side=tk.LEFT)
        # ttk.Button(ctrl_frame, text="清空时间轴", command=self.clear).pack(side=tk.LEFT, padx=10)
    def _bind_events(self):
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._hide_tip)
    def set_data(self, data_list):
        self.action_data = data_list.copy()
        self.play_action_index = None
        self.redraw()
    def append_action(self, action_dict):
        self.action_data.append(action_dict)
        self.redraw()
    def clear(self):
        self.action_data.clear()
        self.cut_pos_x = None
        self.play_action_index = None
        self.cut_info_text.set("切割位置：未选定")
        self.redraw()
    def clear_cut(self):
        self.cut_pos_x = None
        self.cut_info_text.set("切割位置：未选定")
        self.redraw()
    def set_play_index(self, action_idx: int | None):
        self.play_action_index = action_idx
        self.redraw()
    def get_cut_index(self):
        if not self.action_data or self.cut_pos_x is None:
            return None
        max_t = max(a["abs_time"] for a in self.action_data)
        if max_t <= 0:
            return None
        cw = max(self.canvas_width - 20, 1)
        ratio = (self.cut_pos_x - 10) / cw
        target_t = max_t * ratio
        best_idx = len(self.action_data)
        for idx, act in enumerate(self.action_data):
            if act["abs_time"] >= target_t:
                best_idx = idx
                break
        return best_idx
    def redraw(self):
        self.canvas.delete(tk.ALL)
        data_filtered = []
        for d in self.action_data:
            if d["type"] == "mouse_move" and not self.filter_vars["mouse_move"].get():
                continue
            if d["type"] == "mouse_click" and not self.filter_vars["mouse_click"].get():
                continue
            if d["type"] == "mouse_scroll" and not self.filter_vars["mouse_scroll"].get():
                continue
            if d["type"] == "key_press" and not self.filter_vars["key_press"].get():
                continue
            if d["type"] == "key_release" and not self.filter_vars["key_release"].get():
                continue
            if d["type"] == "mouse_double_click" and not self.filter_vars["mouse_double_click"].get():
                continue
            data_filtered.append(d)
        if not data_filtered:
            self.canvas.create_text(
                self.canvas_width//2, self.canvas_height//2,
                fill="#aaaaaa", text="暂无录制动作"
            )
            return
        max_time = max(act["abs_time"] for act in data_filtered)
        pad_top = 20
        bottom_y = self.canvas_height - 10
        cw = max(self.canvas_width - 20, 1)
        self.canvas.create_line(10, bottom_y, self.canvas_width-10, bottom_y, fill="#777777")
        step = max(1.0, round(max_time / 10, 1))
        t = 0.0
        while t <= max_time:
            ratio = t / max_time
            x = 10 + ratio * cw
            self.canvas.create_line(x, bottom_y, x, bottom_y-8, fill="#999999")
            self.canvas.create_text(x, bottom_y-12, fill="#cccccc", text=f"{t:.1f}s")
            t += step
        click_counter = 0
        click_info = {}
        for idx, act in enumerate(self.action_data):
            if act["type"] == "mouse_click":
                click_counter += 1
                click_info[idx] = click_counter
        for idx, act in enumerate(self.action_data):
            if act["type"] == "mouse_move" and not self.filter_vars["mouse_move"].get():
                continue
            if act["type"] == "mouse_click" and not self.filter_vars["mouse_click"].get():
                continue
            if act["type"] == "mouse_scroll" and not self.filter_vars["mouse_scroll"].get():
                continue
            if act["type"] == "key_press" and not self.filter_vars["key_press"].get():
                continue
            if act["type"] == "key_release" and not self.filter_vars["key_release"].get():
                continue
            if act["type"] == "mouse_double_click" and not self.filter_vars["mouse_double_click"].get():
                continue
            rt = act["abs_time"]
            r = rt / max_time
            x = 10 + r * cw
            if act["type"] == "mouse_double_click":
                color = self.COLOR_MAP["mouse_double_click"]
                self.canvas.create_oval(x-5, bottom_y-14, x+5, bottom_y-4, fill=color)
                self.canvas.create_text(x, bottom_y - 18, fill="#000", font=("Arial",8), text="DBL")
            elif act["type"] == "mouse_click":
                btn = act["button"]
                pressed = act["pressed"]
                state_key = f"mouse_click_{btn}_{'down' if pressed else 'up'}"
                color = self.COLOR_MAP.get(state_key, "#ffffff")
                self.canvas.create_oval(x-3, bottom_y-12, x+3, bottom_y-6, fill=color)
                if idx in click_info:
                    num = click_info[idx]
                    self.canvas.create_text(x, bottom_y - 18, fill="#fff", font=("Arial",8), text=f"#{num}")
            else:
                color = self.COLOR_MAP.get(act["type"], "#ffffff")
                self.canvas.create_oval(x-3, bottom_y-12, x+3, bottom_y-6, fill=color)
        if self.play_action_index is not None and 0 <= self.play_action_index < len(self.action_data):
            target_act = self.action_data[self.play_action_index]
            rt = target_act["abs_time"]
            r = rt / max_time
            x = 10 + r * cw
            self.canvas.create_line(x, pad_top, x, bottom_y, fill="#ff2222", width=2)
        if self.cut_pos_x is not None:
            self.canvas.create_line(
                self.cut_pos_x, pad_top, self.cut_pos_x, bottom_y,
                fill="#ffdd00", width=2, dash=(4,2)
            )
    def _on_canvas_resize(self, event):
        self.canvas_width = event.width
        self.redraw()
    def _on_canvas_click(self, event):
        if not self.action_data:
            return
        self.cut_pos_x = event.x
        max_t = max(a["abs_time"] for a in self.action_data)
        cw = max(self.canvas_width - 20, 1)
        ratio = (event.x - 10) / cw
        target_t = max_t * ratio
        best_idx = len(self.action_data)
        for idx, act in enumerate(self.action_data):
            if act["abs_time"] >= target_t:
                best_idx = idx
                break
        self.cut_info_text.set(f"切割位置：动作索引 {best_idx}，时间 {target_t:.2f}s")
        self.redraw()
    def _on_mouse_move(self, event):
        self._hide_tip()
        if not self.action_data:
            return
        max_t = max(a["abs_time"] for a in self.action_data)
        if max_t <= 0:
            return
        cw = max(self.canvas_width - 20, 1)
        mx = event.x
        best_act = None
        min_dist = 9999
        for act in self.action_data:
            rt = act["abs_time"]
            px = 10 + (rt / max_t) * cw
            dist = abs(px - mx)
            if dist < 8 and dist < min_dist:
                min_dist = dist
                best_act = act
        if best_act:
            tip_text = f"类型:{best_act['type']}\n时间:{best_act['abs_time']:.2f}s"
            if "x" in best_act:
                tip_text += f"\n坐标 X:{best_act['x']} Y:{best_act['y']}"
            if "key" in best_act:
                tip_text += f"\n按键:{best_act['key']}"
            if "modifiers" in best_act and best_act["modifiers"]:
                tip_text += f"\n修饰键:{','.join(best_act['modifiers'])}"
            if best_act["type"] == "mouse_click":
                tip_text += f"\n按键:{best_act['button']} 【{'按下' if best_act['pressed'] else '抬起'}】"
            if best_act["type"] == "mouse_double_click":
                tip_text += f"\n双击按键:{best_act['button']}"
            self.hover_tip = tk.Toplevel(self)
            self.hover_tip.wm_overrideredirect(True)
            self.hover_tip.geometry(f"+{event.x_root+15}+{event.y_root+10}")
            lbl = tk.Label(self.hover_tip, text=tip_text, bg="#222222", fg="#ffffff", justify="left", padx=4, pady=2)
            lbl.pack()
    def _hide_tip(self, event=None):
        if self.hover_tip:
            self.hover_tip.destroy()
            self.hover_tip = None
    def _notify_cut(self):
        idx = self.get_cut_index()
        if self.on_cut_position_change:
            self.on_cut_position_change(idx)