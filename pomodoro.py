#!/usr/bin/env python3
"""番茄钟 — 桌面番茄工作法计时器"""

import tkinter as tk
from tkinter import ttk
import threading
import time
from enum import Enum


# ============ 配置 ============
WORK_MINUTES = 25
SHORT_BREAK_MINUTES = 5
LONG_BREAK_MINUTES = 15
POMODOROS_BEFORE_LONG_BREAK = 4

# Catppuccin Mocha 配色
C = {
    "base":     "#1e1e2e",
    "surface0": "#313244",
    "surface1": "#45475a",
    "text":     "#cdd6f4",
    "subtext0": "#a6adc8",
    "subtext1": "#bac2de",
    "red":      "#f38ba8",
    "green":    "#a6e3a1",
    "blue":     "#89b4fa",
    "teal":     "#94e2d5",
    "white":    "#ffffff",
}


class TimerState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


class PomodoroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("番茄钟")
        self.root.configure(bg=C["base"])
        self.root.resizable(False, False)

        # 窗口置顶
        self._pinned = True
        self.root.attributes("-topmost", True)

        self.W, self.H = 400, 560
        self.root.geometry(f"{self.W}x{self.H}")

        # 状态
        self.state = TimerState.IDLE
        self.mode = "work"          # work / short_break / long_break
        self.remaining = WORK_MINUTES * 60
        self.total = WORK_MINUTES * 60
        self.pomodoros = 0          # 已完成番茄数
        self._running = False
        self._thread = None

        self._setup_style()
        self._build_ui()
        self._center()
        self._render()

    # ==================== ttk 样式 ====================

    def _setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # 通用按钮
        self.style.configure(
            "Pomodoro.TButton",
            font=("Microsoft YaHei UI", 11),
            borderwidth=0,
            relief="flat",
            padding=(16, 8),
            background=C["surface0"],
            foreground=C["text"],
        )
        self.style.map("Pomodoro.TButton",
                       background=[("active", C["surface1"]), ("!active", C["surface0"])])

        # 主按钮 - 大号
        self.style.configure(
            "Main.TButton",
            font=("Microsoft YaHei UI", 14, "bold"),
            borderwidth=0,
            relief="flat",
            padding=(30, 12),
            background=C["red"],
            foreground=C["white"],
        )

        # 模式选择按钮
        self.style.configure(
            "Mode.TButton",
            font=("Segoe UI", 14),
            borderwidth=0,
            relief="flat",
            padding=(10, 6),
        )

    # ==================== UI 布局 ====================

    def _build_ui(self):
        # 主容器
        main = tk.Frame(self.root, bg=C["base"])
        main.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        # ---- 顶部：标题 + 置顶 ----
        top = tk.Frame(main, bg=C["base"])
        top.pack(fill=tk.X)

        title = tk.Label(top, text="🍅 番茄钟",
                         font=("Microsoft YaHei UI", 18, "bold"),
                         fg=C["text"], bg=C["base"])
        title.pack(side=tk.LEFT)

        self._pin_label = tk.Label(
            top, text="📌",
            font=("Segoe UI", 12), fg=C["blue"], bg=C["base"], cursor="hand2"
        )
        self._pin_label.pack(side=tk.RIGHT)
        self._pin_label.bind("<Button-1>", self._toggle_pin)

        # ---- 模式标签 ----
        self._mode_label = tk.Label(
            main, text="专注",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=C["red"], bg=C["base"]
        )
        self._mode_label.pack(pady=(8, 0))

        # ---- 进度环画布 ----
        self._canvas = tk.Canvas(
            main, width=260, height=260,
            bg=C["base"], highlightthickness=0
        )
        self._canvas.pack(pady=(8, 0))

        # ---- 番茄计数 ----
        self._tomato_label = tk.Label(
            main, text="",
            font=("Segoe UI", 14), fg=C["subtext0"], bg=C["base"]
        )
        self._tomato_label.pack(pady=(4, 0))

        # ---- 控制按钮行 ----
        ctrl = tk.Frame(main, bg=C["base"])
        ctrl.pack(pady=(16, 0))

        self._main_btn = ttk.Button(
            ctrl, text="▶  开始专注", style="Main.TButton",
            command=self._on_main
        )
        self._main_btn.pack(side=tk.LEFT, padx=6)

        self._reset_btn = ttk.Button(
            ctrl, text="↺ 重置", style="Pomodoro.TButton",
            command=self._on_reset
        )
        self._reset_btn.pack(side=tk.LEFT, padx=6)

        self._skip_btn = ttk.Button(
            ctrl, text="⏭ 跳过", style="Pomodoro.TButton",
            command=self._on_skip
        )
        self._skip_btn.pack(side=tk.LEFT, padx=6)

        # ---- 模式切换按钮行 ----
        mode_frame = tk.Frame(main, bg=C["base"])
        mode_frame.pack(pady=(20, 0))

        self._btn_work = tk.Label(
            mode_frame, text="🍅",
            font=("Segoe UI", 16), fg=C["white"], bg=C["red"],
            padx=14, pady=6, cursor="hand2"
        )
        self._btn_work.pack(side=tk.LEFT, padx=8)
        self._btn_work.bind("<Button-1>", lambda e: self._switch("work"))

        self._btn_short = tk.Label(
            mode_frame, text="☕",
            font=("Segoe UI", 16), fg=C["text"], bg=C["surface0"],
            padx=14, pady=6, cursor="hand2"
        )
        self._btn_short.pack(side=tk.LEFT, padx=8)
        self._btn_short.bind("<Button-1>", lambda e: self._switch("short_break"))

        self._btn_long = tk.Label(
            mode_frame, text="🌴",
            font=("Segoe UI", 16), fg=C["text"], bg=C["surface0"],
            padx=14, pady=6, cursor="hand2"
        )
        self._btn_long.pack(side=tk.LEFT, padx=8)
        self._btn_long.bind("<Button-1>", lambda e: self._switch("long_break"))

        # ---- 底部提示 ----
        self._hint = tk.Label(
            main, text="选好模式，点击开始吧",
            font=("Microsoft YaHei UI", 9), fg=C["subtext0"], bg=C["base"]
        )
        self._hint.pack(pady=(20, 0))

    # ==================== 渲染 ====================

    def _render(self):
        """绘制进度环和时间"""
        self._canvas.delete("all")
        cx, cy = 130, 130
        r = 105
        w = 10

        color = C["red"] if self.mode == "work" else C["green"]

        # 背景圆环
        self._canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=C["surface0"], width=w
        )

        # 进度弧
        if self.total > 0:
            pct = 1.0 - (self.remaining / self.total)
        else:
            pct = 0

        if pct > 0.001:
            extent = -int(pct * 360)
            if extent <= -360:
                extent = -359  # tkinter 画不了满圆
            self._canvas.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=90, extent=extent,
                outline=color, width=w, style="arc"
            )

        # 中心时间
        mins = self.remaining // 60
        secs = self.remaining % 60
        self._canvas.create_text(
            cx, cy - 6,
            text=f"{mins:02d}:{secs:02d}",
            font=("Microsoft YaHei UI", 42, "bold"),
            fill=C["text"]
        )
        self._canvas.create_text(
            cx, cy + 32,
            text=f"{secs:02d}",
            font=("Microsoft YaHei UI", 10),
            fill=C["subtext0"]
        )

        # 模式标签
        names = {"work": "专注", "short_break": "短休息", "long_break": "长休息"}
        self._mode_label.configure(text=names[self.mode], fg=color)

        # 番茄计数
        full = self.pomodoros % POMODOROS_BEFORE_LONG_BREAK
        self._tomato_label.configure(
            text="  ".join(
                "🍅" if i < full else "○"
                for i in range(POMODOROS_BEFORE_LONG_BREAK)
            )
        )

        # 模式按钮高亮
        for lbl, m in [
            (self._btn_work, "work"),
            (self._btn_short, "short_break"),
            (self._btn_long, "long_break"),
        ]:
            if m == self.mode:
                lbl.configure(bg=color, fg=C["white"])
            else:
                lbl.configure(bg=C["surface0"], fg=C["text"])

    # ==================== 定时器线程 ====================

    def _timer_loop(self):
        while self._running:
            time.sleep(1)
            if not self._running:
                return
            if self.state != TimerState.RUNNING:
                continue

            self.remaining -= 1
            self.root.after(0, self._render)

            if self.remaining <= 0:
                self.root.after(0, self._on_finish)
                return

    def _on_finish(self):
        self._running = False
        self.state = TimerState.IDLE

        # 提示音
        for i in range(4):
            self.root.after(i * 200, self.root.bell)

        # 闪烁窗口
        self._flash()

        if self.mode == "work":
            self.pomodoros += 1
            self._hint.configure(text=f"🎉 完成 {self.pomodoros} 个番茄！休息一下吧～")

            if self.pomodoros % POMODOROS_BEFORE_LONG_BREAK == 0:
                self._switch("long_break")
            else:
                self._switch("short_break")
        else:
            self._hint.configure(text="休息结束，开始新的番茄吧！")
            self._switch("work")

        self._update_main_btn()

    def _flash(self):
        for i in range(4):
            self.root.after(i * 250, lambda: self.root.attributes("-topmost", False))
            self.root.after(i * 250 + 125,
                            lambda: self.root.attributes("-topmost", self._pinned))

    # ==================== 按钮逻辑 ====================

    def _on_main(self):
        if self.state == TimerState.IDLE:
            # 开始
            self.state = TimerState.RUNNING
            self._running = True
            self._hint.configure(
                text="专注中，别分心 ✨" if self.mode == "work" else "休息中..."
            )
            self._thread = threading.Thread(target=self._timer_loop, daemon=True)
            self._thread.start()
        elif self.state == TimerState.RUNNING:
            # 暂停
            self.state = TimerState.PAUSED
            self._hint.configure(text="已暂停")
        elif self.state == TimerState.PAUSED:
            # 继续
            self.state = TimerState.RUNNING
            self._hint.configure(
                text="继续专注 ✨" if self.mode == "work" else "继续休息..."
            )

        self._update_main_btn()

    def _update_main_btn(self):
        """更新主按钮样式"""
        color = C["red"] if self.mode == "work" else C["green"]

        if self.state == TimerState.IDLE:
            text = "▶  开始专注" if self.mode == "work" else "▶  开始休息"
            self.style.configure("Main.TButton", background=color)
        elif self.state == TimerState.RUNNING:
            text = "⏸  暂停"
            self.style.configure("Main.TButton", background=C["blue"])
        elif self.state == TimerState.PAUSED:
            text = "▶  继续"
            self.style.configure("Main.TButton", background=C["teal"])

        self._main_btn.configure(text=text)

    def _on_reset(self):
        self._running = False
        self.state = TimerState.IDLE
        self._set_time()
        self._hint.configure(text="已重置")
        self._update_main_btn()
        self._render()

    def _on_skip(self):
        self._running = False
        self.state = TimerState.IDLE
        self.remaining = 0
        self._render()
        self._on_finish()

    def _switch(self, mode):
        self._running = False
        self.state = TimerState.IDLE
        self.mode = mode
        self._set_time()
        self._hint.configure(
            text="选好模式，点击开始吧" if mode == "work" else "休息一下，点击开始"
        )
        self._update_main_btn()
        self._render()

    def _set_time(self):
        times = {
            "work": WORK_MINUTES * 60,
            "short_break": SHORT_BREAK_MINUTES * 60,
            "long_break": LONG_BREAK_MINUTES * 60,
        }
        self.remaining = times[self.mode]
        self.total = times[self.mode]

    def _toggle_pin(self, event=None):
        self._pinned = not self._pinned
        self.root.attributes("-topmost", self._pinned)
        self._pin_label.configure(fg=C["blue"] if self._pinned else C["subtext0"])

    def _center(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - self.W) // 2
        y = (sh - self.H) // 2
        self.root.geometry(f"+{x}+{y}")


def main():
    root = tk.Tk()
    PomodoroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
    print("程序结束")
