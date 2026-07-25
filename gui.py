# gui.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import queue
import threading
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseCtrl

from config import AppConfig
from core import RecorderCore, PlayerCore
from util import ScreenUtil, FileUtil, parse_number_set
from timeline_widget import TimelineWidget
from timeline_clip_model import ClipEditor, Track


class MacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("键鼠宏录制剪辑工具｜多轨道剪辑版")
        self.root.geometry("1160x860")

        # 消息队列
        self.log_queue = queue.Queue()
        self.ui_action_queue = queue.Queue()

        # 回放内核
        self.player = PlayerCore(self.log_queue)
        self.last_play_file = None
        self.is_working = False
        self.is_capturing_offset = False
        self.is_recording_now = False

        # 鼠标坐标监视
        self.mouse_monitor_running = False
        self.mouse_ctrl = MouseCtrl()
        self.mouse_coord_var = tk.StringVar(value="鼠标坐标：未开启监视")
        self.monitor_list = ScreenUtil.get_all_monitors()

        # 剪辑模型（核心多轨道管理器）
        self.clip_editor = ClipEditor()

        self.build_menu()
        self.build_ui()
        self.bind_hotkey()

        self.poll_all_queues()
        self.start_global_hotkey_listener()

        self.log_queue.put(f"🖥️ 检测显示器数量：{len(self.monitor_list)}")
        for idx, rect in enumerate(self.monitor_list):
            self.log_queue.put(f" 屏幕{idx+1}边界：{rect}")

    def build_menu(self):
        """顶部菜单栏：文件、剪辑"""
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        menu_file = tk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="文件", menu=menu_file)
        menu_file.add_command(label="加载文件回放（单轨道执行）", command=self.start_play)
        menu_file.add_command(label="导入时间轨道（进入剪辑器）", command=self.import_track_to_editor)
        menu_file.add_separator()
        menu_file.add_command(label="导出选中轨道", command=self.export_active_track)
        menu_file.add_command(label="导出全部合并轨道（用于回放）", command=self.export_merge_track)

        menu_clip = tk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="剪辑", menu=menu_clip)
        menu_clip.add_command(label="撤销 Ctrl+Z", command=self.do_undo)
        menu_clip.add_command(label="重做 Ctrl+Y", command=self.do_redo)
        menu_clip.add_separator()
        menu_clip.add_command(label="剪切选中片段", command=self.cmd_cut)
        menu_clip.add_command(label="复制选中片段", command=self.cmd_copy)
        menu_clip.add_command(label="粘贴", command=self.cmd_paste)
        menu_clip.add_command(label="删除选中片段", command=self.cmd_delete)

    def bind_hotkey(self):
        """全局快捷键 Ctrl+Z / Ctrl+Y"""
        self.root.bind("<Control-z>", lambda e: self.do_undo())
        self.root.bind("<Control-y>", lambda e: self.do_redo())

    def build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        coord_bar = ttk.Frame(main_frame)
        coord_bar.pack(fill=tk.X, pady=(0,6))
        ttk.Label(coord_bar, textvariable=self.mouse_coord_var, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        self.btn_full = ttk.Button(btn_frame, text="启动【全量录制】", command=self.start_full_record)
        self.btn_full.pack(side=tk.LEFT, padx=4)
        self.btn_simple = ttk.Button(btn_frame, text="启动【简易录制】", command=self.start_simple_record)
        self.btn_simple.pack(side=tk.LEFT, padx=4)
        self.btn_capture_offset = ttk.Button(btn_frame, text="两点拾取偏移", command=self.start_capture_offset)
        self.btn_capture_offset.pack(side=tk.LEFT, padx=4)
        self.btn_monitor_mouse = ttk.Button(btn_frame, text="开启坐标监视", command=self.toggle_mouse_monitor)
        self.btn_monitor_mouse.pack(side=tk.LEFT, padx=4)

        timeline_wrap = ttk.LabelFrame(main_frame, text="多轨道时间轴｜黄色=切割标记｜红色=回放游标｜鼠标拖拽框选片段")
        timeline_wrap.pack(fill=tk.BOTH, expand=True, pady=8)

        self.timeline = TimelineWidget(
            timeline_wrap,
            on_cut_change=self.on_timeline_cut_changed,
            on_playhead_jump=self.jump_playback_to_time,
            on_range_select=self.on_range_selected,
            on_clip_command=self.on_timeline_clip_command
        )
        self.timeline.pack(fill=tk.BOTH, expand=True)

        param_frame = ttk.Frame(main_frame)
        param_frame.pack(fill=tk.X, pady=6)
        ttk.Label(param_frame, text="循环次数(0=无限)：").pack(side=tk.LEFT)
        self.loop_var = tk.StringVar(value="1")
        ttk.Spinbox(param_frame, from_=0, to=9999, textvariable=self.loop_var, width=7).pack(side=tk.LEFT, padx=3)

        ttk.Label(param_frame, text=" 倒计时(秒)：").pack(side=tk.LEFT)
        self.countdown_var = tk.StringVar(value="3")
        ttk.Spinbox(param_frame, from_=0, to=AppConfig.MAX_COUNTDOWN, increment=0.5,
                    textvariable=self.countdown_var, width=7).pack(side=tk.LEFT, padx=3)

        ttk.Label(param_frame, text=" 倍速(0.01~100)：").pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value="1.0")
        ttk.Spinbox(param_frame, from_=AppConfig.MIN_SPEED, to=AppConfig.MAX_SPEED, increment=0.01,
                    textvariable=self.speed_var, width=7).pack(side=tk.LEFT, padx=3)

        offset_setting_frame = ttk.Frame(main_frame)
        offset_setting_frame.pack(fill=tk.X, pady=6)
        ttk.Label(offset_setting_frame, text="偏移总开关：").pack(side=tk.LEFT)
        self.offset_enable_var = tk.StringVar(value="启用偏移")
        cbo_switch = ttk.Combobox(offset_setting_frame, textvariable=self.offset_enable_var, state="readonly", width=10)
        cbo_switch["values"] = ("启用偏移", "不启用任何偏移")
        cbo_switch.pack(side=tk.LEFT, padx=3)

        ttk.Label(offset_setting_frame, text="偏移模式：").pack(side=tk.LEFT)
        self.offset_mode_var = tk.StringVar(value=AppConfig.OFFSET_FIXED)
        cbo_mode = ttk.Combobox(offset_setting_frame, textvariable=self.offset_mode_var, state="readonly", width=12)
        cbo_mode["values"] = (AppConfig.OFFSET_FIXED, AppConfig.OFFSET_ITER)
        cbo_mode.pack(side=tk.LEFT, padx=3)

        ttk.Label(offset_setting_frame, text=" 偏移起始轮次：").pack(side=tk.LEFT)
        self.offset_round_var = tk.StringVar(value="1")
        ttk.Spinbox(offset_setting_frame, from_=1, to=9999, textvariable=self.offset_round_var, width=6).pack(side=tk.LEFT, padx=3)

        ttk.Label(offset_setting_frame, text=" X偏移：").pack(side=tk.LEFT)
        self.off_x_var = tk.StringVar(value="0")
        ttk.Spinbox(offset_setting_frame, from_=-9999, to=9999, textvariable=self.off_x_var, width=6).pack(side=tk.LEFT, padx=3)

        ttk.Label(offset_setting_frame, text=" Y偏移：").pack(side=tk.LEFT)
        self.off_y_var = tk.StringVar(value="0")
        ttk.Spinbox(offset_setting_frame, from_=-9999, to=9999, textvariable=self.off_y_var, width=6).pack(side=tk.LEFT, padx=3)

        ttk.Label(offset_setting_frame, text=" 生效点击序号：").pack(side=tk.LEFT)
        self.target_clicks_var = tk.StringVar(value="")
        ttk.Entry(offset_setting_frame, textvariable=self.target_clicks_var, width=14).pack(side=tk.LEFT, padx=3)
        ttk.Label(offset_setting_frame, text="（例：2,5,8 或 1-10，空=全部）").pack(side=tk.LEFT)

        ttk.Label(offset_setting_frame, text=" 禁用点击序号：").pack(side=tk.LEFT, padx=(10,0))
        self.exclude_clicks_var = tk.StringVar(value="")
        ttk.Entry(offset_setting_frame, textvariable=self.exclude_clicks_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(offset_setting_frame, text="（支持区间20-25）").pack(side=tk.LEFT)

        hint_frame = ttk.Frame(main_frame)
        hint_frame.pack(fill=tk.X, pady=6)
        ttk.Label(hint_frame, text="提示：F5快速回放｜F9录制暂停｜ESC终止任务｜Ctrl+Z撤销剪辑").pack(side=tk.LEFT)

        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, wrap=tk.WORD)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ========== 剪辑回调函数 ==========
    def refresh_timeline_view(self):
        """将剪辑模型所有轨道推送至视图刷新"""
        self.timeline.set_tracks(self.clip_editor.tracks)

    def on_range_selected(self, track_id, start_idx, end_idx):
        pass

    def on_timeline_clip_command(self, cmd_type, track_id, start_idx, end_idx):
        track = self.clip_editor.get_track_by_id(track_id)
        if not track:
            self.log_queue.put("⚠️ 未找到目标轨道")
            return
        if cmd_type == "cut":
            self.clip_editor.cut_range(track, start_idx, end_idx)
        elif cmd_type == "copy":
            self.clip_editor.copy_range(track, start_idx, end_idx)
        elif cmd_type == "delete":
            self.clip_editor.delete_range(track, start_idx, end_idx)
        self.refresh_timeline_view()

    def do_undo(self):
        if self.clip_editor.undo():
            self.log_queue.put("↩️ 撤销成功")
            self.refresh_timeline_view()
        else:
            self.log_queue.put("⚠️ 无可撤销操作")

    def do_redo(self):
        if self.clip_editor.redo():
            self.log_queue.put("↪️ 重做成功")
            self.refresh_timeline_view()
        else:
            self.log_queue.put("⚠️ 无可重做操作")

    def cmd_cut(self):
        track = self.clip_editor.get_active_track()
        if not track:
            self.log_queue.put("⚠️ 请先选中轨道与片段")
            return
        # 简化版本：需要先框选，正式版本需要保存选中区间
        self.log_queue.put("提示：请先在时间轴鼠标拖拽框选片段")

    def cmd_copy(self):
        track = self.clip_editor.get_active_track()
        if not track:
            self.log_queue.put("⚠️ 请先选中轨道与片段")
            return
        self.log_queue.put("提示：请先在时间轴鼠标拖拽框选片段")

    def cmd_paste(self):
        track = self.clip_editor.get_active_track()
        if not track:
            self.log_queue.put("⚠️ 请先选中目标轨道")
            return
        if self.clip_editor.paste(track, len(track.actions)):
            self.log_queue.put("📋 粘贴至轨道末尾完成")
            self.refresh_timeline_view()
        else:
            self.log_queue.put("⚠️ 剪贴板为空")

    def cmd_delete(self):
        track = self.clip_editor.get_active_track()
        if not track:
            self.log_queue.put("⚠️ 请先选中轨道与片段")
            return
        self.log_queue.put("提示：请先框选片段")

    # ========== 文件导入导出 ==========
    def import_track_to_editor(self):
        """【导入时间轨道】仅加入剪辑模型，不自动回放"""
        path = filedialog.askopenfilename(filetypes=[("录制脚本", "*.json")])
        if not path:
            return
        try:
            new_track = FileUtil.track_from_json(path)
            self.clip_editor.add_track(new_track)
            self.log_queue.put(f"📥 成功导入轨道：{new_track.name}，动作数量：{len(new_track.actions)}")
            self.refresh_timeline_view()
        except Exception as e:
            self.log_queue.put(f"⚠️ 导入轨道失败：{str(e)}")

    def export_active_track(self):
        track = self.clip_editor.get_active_track()
        if not track:
            messagebox.showwarning("提示", "无激活轨道")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON脚本", "*.json")])
        if save_path:
            FileUtil.track_save_json(track, save_path)
            self.log_queue.put(f"💾 轨道导出完成：{save_path}")

    def export_merge_track(self):
        if not self.clip_editor.tracks:
            messagebox.showwarning("提示", "没有轨道可合并")
            return
        merged_track = self.clip_editor.merge_all_tracks()
        save_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON脚本", "*.json")])
        if save_path:
            FileUtil.track_save_json(merged_track, save_path)
            self.log_queue.put(f"💾 全部轨道合并导出完成，总动作：{len(merged_track.actions)}，路径：{save_path}")

    # ========== 录制相关 ==========
    def on_timeline_cut_changed(self, cut_index):
        if self.recorder_instance:
            self.recorder_instance.set_cut_position(cut_index)
            self.log_queue.put(f"✅ 录制截断点设置：下标{cut_index}，历史动作保留，新录制内容追加")

    def start_full_record(self):
        self.set_btn_state(tk.DISABLED)
        self.is_recording_now = True
        self.timeline.clear_view()
        self.log_queue.put("📌 准备开启全量录制")
        def task():
            self.recorder_instance = RecorderCore(AppConfig.MODE_FULL, self.log_queue, self.ui_action_queue)
            self.recorder_instance.start_record()
            self.recorder_instance = None
            self.is_recording_now = False
            self.root.after(200, lambda: self.set_btn_state(tk.NORMAL))
        threading.Thread(target=task, daemon=True).start()

    def start_simple_record(self):
        self.set_btn_state(tk.DISABLED)
        self.is_recording_now = True
        self.timeline.clear_view()
        self.log_queue.put("📌 准备开启简易录制")
        def task():
            self.recorder_instance = RecorderCore(AppConfig.MODE_SIMPLE, self.log_queue, self.ui_action_queue)
            self.recorder_instance.start_record()
            self.recorder_instance = None
            self.is_recording_now = False
            self.root.after(200, lambda: self.set_btn_state(tk.NORMAL))
        threading.Thread(target=task, daemon=True).start()

    # ========== 回放seek跳转 ==========
    def jump_playback_to_time(self, target_abs_time: float):
        idx = self.player.seek_playback(target_abs_time)
        self.log_queue.put(f"🎯 请求跳转至时间 {target_abs_time:.2f}s，最近动作下标 {idx}")

    def start_play(self):
        """加载文件回放（不进入剪辑器，直接送入PlayerCore执行）"""
        params = self._get_play_params()
        if params is None:
            messagebox.showerror("参数错误", "检查回放参数！")
            return
        path = filedialog.askopenfilename(filetypes=[("录制脚本", "*.json")])
        if not path:
            return
        self.last_play_file = path
        try:
            action_data = FileUtil.load_recording(path)
            self.timeline.set_tracks([])
            self.log_queue.put(f"📂 载入回放脚本，总动作 {len(action_data)}")
        except Exception as e:
            self.log_queue.put(f"⚠️ 文件载入失败：{e}")
            return
        self.set_btn_state(tk.DISABLED)
        loop_num, wait_sec, speed, off_round, off_mode, ox, oy, target_set, enable_off, exclude_set = params
        threading.Thread(target=self.player.play_recording,
                         args=(action_data, loop_num, wait_sec, speed, off_round, off_mode, ox, oy, target_set, enable_off, exclude_set),
                         daemon=True).start()

    def quick_play_last(self):
        if self.is_working:
            self.log_queue.put("⚠️ 当前任务运行中，等待结束！")
            return
        if not self.last_play_file:
            self.log_queue.put("⚠️ 无最近回放文件")
            return
        self.log_queue.put(f"\n🎯 F5快速回放：{self.last_play_file}")
        self.set_btn_state(tk.DISABLED)
        params = self._get_play_params()
        if params is None:
            self.set_btn_state(tk.NORMAL)
            return
        loop_num, wait_sec, speed, off_round, off_mode, ox, oy, target_set, enable_off, exclude_set = params
        try:
            action_data = FileUtil.load_recording(self.last_play_file)
        except Exception as e:
            self.log_queue.put(f"⚠️ 文件读取失败 {e}")
            self.set_btn_state(tk.NORMAL)
            return
        threading.Thread(target=self.player.play_recording,
                         args=(action_data, loop_num, wait_sec, speed, off_round, off_mode, ox, oy, target_set, enable_off, exclude_set),
                         daemon=True).start()

    def start_capture_offset(self):
        if self.is_working or self.is_capturing_offset:
            self.log_queue.put("⚠️ 任务运行中")
            return
        self.is_capturing_offset = True
        self.set_btn_state(tk.DISABLED)
        self.log_queue.put("\n🎯 拾取偏移：先后点击两处坐标，ESC取消")
        def capture_thread():
            points = []
            def on_click(x,y,btn,pressed):
                nonlocal points
                if not pressed or btn != mouse.Button.left:
                    return
                points.append((x,y))
                sid = ScreenUtil.get_cursor_screen_index(x,y,self.monitor_list)
                self.log_queue.put(f"✅ 拾取点位{len(points)} X={x} Y={y} 屏幕{sid}")
                if len(points)>=2:
                    return False
            def on_key(key):
                if key == AppConfig.EXIT_HOTKEY:
                    points.clear()
                    return False
            ml = mouse.Listener(on_click=on_click)
            kl = keyboard.Listener(on_press=on_key)
            ml.start()
            kl.start()
            ml.join()
            kl.stop()
            if len(points)==2:
                (x1,y1),(x2,y2)=points
                dx = x2-x1
                dy = y2-y1
                self.root.after(0, lambda:self.off_x_var.set(str(dx)))
                self.root.after(0, lambda:self.off_y_var.set(str(dy)))
                self.log_queue.put(f"✅ 偏移计算完成 X={dx} Y={dy}")
            else:
                self.log_queue.put("❌ 拾取已取消")
            self.is_capturing_offset = False
            self.root.after(200, lambda:self.set_btn_state(tk.NORMAL))
        threading.Thread(target=capture_thread, daemon=True).start()

    def toggle_mouse_monitor(self):
        if not self.mouse_monitor_running:
            self.mouse_monitor_running = True
            self.btn_monitor_mouse.config(text="关闭坐标监视")
            self.log_queue.put("🖱️ 坐标监视器已开启")
            def loop():
                while self.mouse_monitor_running:
                    x,y = self.mouse_ctrl.position
                    sid = ScreenUtil.get_cursor_screen_index(x,y,self.monitor_list)
                    self.root.after(0, lambda xv=x,yv=y,sidv=sid:
                                    self.mouse_coord_var.set(f"鼠标坐标：X={xv},Y={yv}｜屏幕{sidv}"))
                    import time
                    time.sleep(0.18)
            threading.Thread(target=loop, daemon=True).start()
        else:
            self.mouse_monitor_running = False
            self.btn_monitor_mouse.config(text="开启坐标监视")
            self.mouse_coord_var.set("鼠标坐标：未开启监视")
            self.log_queue.put("🖱️ 坐标监视器关闭")

    def write_log(self, msg):
        self.log_text.insert(tk.END, msg+"\n")
        self.log_text.see(tk.END)

    def poll_all_queues(self):
        while not self.log_queue.empty():
            item = self.log_queue.get()
            if isinstance(item, tuple):
                cmd, payload = item[0], item[1]
                if cmd == "PLAY_ABSTIME":
                    self.timeline.set_play_abstime(payload)
            else:
                self.write_log(item)
        while not self.ui_action_queue.empty():
            act = self.ui_action_queue.get()
            # 实时录制内容自动新建轨道加入剪辑器
            if not self.clip_editor.tracks:
                tr = Track(name="实时录制轨道", color="#88ee88")
                self.clip_editor.add_track(tr)
            active_tr = self.clip_editor.get_active_track()
            active_tr.actions.append(act)
            self.refresh_timeline_view()
        self.root.after(50, self.poll_all_queues)

    def set_btn_state(self, state):
        self.btn_full.config(state=state)
        self.btn_simple.config(state=state)
        self.btn_play.config(state=state)
        self.btn_capture_offset.config(state=state)
        self.is_working = (state == tk.DISABLED)

    def _get_play_params(self):
        try:
            loop_num = int(self.loop_var.get())
            wait_sec = float(self.countdown_var.get())
            speed = float(self.speed_var.get())
            off_round = int(self.offset_round_var.get())
            ox = int(self.off_x_var.get())
            oy = int(self.off_y_var.get())
        except:
            return None
        if wait_sec <0 or wait_sec>AppConfig.MAX_COUNTDOWN:
            return None
        if not (AppConfig.MIN_SPEED <= speed <= AppConfig.MAX_SPEED):
            return None
        if off_round <1:
            return None
        target_set = parse_number_set(self.target_clicks_var.get())
        exclude_set = parse_number_set(self.exclude_clicks_var.get())
        enable_off = (self.offset_enable_var.get() == "启用偏移")
        off_mode = self.offset_mode_var.get()
        return loop_num, wait_sec, speed, off_round, off_mode, ox, oy, target_set, enable_off, exclude_set

    def start_global_hotkey_listener(self):
        def listen():
            def on_key(key):
                if key == AppConfig.PLAY_LAST_HOTKEY:
                    self.root.after(0, self.quick_play_last)
            lst = keyboard.Listener(on_press=on_key)
            lst.run()
        threading.Thread(target=listen, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = MacroGUI(root)
    root.mainloop()