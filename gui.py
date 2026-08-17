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
class MacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("键鼠宏录制工具 GUI版 | 模块化")
        self.root.geometry("1120x820")
        self.log_queue = queue.Queue()
        self.ui_action_queue = queue.Queue()
        self.player = PlayerCore(self.log_queue)
        self.last_play_file = None
        self.is_working = False
        self.is_capturing_offset = False
        self.is_recording_now = False
        self.mouse_monitor_running = False
        self.mouse_ctrl = MouseCtrl()
        self.mouse_coord_var = tk.StringVar(value="鼠标坐标：未开启监视")
        self.monitor_list = ScreenUtil.get_all_monitors()
        self.timeline = None
        self.recorder_instance = None
        # 新增：偏移文件存储列表
        self.offset_file_list: list[tuple[int, int]] = []
        self.build_ui()
        self.poll_all_queues()
        self.start_global_hotkey_listener()
        # 初始化偏移控件为可用
        self.set_offset_ctrl_state(True)
        self.log_queue.put(f"🖥️ 检测到显示器总数：{len(self.monitor_list)}")
        for idx, rect in enumerate(self.monitor_list):
            self.log_queue.put(f" 屏幕{idx+1}边界(left,top,right,bottom)：{rect}")

    def set_offset_ctrl_state(self, enable: bool):
        """统一控制偏移模式下拉、X/Y输入框启用/置灰"""
        state = "normal" if enable else "disabled"
        self.cbo_offset_mode.config(state=state)
        self.spin_ox.config(state=state)
        self.spin_oy.config(state=state)

    def build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        coord_bar = ttk.Frame(main_frame)
        coord_bar.pack(fill=tk.X, pady=(0,6))
        ttk.Label(coord_bar, textvariable=self.mouse_coord_var, font=("Microsoft YaHei",10,"bold")).pack(side=tk.LEFT)
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        self.btn_full = ttk.Button(btn_frame, text="启动【全量录制】", command=self.start_full_record)
        self.btn_full.pack(side=tk.LEFT, padx=4)
        self.btn_simple = ttk.Button(btn_frame, text="启动【简易录制】", command=self.start_simple_record)
        self.btn_simple.pack(side=tk.LEFT, padx=4)
        self.btn_play = ttk.Button(btn_frame, text="加载文件回放", command=self.start_play)
        self.btn_play.pack(side=tk.LEFT, padx=4)
        self.btn_capture_offset = ttk.Button(btn_frame, text="两点拾取偏移", command=self.start_capture_offset)
        self.btn_capture_offset.pack(side=tk.LEFT, padx=4)
        self.btn_monitor_mouse = ttk.Button(btn_frame, text="开启坐标监视", command=self.toggle_mouse_monitor)
        self.btn_monitor_mouse.pack(side=tk.LEFT, padx=4)
        timeline_wrap = ttk.LabelFrame(main_frame, text="录制时间轴（鼠标点击选定切割位置 | 圆点悬浮查看详情）")
        timeline_wrap.pack(fill=tk.X, pady=8)
        self.timeline = TimelineWidget(
            timeline_wrap,
            on_cut_position_change=self.on_timeline_cut_changed
        )
        self.timeline.pack(fill=tk.X, padx=2, pady=2)
        param_frame = ttk.Frame(main_frame)
        param_frame.pack(fill=tk.X, pady=6)
        ttk.Label(param_frame, text="循环次数(0=无限)：").pack(side=tk.LEFT)
        self.loop_var = tk.StringVar(value="1")
        spin_loop = ttk.Spinbox(param_frame, from_=0, to=9999, textvariable=self.loop_var, width=7)
        spin_loop.pack(side=tk.LEFT, padx=3)
        ttk.Label(param_frame, text=" 倒计时(秒)：").pack(side=tk.LEFT)
        self.countdown_var = tk.StringVar(value="3")
        spin_count = ttk.Spinbox(param_frame, from_=0, to=AppConfig.MAX_COUNTDOWN, increment=0.5,
                                 textvariable=self.countdown_var, width=7)
        spin_count.pack(side=tk.LEFT, padx=3)
        ttk.Label(param_frame, text=" 倍速(0.01~100)：").pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value="1.0")
        spin_speed = ttk.Spinbox(param_frame, from_=AppConfig.MIN_SPEED, to=AppConfig.MAX_SPEED, increment=0.01,
                                 textvariable=self.speed_var, width=7)
        spin_speed.pack(side=tk.LEFT, padx=3)
        offset_setting_frame = ttk.Frame(main_frame)
        offset_setting_frame.pack(fill=tk.X, pady=6)
        ttk.Label(offset_setting_frame, text="偏移总开关：").pack(side=tk.LEFT)
        self.offset_enable_var = tk.StringVar(value="启用偏移")
        cbo_offset_switch = ttk.Combobox(offset_setting_frame, textvariable=self.offset_enable_var, state="readonly", width=10)
        cbo_offset_switch["values"] = ("启用偏移", "不启用任何偏移")
        cbo_offset_switch.pack(side=tk.LEFT, padx=3)
        # 新增首轮偏移复选框
        self.first_round_offset_var = tk.BooleanVar(value=False)
        chk_first_off = ttk.Checkbutton(offset_setting_frame, text="首轮回放启用偏移", variable=self.first_round_offset_var)
        chk_first_off.pack(side=tk.LEFT, padx=6)
        ttk.Label(offset_setting_frame, text="偏移模式：").pack(side=tk.LEFT)
        self.offset_mode_var = tk.StringVar(value=AppConfig.OFFSET_FIXED)
        self.cbo_offset_mode = ttk.Combobox(offset_setting_frame, textvariable=self.offset_mode_var, state="readonly", width=12)
        self.cbo_offset_mode["values"] = (AppConfig.OFFSET_FIXED, AppConfig.OFFSET_ITER)
        self.cbo_offset_mode.pack(side=tk.LEFT, padx=3)
        ttk.Label(offset_setting_frame, text=" 偏移起始轮次：").pack(side=tk.LEFT)
        self.offset_round_var = tk.StringVar(value="2")
        spin_off_round = ttk.Spinbox(offset_setting_frame, from_=1, to=9999, textvariable=self.offset_round_var, width=6)
        spin_off_round.pack(side=tk.LEFT, padx=3)
        ttk.Label(offset_setting_frame, text=" X偏移：").pack(side=tk.LEFT)
        self.off_x_var = tk.StringVar(value="0")
        self.spin_ox = ttk.Spinbox(offset_setting_frame, from_=-9999, to=9999, textvariable=self.off_x_var, width=6)
        self.spin_ox.pack(side=tk.LEFT, padx=3)
        ttk.Label(offset_setting_frame, text=" Y偏移：").pack(side=tk.LEFT)
        self.off_y_var = tk.StringVar(value="0")
        self.spin_oy = ttk.Spinbox(offset_setting_frame, from_=-9999, to=9999, textvariable=self.off_y_var, width=6)
        self.spin_oy.pack(side=tk.LEFT, padx=3)
        # 加载偏移文件行
        file_offset_frame = ttk.Frame(main_frame)
        file_offset_frame.pack(fill=tk.X, pady=(0,6))
        self.load_offset_btn = ttk.Button(file_offset_frame, text="加载自定义偏移文件(txt)", command=self.load_offset_file_action)
        self.load_offset_btn.pack(side=tk.LEFT)
        # 新增清空偏移按钮
        self.clear_offset_btn = ttk.Button(file_offset_frame, text="清空偏移文件", command=self.clear_offset_file_action)
        self.clear_offset_btn.pack(side=tk.LEFT, padx=5)
        self.offset_file_info_var = tk.StringVar(value="未加载偏移文件")
        ttk.Label(file_offset_frame, textvariable=self.offset_file_info_var, foreground="#0066cc").pack(side=tk.LEFT, padx=10)
        ttk.Label(offset_setting_frame, text=" 生效点击序号：").pack(side=tk.LEFT)
        self.target_clicks_var = tk.StringVar(value="")
        entry_target_clicks = ttk.Entry(offset_setting_frame, textvariable=self.target_clicks_var, width=14)
        entry_target_clicks.pack(side=tk.LEFT, padx=3)
        ttk.Label(offset_setting_frame, text="（例：2,5,6 或 2-5，空=全部点击生效）").pack(side=tk.LEFT)
        ttk.Label(offset_setting_frame, text=" 禁用点击序号：").pack(side=tk.LEFT, padx=(10,0))
        self.exclude_clicks_var = tk.StringVar(value="")
        entry_exclude = ttk.Entry(offset_setting_frame, textvariable=self.exclude_clicks_var, width=10)
        entry_exclude.pack(side=tk.LEFT, padx=3)
        ttk.Label(offset_setting_frame, text="（例：22,33）").pack(side=tk.LEFT)
        hint_frame = ttk.Frame(main_frame)
        hint_frame.pack(fill=tk.X, pady=6)
        ttk.Label(hint_frame, text="操作提示：F1开始录制 | F2终止录制/回放/拾取 | F5=快速回放 | F9录制暂停/继续").pack(side=tk.LEFT) 
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, wrap=tk.WORD)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT)

    # 清空偏移文件
    def clear_offset_file_action(self):
        self.offset_file_list = []
        self.offset_file_info_var.set("未加载偏移文件")
        self.set_offset_ctrl_state(True)
        self.log_queue.put("已清空偏移文件，偏移模式、X/Y输入框恢复可用")

    # 加载偏移文件按钮事件
    def load_offset_file_action(self):
        path = filedialog.askopenfilename(
            filetypes=[("偏移坐标文本", "*.txt"), ("所有文件", "*")]
        )
        if not path:
            return
        try:
            offset_data = FileUtil.load_offset_file(path)
            if not offset_data:
                self.log_queue.put("⚠️ 偏移文件内无有效X,Y坐标数据")
                self.offset_file_info_var.set("无有效偏移数据")
                self.offset_file_list = []
                self.set_offset_ctrl_state(True)
                return
            self.offset_file_list = offset_data
            show_text = f"已加载 {len(offset_data)} 组偏移坐标"
            self.offset_file_info_var.set(show_text)
            # 加载成功 → 置灰偏移模式、X/Y输入框
            self.set_offset_ctrl_state(False)
            self.log_queue.put(f"✅ 加载偏移文件成功，共{len(offset_data)}套坐标：{offset_data}")
            self.log_queue.put("提示：当前使用文件偏移，偏移模式、X/Y输入框已禁用，修改无效")
        except Exception as e:
            self.log_queue.put(f"❌ 读取偏移文件失败：{str(e)}")
            self.offset_file_info_var.set("文件读取失败")
            self.offset_file_list = []
            self.set_offset_ctrl_state(True)

    def on_timeline_cut_changed(self, cut_index):
        if self.recorder_instance:
            self.recorder_instance.set_cut_position(cut_index)
            self.log_queue.put(f"✅ 已设置录制截断点：索引{cut_index}，后续录制将从该位置追加")
        full_data = self.timeline.action_data
        if cut_index is not None and 0 <= cut_index < len(full_data):
            self.timeline.set_data(full_data[:cut_index])

    def toggle_mouse_monitor(self):
        if not self.mouse_monitor_running:
            self.mouse_monitor_running = True
            self.btn_monitor_mouse.config(text="关闭坐标监视")
            self.log_queue.put("🖱️ 鼠标坐标监视器【已开启】")
            def monitor_loop():
                while self.mouse_monitor_running:
                    x, y = self.mouse_ctrl.position
                    screen_id = ScreenUtil.get_cursor_screen_index(x, y, self.monitor_list)
                    self.root.after(0, lambda xv=x, yv=y, sid=screen_id:
                                    self.mouse_coord_var.set(f"鼠标坐标：X={xv} , Y={yv} | 当前屏幕：{sid}"))
                    import time
                    time.sleep(0.18)
            threading.Thread(target=monitor_loop, daemon=True).start()
        else:
            self.mouse_monitor_running = False
            self.btn_monitor_mouse.config(text="开启坐标监视")
            self.mouse_coord_var.set("鼠标坐标：未开启监视")
            self.log_queue.put("🖱️ 鼠标坐标监视器【已关闭】")

    def write_log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def poll_all_queues(self):
        while not self.log_queue.empty():
            item = self.log_queue.get()
            if isinstance(item, tuple) and item[0] == "PLAY_INDEX":
                act_idx = item[1]
                self.timeline.set_play_index(act_idx)
            else:
                self.write_log(item)
        while not self.ui_action_queue.empty():
            act = self.ui_action_queue.get()
            self.timeline.append_action(act)
        self.root.after(50, self.poll_all_queues)

    def set_btn_state(self, state):
        self.btn_full.config(state=state)
        self.btn_simple.config(state=state)
        self.btn_play.config(state=state)
        self.btn_capture_offset.config(state=state)
        self.is_working = (state == tk.DISABLED)

    def start_full_record(self):
        self.set_btn_state(tk.DISABLED)
        self.is_recording_now = True
        self.timeline.clear()
        self.log_queue.put("📌 准备新一轮录制，已自动清空时间轴历史动作")
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
        self.timeline.clear()
        self.log_queue.put("📌 准备新一轮录制，已自动清空时间轴历史动作")
        def task():
            self.recorder_instance = RecorderCore(AppConfig.MODE_SIMPLE, self.log_queue, self.ui_action_queue)
            self.recorder_instance.start_record()
            self.recorder_instance = None
            self.is_recording_now = False
            self.root.after(200, lambda: self.set_btn_state(tk.NORMAL))
        threading.Thread(target=task, daemon=True).start()

    def start_capture_offset(self):
        if self.is_working or self.is_capturing_offset:
            self.log_queue.put("⚠️ 正在执行任务或正在拾取偏移！")
            return
        self.is_capturing_offset = True
        self.set_btn_state(tk.DISABLED)
        self.log_queue.put("\n🎯【拾取偏移】请先后点击屏幕两个目标位置，ESC取消拾取")
        def capture_thread():
            points = []
            def on_click(x, y, button, pressed):
                nonlocal points
                if not pressed or button != mouse.Button.left:
                    return
                points.append((x, y))
                screen_id = ScreenUtil.get_cursor_screen_index(x, y, self.monitor_list)
                self.log_queue.put(f"✅ 已拾取点位{len(points)}：X={x}, Y={y} 屏幕{screen_id}")
                if len(points) >= 2:
                    return False
            def on_key(key):
                if key == AppConfig.EXIT_HOTKEY:
                    points.clear()
                    return False
            mouse_list = mouse.Listener(on_click=on_click)
            key_list = keyboard.Listener(on_press=on_key)
            mouse_list.start()
            key_list.start()
            mouse_list.join()
            key_list.stop()
            if len(points) == 2:
                (x1, y1), (x2, y2) = points
                dx = x2 - x1
                dy = y2 - y1
                self.root.after(0, lambda: self.off_x_var.set(str(dx)))
                self.root.after(0, lambda: self.off_y_var.set(str(dy)))
                self.log_queue.put(f"✅ 自动计算偏移完成：基础X偏移={dx}，基础Y偏移={dy}")
            else:
                self.log_queue.put("❌ 拾取已取消或点位不足")
            self.is_capturing_offset = False
            self.root.after(200, lambda: self.set_btn_state(tk.NORMAL))
        threading.Thread(target=capture_thread, daemon=True).start()

    def _parse_target_click_indexes(self):
        expr_enable = self.target_clicks_var.get().strip()
        expr_exclude = self.exclude_clicks_var.get().strip()
        enable_set = parse_number_set(expr_enable)
        exclude_set = parse_number_set(expr_exclude)
        if not enable_set:
            final_set = set()
        else:
            final_set = enable_set - exclude_set
        return final_set, exclude_set

    def _get_play_params(self):
        try:
            loop_num = int(self.loop_var.get())
        except ValueError:
            self.log_queue.put("❌ 循环次数输入非法！")
            return None
        try:
            wait_sec = float(self.countdown_var.get())
        except ValueError:
            self.log_queue.put("❌ 倒计时输入非法！")
            return None
        try:
            speed = float(self.speed_var.get())
        except ValueError:
            self.log_queue.put("❌ 倍速输入非法！")
            return None
        try:
            off_round = int(self.offset_round_var.get())
            ox = int(self.off_x_var.get())
            oy = int(self.off_y_var.get())
        except ValueError:
            self.log_queue.put("❌ 偏移参数必须为整数！")
            return None
        if wait_sec < 0 or wait_sec > AppConfig.MAX_COUNTDOWN:
            self.log_queue.put(f"❌ 倒计时范围 0~{AppConfig.MAX_COUNTDOWN}！")
            return None
        if not (AppConfig.MIN_SPEED <= speed <= AppConfig.MAX_SPEED):
            self.log_queue.put(f"❌ 倍速范围 {AppConfig.MIN_SPEED} ~ {AppConfig.MAX_SPEED}！")
            return None
        if off_round < 1:
            self.log_queue.put("❌ 偏移起始轮次最小为1！")
            return None
        target_set, exclude_set = self._parse_target_click_indexes()
        offset_mode = self.offset_mode_var.get()
        enable_offset = (self.offset_enable_var.get() == "启用偏移")
        first_round_off = self.first_round_offset_var.get()
        file_off_list = self.offset_file_list
        return (loop_num, wait_sec, speed, off_round, offset_mode, ox, oy, target_set, enable_offset, exclude_set, first_round_off, file_off_list)

    def _run_play_task(self, filepath):
        params = self._get_play_params()
        if params is None:
            self.root.after(200, lambda: self.set_btn_state(tk.NORMAL))
            return
        loop_num, wait_sec, speed, off_round, offset_mode, ox, oy, target_set, enable_offset, exclude_set, first_round_off, file_off_list = params
        self.player.play_recording(
            filepath,
            loop_num,
            wait_sec,
            speed,
            off_round,
            offset_mode,
            ox,
            oy,
            target_set,
            enable_offset,
            exclude_set,
            first_round_off,
            file_off_list
        )
        self.root.after(200, lambda: self.set_btn_state(tk.NORMAL))

    def start_play(self):
        params = self._get_play_params()
        if params is None:
            messagebox.showerror("参数错误", "检查所有回放输入！")
            return
        file_path = filedialog.askopenfilename(
            filetypes=[("录制脚本", "*.json"), ("所有文件", "*")]
        )
        if not file_path:
            return
        self.last_play_file = file_path
        try:
            loaded_data = FileUtil.load_recording(file_path)
            self.timeline.set_data(loaded_data)
            self.log_queue.put(f"📂 已载入脚本，动作总数：{len(loaded_data)}，时间轴已刷新")
        except Exception as e:
            self.log_queue.put(f"⚠️ 载入预览失败：{e}")
        self.set_btn_state(tk.DISABLED)
        threading.Thread(target=self._run_play_task, args=(file_path,), daemon=True).start()

    def quick_play_last(self):
        if self.is_working:
            self.log_queue.put("⚠️ 当前正在执行任务，请等待任务结束！")
            return
        if not self.last_play_file:
            self.log_queue.put("⚠️ 暂无历史回放文件，请先手动加载脚本！")
            return
        self.log_queue.put(f"\n🎯 F5触发：快速回放最近文件 {self.last_play_file}")
        self.set_btn_state(tk.DISABLED)
        threading.Thread(target=self._run_play_task, args=(self.last_play_file,), daemon=True).start()

    def start_global_hotkey_listener(self):
        def listen_hotkey():
            def on_key(key):
                if key == AppConfig.PLAY_LAST_HOTKEY:
                    self.root.after(0, self.quick_play_last)
            listener = keyboard.Listener(on_press=on_key)
            listener.run()
        threading.Thread(target=listen_hotkey, daemon=True).start()