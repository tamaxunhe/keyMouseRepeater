# core.py
import time
import json
import queue
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseCtrl, Button
from pynput.keyboard import Controller as KeyCtrl, Key
from config import AppConfig
from util import ActionConverter, FileUtil

class RecorderCore:
    STATE_WAIT_START = "wait_start"
    STATE_RECORDING = "recording"
    STATE_REC_PAUSED = "rec_paused"
    def __init__(self, record_mode: str, log_queue: queue.Queue, ui_action_queue: queue.Queue):
        self.record_mode = record_mode
        self.action_list = []
        self.last_time = 0.0
        self.rec_state = self.STATE_WAIT_START
        self.ignore_next_enter_release = False
        self.last_click_pos = (None, None)
        self.is_dragging = False
        self.key_down_map = {}
        self.log_queue = log_queue
        self.ui_action_queue = ui_action_queue
        self.mouse_ctrl = MouseCtrl()
        self.key_ctrl = KeyCtrl
        self.rec_start_ts = 0.0
        self.pause_start = 0.0
        self.pause_total = 0.0
        self.cut_index = None
        # 双击缓存
        self.last_click_ts = 0.0
        self.last_click_info = None
        # 修饰键按下集合
        self.pressed_modifiers = set()

    def reset_recorder(self):
        self.action_list.clear()
        self.last_time = time.perf_counter()
        self.rec_state = self.STATE_WAIT_START
        self.ignore_next_enter_release = False
        self.last_click_pos = (None, None)
        self.is_dragging = False
        self.key_down_map.clear()
        self.rec_start_ts = 0.0
        self.pause_start = 0.0
        self.pause_total = 0.0
        self.cut_index = None
        self.last_click_ts = 0.0
        self.last_click_info = None
        self.pressed_modifiers.clear()

    def set_cut_position(self, idx):
        if idx is None or 0 <= idx <= len(self.action_list):
            self.cut_index = idx

    def toggle_pause(self):
        if self.rec_state == self.STATE_RECORDING:
            self.rec_state = self.STATE_REC_PAUSED
            self.pause_start = time.perf_counter()
            self.log_queue.put("⏸️ 录制【暂停】，按F9继续录制")
            return False
        elif self.rec_state == self.STATE_REC_PAUSED:
            pause_dur = time.perf_counter() - self.pause_start
            self.pause_total += pause_dur
            self.last_time = time.perf_counter()
            self.rec_state = self.STATE_RECORDING
            self.log_queue.put(f"▶️ 录制【继续】，本次暂停时长 {pause_dur:.2f}s")
            return True

    def _calc_delay(self) -> float:
        delay = round(time.perf_counter() - self.last_time, AppConfig.TIME_PRECISION)
        self.last_time = time.perf_counter()
        return delay

    def _get_abs_time(self):
        real_now = time.perf_counter()
        return round((real_now - self.rec_start_ts - self.pause_total), AppConfig.TIME_PRECISION)

    def _push_action(self, act_dict):
        act_dict["modifiers"] = sorted([str(k) for k in self.pressed_modifiers])
        self.action_list.append(act_dict)
        self.ui_action_queue.put(act_dict)

    def on_mouse_move(self, x: int, y: int):
        if self.rec_state != self.STATE_RECORDING:
            return
        if self.record_mode == AppConfig.MODE_FULL:
            delay = self._calc_delay()
            abs_t = self._get_abs_time()
            self._push_action({"type": "mouse_move", "x": x, "y": y, "delay": delay, "abs_time": abs_t})
        else:
            if self.is_dragging:
                delay = self._calc_delay()
                abs_t = self._get_abs_time()
                self._push_action({"type": "mouse_move", "x": x, "y": y, "delay": delay, "abs_time": abs_t})

    def on_mouse_click(self, x: int, y: int, button: Button, pressed: bool):
        if self.rec_state != self.STATE_RECORDING:
            return
        now_ts = time.perf_counter()
        btn_name = ActionConverter.mouse_btn_to_str(button)

        # 双击判断逻辑（仅抬起时校验）
        if not pressed:
            curr_click = (x, y, btn_name)
            dx = abs(x - self.last_click_info[0]) if self.last_click_info else 9999
            dy = abs(y - self.last_click_info[1]) if self.last_click_info else 9999
            time_diff_ms = (now_ts - self.last_click_ts) * 1000
            if (self.last_click_info
                and self.last_click_info[2] == btn_name
                and dx <= AppConfig.DOUBLE_CLICK_POS_TOLERANCE
                and dy <= AppConfig.DOUBLE_CLICK_POS_TOLERANCE
                and time_diff_ms <= AppConfig.DOUBLE_CLICK_MS):
                # 移除上一条单击抬起，替换为双击动作
                if self.action_list and self.action_list[-1]["type"] == "mouse_click":
                    self.action_list.pop()
                    delay = self._calc_delay()
                    abs_t = self._get_abs_time()
                    self._push_action({
                        "type": "mouse_double_click",
                        "x": x, "y": y,
                        "button": btn_name,
                        "delay": delay,
                        "abs_time": abs_t
                    })
                    self.last_click_ts = 0.0
                    self.last_click_info = None
                    return
            self.last_click_ts = now_ts
            self.last_click_info = curr_click

        # 简易模式拖拽记录
        if self.record_mode == AppConfig.MODE_SIMPLE:
            if pressed:
                self.is_dragging = True
                if (x, y) != self.last_click_pos:
                    delay = self._calc_delay()
                    abs_t = self._get_abs_time()
                    self._push_action({"type": "mouse_move", "x": x, "y": y, "delay": delay, "abs_time": abs_t})
                    self.last_click_pos = (x, y)
            else:
                self.is_dragging = False

        delay = self._calc_delay()
        abs_t = self._get_abs_time()
        self._push_action({
            "type": "mouse_click", "x": x, "y": y,
            "button": btn_name, "pressed": pressed,
            "delay": delay, "abs_time": abs_t
        })

    def on_mouse_scroll(self, x: int, y: int, dx: int, dy: int):
        if self.rec_state != self.STATE_RECORDING:
            return
        if self.record_mode == AppConfig.MODE_SIMPLE:
            if (x, y) != self.last_click_pos:
                delay = self._calc_delay()
                abs_t = self._get_abs_time()
                self._push_action({"type": "mouse_move", "x": x, "y": y, "delay": delay, "abs_time": abs_t})
                self.last_click_pos = (x, y)
        delay = self._calc_delay()
        abs_t = self._get_abs_time()
        self._push_action({
            "type": "mouse_scroll", "x": x, "y": y,
            "dx": dx, "dy": dy, "delay": delay, "abs_time": abs_t
        })

    def on_key_press(self, key):
        # 获取当前快捷键
        stop_key = AppConfig.get_key(AppConfig.HOTKEYS["stop_record"])
        pause_key = AppConfig.get_key(AppConfig.HOTKEYS["pause_record"])
        start_key = AppConfig.get_key(AppConfig.HOTKEYS["start_record"])
        
        if key == stop_key:
            return False
        if key == pause_key:
            self.toggle_pause()
            return
        if self.rec_state == self.STATE_WAIT_START:
            if key == start_key:
                self.rec_state = self.STATE_RECORDING
                self.last_time = time.perf_counter()
                self.rec_start_ts = time.perf_counter()
                self.ignore_next_enter_release = True
                start_name = AppConfig.get_display_name(AppConfig.HOTKEYS["start_record"])
                self.log_queue.put(f"✅ 检测到{start_name}，正式开始录制操作！")
            return
        
        # 记录修饰键
        if key in AppConfig.MODIFIER_KEYS:
            self.pressed_modifiers.add(key)
        # 转换按键文本
        try:
            key_text = key.char
        except AttributeError:
            key_text = str(key)
        if key_text in AppConfig.CTRL_CHAR_MAP:
            key_text = AppConfig.CTRL_CHAR_MAP[key_text]
        if self.key_down_map.get(key_text, False):
            return
        self.key_down_map[key_text] = True
        delay = self._calc_delay()
        abs_t = self._get_abs_time()
        self._push_action({"type": "key_press", "key": key_text, "delay": delay, "abs_time": abs_t})

    def on_key_release(self, key):
        stop_key = AppConfig.get_key(AppConfig.HOTKEYS["stop_record"])
        pause_key = AppConfig.get_key(AppConfig.HOTKEYS["pause_record"])
        start_key = AppConfig.get_key(AppConfig.HOTKEYS["start_record"])
        
        if key == stop_key:
            return False
        if key == pause_key:
            return
        if self.ignore_next_enter_release and key == start_key:
            self.ignore_next_enter_release = False
            return
        if self.rec_state not in (self.STATE_RECORDING, self.STATE_REC_PAUSED):
            return
        # 移除修饰键标记
        if key in AppConfig.MODIFIER_KEYS:
            if key in self.pressed_modifiers:
                self.pressed_modifiers.remove(key)
        try:
            key_text = key.char
        except AttributeError:
            key_text = str(key)
        if key_text in AppConfig.CTRL_CHAR_MAP:
            key_text = AppConfig.CTRL_CHAR_MAP[key_text]
        self.key_down_map[key_text] = False
        if self.rec_state != self.STATE_RECORDING:
            return
        delay = self._calc_delay()
        abs_t = self._get_abs_time()
        self._push_action({"type": "key_release", "key": key_text, "delay": delay, "abs_time": abs_t})

    def start_record(self):
        self.reset_recorder()
        start_name = AppConfig.get_display_name(AppConfig.HOTKEYS["start_record"])
        stop_name = AppConfig.get_display_name(AppConfig.HOTKEYS["stop_record"])
        pause_name = AppConfig.get_display_name(AppConfig.HOTKEYS["pause_record"])
        
        if self.record_mode == AppConfig.MODE_FULL:
            self.log_queue.put("===== 【全量录制模式】已启动 =====")
            self.log_queue.put("记录：鼠标完整轨迹+点击+滚轮+键盘")
        else:
            self.log_queue.put("===== 【简易录制模式】已启动 =====")
            self.log_queue.put("策略：空闲移动丢弃，拖拽动作完整记录，减小文件体积")
        self.log_queue.put(f"等待按下【{start_name}】正式录制，{stop_name}终止录制，{pause_name}暂停/继续录制\n")
        mouse_listener = mouse.Listener(on_move=self.on_mouse_move, on_click=self.on_mouse_click, on_scroll=self.on_mouse_scroll)
        key_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        mouse_listener.start()
        key_listener.start()
        key_listener.join()
        mouse_listener.stop()
        self.log_queue.put("\n==================== 录制完成 ====================")
        if self.cut_index is not None and self.cut_index < len(self.action_list):
            self.action_list = self.action_list[:self.cut_index]
            self.log_queue.put(f"✂️ 已按时间轴截断，保留前{self.cut_index}条动作")
        default_name = FileUtil.get_time_stamp_filename()
        self.log_queue.put(f"默认保存文件名：{default_name}")
        from tkinter import filedialog
        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("录制脚本", "*.json"), ("所有文件", "*.*")],
            initialfile=default_name
        )
        if save_path:
            FileUtil.save_recording(save_path, self.action_list)
            self.log_queue.put(f"✅ 保存成功！动作总数：{len(self.action_list)}，路径：{save_path}")
        else:
            self.log_queue.put("❌ 已放弃保存录制数据")

