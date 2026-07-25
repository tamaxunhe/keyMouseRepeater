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
        btn_name = ActionConverter.mouse_btn_to_str(button)
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
        if key == AppConfig.EXIT_HOTKEY:
            return False
        if key == AppConfig.REC_PAUSE_HOTKEY:
            self.toggle_pause()
            return

        if self.rec_state == self.STATE_WAIT_START:
            if key == AppConfig.START_HOTKEY:
                self.rec_state = self.STATE_RECORDING
                self.last_time = time.perf_counter()
                self.rec_start_ts = time.perf_counter()
                self.ignore_next_enter_release = True
                self.log_queue.put("✅ 检测到回车，正式开始录制操作！")
            return
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
        if key == AppConfig.EXIT_HOTKEY:
            return False
        if key == AppConfig.REC_PAUSE_HOTKEY:
            return

        if self.ignore_next_enter_release and key == AppConfig.START_HOTKEY:
            self.ignore_next_enter_release = False
            return
        if self.rec_state not in (self.STATE_RECORDING, self.STATE_REC_PAUSED):
            return
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
        if self.record_mode == AppConfig.MODE_FULL:
            self.log_queue.put("===== 【全量录制模式】已启动 =====")
            self.log_queue.put("记录：鼠标完整轨迹+点击+滚轮+键盘")
        else:
            self.log_queue.put("===== 【简易录制模式】已启动 =====")
            self.log_queue.put("策略：空闲移动丢弃，拖拽动作完整记录，减小文件体积")
        self.log_queue.put("等待按下【回车】正式录制，F9暂停/继续录制，ESC终止录制\n")
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
        self.action_data = []
        self.speed = 1.0
        self.offset_cfg = {}
        self._play_thread_running = False

    def stop_play(self):
        self.abort_flag = True

    def load_sequence(self, action_list: list):
        """载入待回放动作序列，支持外部传入合并后的轨道动作"""
        self.action_data = action_list.copy()

    def _find_seek_index(self, target_abs_time: float) -> int:
        """二分查找，定位第一个 abs_time >= target_abs_time 的动作下标"""
        low = 0
        high = len(self.action_data) - 1
        best = 0
        while low <= high:
            mid = (low + high) // 2
            t = self.action_data[mid]["abs_time"]
            if t <= target_abs_time:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        return best

    def seek_playback(self, target_abs_time: float):
        """对外接口：拖拽游标调用，跳转到指定绝对时间开始播放"""
        if self._play_thread_running:
            self.log_queue.put("⚠️ 正在回放中，暂不支持实时seek，请等待本轮结束")
            return
        idx = self._find_seek_index(target_abs_time)
        self.log_queue.put(f"🎯 跳转定位至 时间={target_abs_time:.2f}s，动作下标={idx}")
        return idx

    def play_recording(self, action_data: list,
                        loop_count: int,
                        wait_sec: float,
                        speed: float,
                        offset_start_round: int,
                        offset_mode: str,
                        base_off_x: int,
                        base_off_y: int,
                        target_click_set: set,
                        enable_offset: bool,
                        exclude_set: set):
        self.abort_flag = False
        self._play_thread_running = True
        self.load_sequence(action_data)
        self.speed = speed
        try:
            self._execute_play(loop_count, wait_sec, speed, offset_start_round, offset_mode, base_off_x, base_off_y, target_click_set, enable_offset)
        finally:
            self._play_thread_running = False

    def _execute_play(self, loop_count: int, wait_sec: float, speed: float,
                      offset_start_round: int, offset_mode: str, base_off_x: int, base_off_y: int,
                      target_click_set: set, enable_offset: bool):
        action_data = self.action_data
        if not action_data:
            self.log_queue.put("⚠️ 无回放动作序列")
            return

        self.log_queue.put(f"\n===== 回放启动 | 总动作数：{len(action_data)} =====")
        self.log_queue.put(f"回放倍速：{speed}x")
        if not enable_offset:
            self.log_queue.put("偏移策略：【不启用任何偏移】所有坐标原始执行")
        else:
            self.log_queue.put(f"偏移模式：{offset_mode}")
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
            if key == AppConfig.EXIT_HOTKEY:
                self.abort_flag = True
                return False
        esc_listener = keyboard.Listener(on_press=abort_watch)
        esc_listener.start()

        current_round = 0
        iter_acc_x = 0
        iter_acc_y = 0

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

            use_offset_round = False
            round_off_x = 0
            round_off_y = 0
            if enable_offset and (current_round >= offset_start_round):
                use_offset_round = True
                if offset_mode == AppConfig.OFFSET_FIXED:
                    round_off_x = base_off_x
                    round_off_y = base_off_y
                else:
                    iter_acc_x += base_off_x
                    iter_acc_y += base_off_y
                    round_off_x = iter_acc_x
                    round_off_y = iter_acc_y
                self.log_queue.put(f"本轮偏移 X:{round_off_x} Y:{round_off_y}")

            click_index = 0
            for idx, act in enumerate(action_data):
                self.log_queue.put(("PLAY_ABSTIME", act["abs_time"]))
                if self.abort_flag:
                    break
                time.sleep(act["delay"] / speed)
                act_type = act["type"]

                in_effect_range = False
                for i in range(len(effective_click_act_indexes) - 1):
                    s_idx = effective_click_act_indexes[i]
                    e_idx = effective_click_act_indexes[i + 1]
                    if s_idx <= idx <= e_idx:
                        in_effect_range = True
                        break

                if act_type == "mouse_move":
                    x = act["x"]
                    y = act["y"]
                    if use_offset_round and in_effect_range:
                        x += round_off_x
                        y += round_off_y
                    self.mouse_ctrl.position = (x, y)

                elif act_type == "mouse_click":
                    click_index += 1
                    x = act["x"]
                    y = act["y"]
                    if use_offset_round and ((not target_click_set) or (click_index in target_click_set)):
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
                        k = getattr(Key, key_str.split(".")[-1])
                    else:
                        k = key_str
                    self.key_ctrl.press(k)
                elif act_type == "key_release":
                    key_str = act["key"]
                    if key_str.startswith("Key."):
                        k = getattr(Key, key_str.split(".")[-1])
                    else:
                        k = key_str
                    self.key_ctrl.release(k)

        self.log_queue.put(("PLAY_ABSTIME", None))
        esc_listener.stop()
        if self.abort_flag:
            self.log_queue.put("\n⚠️ 回放被手动ESC终止")
        else:
            self.log_queue.put("\n✅ 全部循环执行完毕！")