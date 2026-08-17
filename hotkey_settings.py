# hotkey_settings.py
import tkinter as tk
from tkinter import ttk, messagebox
from pynput import keyboard
from config import AppConfig

class HotkeySettingsDialog:
    def __init__(self, parent, on_save_callback=None):
        self.parent = parent
        self.on_save_callback = on_save_callback
        self.current_key = None
        self.listening = False
        self.key_listener = None
        
        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("快捷键设置")
        self.dialog.geometry("500x350")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 设置窗口居中
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 350) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        self.build_ui()
        self.load_current_hotkeys()
        
    def build_ui(self):
        # 说明标签
        info_frame = ttk.Frame(self.dialog)
        info_frame.pack(fill=tk.X, padx=20, pady=(15, 10))
        ttk.Label(info_frame, text="点击输入框后按下想要设置的按键组合", font=("Microsoft YaHei", 10)).pack()
        ttk.Label(info_frame, text="（仅支持单个按键，不支持组合键）", font=("Microsoft YaHei", 9), foreground="#666").pack()
        
        # 快捷键设置区域
        settings_frame = ttk.Frame(self.dialog)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 开始录制
        ttk.Label(settings_frame, text="开始录制：", width=12).grid(row=0, column=0, sticky="w", pady=8)
        self.start_entry = self._create_hotkey_entry(settings_frame, "start_record")
        self.start_entry.grid(row=0, column=1, padx=10, pady=8, sticky="w")
        ttk.Label(settings_frame, text="当前快捷键", foreground="#666").grid(row=0, column=2, sticky="w", pady=8)
        self.start_label = ttk.Label(settings_frame, text="", foreground="#0066cc")
        self.start_label.grid(row=0, column=3, padx=5, pady=8, sticky="w")
        
        # 停止录制
        ttk.Label(settings_frame, text="停止录制：", width=12).grid(row=1, column=0, sticky="w", pady=8)
        self.stop_entry = self._create_hotkey_entry(settings_frame, "stop_record")
        self.stop_entry.grid(row=1, column=1, padx=10, pady=8, sticky="w")
        ttk.Label(settings_frame, text="当前快捷键", foreground="#666").grid(row=1, column=2, sticky="w", pady=8)
        self.stop_label = ttk.Label(settings_frame, text="", foreground="#0066cc")
        self.stop_label.grid(row=1, column=3, padx=5, pady=8, sticky="w")
        
        # 暂停/继续
        ttk.Label(settings_frame, text="暂停/继续：", width=12).grid(row=2, column=0, sticky="w", pady=8)
        self.pause_entry = self._create_hotkey_entry(settings_frame, "pause_record")
        self.pause_entry.grid(row=2, column=1, padx=10, pady=8, sticky="w")
        ttk.Label(settings_frame, text="当前快捷键", foreground="#666").grid(row=2, column=2, sticky="w", pady=8)
        self.pause_label = ttk.Label(settings_frame, text="", foreground="#0066cc")
        self.pause_label.grid(row=2, column=3, padx=5, pady=8, sticky="w")
        
        # 快速回放
        ttk.Label(settings_frame, text="快速回放：", width=12).grid(row=3, column=0, sticky="w", pady=8)
        self.play_entry = self._create_hotkey_entry(settings_frame, "play_last")
        self.play_entry.grid(row=3, column=1, padx=10, pady=8, sticky="w")
        ttk.Label(settings_frame, text="当前快捷键", foreground="#666").grid(row=3, column=2, sticky="w", pady=8)
        self.play_label = ttk.Label(settings_frame, text="", foreground="#0066cc")
        self.play_label.grid(row=3, column=3, padx=5, pady=8, sticky="w")
        
        # 按钮
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        ttk.Button(btn_frame, text="恢复默认", command=self.reset_default).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="保存", command=self.save_and_close).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
    def _create_hotkey_entry(self, parent, key_name):
        """创建快捷键输入框"""
        entry = ttk.Entry(parent, width=15, state="readonly")
        entry.bind("<Button-1>", lambda e: self.start_listening(key_name, entry))
        return entry
    
    def load_current_hotkeys(self):
        """加载当前快捷键到界面"""
        hotkeys = AppConfig.HOTKEYS
        self.start_entry.config(state="normal")
        self.start_entry.delete(0, tk.END)
        self.start_entry.insert(0, AppConfig.get_display_name(hotkeys.get("start_record", "f1")))
        self.start_entry.config(state="readonly")
        self.start_label.config(text=hotkeys.get("start_record", "f1"))
        
        self.stop_entry.config(state="normal")
        self.stop_entry.delete(0, tk.END)
        self.stop_entry.insert(0, AppConfig.get_display_name(hotkeys.get("stop_record", "f2")))
        self.stop_entry.config(state="readonly")
        self.stop_label.config(text=hotkeys.get("stop_record", "f2"))
        
        self.pause_entry.config(state="normal")
        self.pause_entry.delete(0, tk.END)
        self.pause_entry.insert(0, AppConfig.get_display_name(hotkeys.get("pause_record", "f9")))
        self.pause_entry.config(state="readonly")
        self.pause_label.config(text=hotkeys.get("pause_record", "f9"))
        
        self.play_entry.config(state="normal")
        self.play_entry.delete(0, tk.END)
        self.play_entry.insert(0, AppConfig.get_display_name(hotkeys.get("play_last", "f5")))
        self.play_entry.config(state="readonly")
        self.play_label.config(text=hotkeys.get("play_last", "f5"))
    
    def start_listening(self, key_name, entry):
        """开始监听按键"""
        if self.listening:
            return
        
        self.current_key = key_name
        self.listening = True
        entry.config(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, "按下按键...")
        entry.config(state="readonly")
        
        # 启动监听
        def on_press(key):
            if self.listening:
                # 转换按键为字符串
                try:
                    if hasattr(key, 'char') and key.char is not None:
                        key_name_str = key.char.lower()
                    else:
                        key_name_str = str(key).replace("Key.", "").lower()
                except:
                    return
                
                # 过滤无效按键
                if key_name_str in ["", " ", "\x03", "\x16"]:
                    return
                
                # 更新界面
                self.parent.after(0, lambda: self._on_key_pressed(key_name_str, entry))
                return False  # 停止监听
                
        self.key_listener = keyboard.Listener(on_press=on_press)
        self.key_listener.start()
    
    def _on_key_pressed(self, key_name, entry):
        """按键被按下后的处理"""
        # 验证按键是否有效
        if key_name not in AppConfig.KEY_MAP:
            messagebox.showwarning("无效按键", f"按键 '{key_name}' 不被支持，请选择其他按键")
            entry.config(state="normal")
            entry.delete(0, tk.END)
            entry.insert(0, AppConfig.get_display_name(AppConfig.HOTKEYS[self.current_key]))
            entry.config(state="readonly")
            self.listening = False
            return
        
        # 更新输入框
        display_name = AppConfig.get_display_name(key_name)
        entry.config(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, display_name)
        entry.config(state="readonly")
        
        # 保存到临时配置
        AppConfig.HOTKEYS[self.current_key] = key_name
        
        # 更新对应的标签
        if self.current_key == "start_record":
            self.start_label.config(text=key_name)
        elif self.current_key == "stop_record":
            self.stop_label.config(text=key_name)
        elif self.current_key == "pause_record":
            self.pause_label.config(text=key_name)
        elif self.current_key == "play_last":
            self.play_label.config(text=key_name)
        
        self.listening = False
        if self.key_listener:
            self.key_listener.stop()
    
    def reset_default(self):
        """恢复默认快捷键"""
        if messagebox.askyesno("确认", "恢复默认快捷键设置？"):
            AppConfig.reset_hotkeys()
            self.load_current_hotkeys()
            messagebox.showinfo("成功", "已恢复默认快捷键")
    
    def save_and_close(self):
        """保存并关闭"""
        # 检查是否有重复的快捷键
        values = list(AppConfig.HOTKEYS.values())
        if len(values) != len(set(values)):
            # 找出重复的
            duplicates = [k for k, v in AppConfig.HOTKEYS.items() if values.count(v) > 1]
            duplicate_names = [AppConfig.get_display_name(AppConfig.HOTKEYS[k]) for k in set(duplicates)]
            messagebox.showwarning("重复快捷键", f"以下快捷键被重复使用：{', '.join(duplicate_names)}\n请确保每个功能使用不同的快捷键")
            return
        
        # 保存配置
        AppConfig.save_hotkeys()
        
        # 触发回调
        if self.on_save_callback:
            self.on_save_callback()
        
        self.dialog.destroy()
        messagebox.showinfo("成功", "快捷键设置已保存！")