class PlayerCore:
    def __init__(self, log_queue: queue.Queue):
        from pynput.mouse import Controller as MouseCtrl
        from pynput.keyboard import Controller as KeyCtrl
        self.mouse_ctrl = MouseCtrl()
        self.key_ctrl = KeyCtrl()
        self.log_queue = log_queue
        self.abort_flag = False
    def stop_play(self):
        self.abort_flag = True
    def play_recording(self, file_name: str,
                        loop_count: int,
                        wait_sec: float,
                        speed: float,
                        offset_start_round: int,
                        offset_mode: str,
                        base_off_x: int,
                        base_off_y: int,
                        target_click_set: set,
                        enable_offset: bool,
                        exclude_set: set,
                        first_round_offset: bool,
                        file_offset_list: list[tuple[int, int]]):
        self.abort_flag = False
        try:
            action_data = FileUtil.load_recording(file_name)
        except FileNotFoundError:
            self.log_queue.put(f"❌ 错误：文件 {file_name} 不存在！")
            return
        except json.JSONDecodeError:
            self.log_queue.put("❌ 文件损坏，不是合法录制脚本！")
            return
        self.log_queue.put(f"\n===== 回放启动 | 总动作数：{len(action_data)} =====")
        self.log_queue.put(f"回放倍速：{speed}x")

        use_file_offset = len(file_offset_list) > 0
        if use_file_offset:
            self.log_queue.put(f"✅ 已启用文件多组偏移，共 {len(file_offset_list)} 套坐标循环使用")
        if not enable_offset:
            self.log_queue.put("偏移策略：【不启用任何偏移】所有坐标原始执行")
        else:
            self.log_queue.put(f"偏移模式：{offset_mode}")
            self.log_queue.put(f"首轮回放是否开启偏移：{'是' if first_round_offset else '否'}")
            if not target_click_set:
                self.log_queue.put("生效点击序号：全部点击")
            else:
                self.log_queue.put(f"生效点击序号：{sorted(target_click_set)}")
        if loop_count <= 0:
            self.log_queue.put("循环模式：无限循环（ESC中断）")
        else:
            self.log_queue.put(f"循环模式：执行 {loop_count} 次")

        remain = wait_sec
        while remain > 0 and not self.abort_flag:
            time.sleep(0.1)
            remain -= 0.1
        if self.abort_flag:
            self.log_queue.put("⚠️ 倒计时阶段被终止，取消回放")
            return

        def abort_watch(key):
            stop_key = AppConfig.get_key(AppConfig.HOTKEYS["stop_record"])
            if key == stop_key:
                self.abort_flag = True
                return False
        esc_listener = keyboard.Listener(on_press=abort_watch)
        esc_listener.start()

        current_round = 0
        iter_acc_x = 0
        iter_acc_y = 0
        file_offset_idx = 0

        click_global_index = 0
        all_click_positions = []
        for act_idx, act in enumerate(action_data):
            if act["type"] == "mouse_click":
                click_global_index += 1
                all_click_positions.append((act_idx, click_global_index))
        effective_click_act_indexes = sorted([
            act_idx for act_idx, c_idx in all_click_positions
            if (not target_click_set) or (c_idx in target_click_set)
        ])

        while True:
            if self.abort_flag:
                break
            if loop_count > 0 and current_round >= loop_count:
                break
            current_round += 1
            self.log_queue.put(f"\n-------- 开始第 {current_round} 轮回放 --------")

            if current_round == 1:
                round_enable_offset = enable_offset and first_round_offset
            else:
                round_enable_offset = enable_offset and (current_round >= offset_start_round)

            round_off_x = 0
            round_off_y = 0
            if round_enable_offset:
                if use_file_offset:
                    ox, oy = file_offset_list[file_offset_idx]
                    round_off_x = ox
                    round_off_y = oy
                    self.log_queue.put(f"本轮使用文件偏移下标{file_offset_idx} X:{ox} Y:{oy}")
                    file_offset_idx = (file_offset_idx + 1) % len(file_offset_list)
                else:
                    if offset_mode == AppConfig.OFFSET_FIXED:
                        round_off_x = base_off_x
                        round_off_y = base_off_y
                    else:
                        iter_acc_x += base_off_x
                        iter_acc_y += base_off_y
                        round_off_x = iter_acc_x
                        round_off_y = iter_acc_y
                    self.log_queue.put(f"本轮手动偏移 X:{round_off_x} Y:{round_off_y}")

            click_index = 0
            total_act = len(action_data)
            for idx, act in enumerate(action_data):
                self.log_queue.put(("PLAY_INDEX", idx))
                if self.abort_flag:
                    break
                time.sleep(act["delay"] / speed)
                act_type = act["type"]
                in_effect_range = False
                for i in range(len(effective_click_act_indexes) - 1):
                    start_act_idx = effective_click_act_indexes[i]
                    end_act_idx = effective_click_act_indexes[i+1]
                    if start_act_idx <= idx <= end_act_idx:
                        in_effect_range = True
                        break

                if act_type == "mouse_move":
                    x = act["x"]
                    y = act["y"]
                    if round_enable_offset and in_effect_range:
                        x += round_off_x
                        y += round_off_y
                    self.mouse_ctrl.position = (x, y)
                elif act_type == "mouse_double_click":
                    x = act["x"]
                    y = act["y"]
                    if round_enable_offset and ((not target_click_set) or (click_index in target_click_set)):
                        x += round_off_x
                        y += round_off_y
                    btn = ActionConverter.str_to_mouse_btn(act["button"])
                    self.mouse_ctrl.position = (x, y)
                    self.mouse_ctrl.click(btn, 2)
                elif act_type == "mouse_click":
                    click_index += 1
                    x = act["x"]
                    y = act["y"]
                    if round_enable_offset and ((not target_click_set) or (click_index in target_click_set)):
                        x += round_off_x
                        y += round_off_y
                    btn = ActionConverter.str_to_mouse_btn(act["button"])
                    self.mouse_ctrl.position = (x, y)
                    if act["pressed"]:
                        self.mouse_ctrl.press(btn)
                    else:
                        self.mouse_ctrl.release(btn)
                elif act_type == "mouse_scroll":
                    self.mouse_ctrl.scroll(act["dx"], act["dy"])
                elif act_type == "key_press":
                    key_str = act["key"]
                    if key_str.startswith("Key."):
                        k = getattr(Key, key_str.split(".")[1])
                    else:
                        k = key_str
                    self.key_ctrl.press(k)
                elif act_type == "key_release":
                    key_str = act["key"]
                    if key_str.startswith("Key."):
                        k = getattr(Key, key_str.split(".")[1])
                    else:
                        k = key_str
                    self.key_ctrl.release(k)
        self.log_queue.put(("PLAY_INDEX", None))
        esc_listener.stop()
        if self.abort_flag:
            self.log_queue.put("\n⚠️ 回放被手动ESC终止")
        else:
            self.log_queue.put("\n✅ 全部循环执行完毕！")