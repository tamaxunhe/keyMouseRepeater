# main.py
# ========= Windows DPI感知 必须最先执行 =========
import os
import ctypes
if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

import tkinter as tk
from gui import MacroGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = MacroGUI(root)
    root.mainloop()