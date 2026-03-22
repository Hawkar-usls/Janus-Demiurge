#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS GUI LAUNCHER — одно окно для всех компонентов.
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import os
import sys
import time
from typing import Dict

class JanusLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("JANUS Control Center 🔥")
        self.root.geometry("900x700")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.scripts = {
            "Core Engine": "core.py",
            "HRAIN Server": "server.py",
        }
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running: Dict[str, bool] = {}
        self.lock = threading.Lock()

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5, fill=tk.X)

        self.buttons = {}
        for name in self.scripts:
            btn = tk.Button(btn_frame, text=f"▶ {name}", command=lambda n=name: self.toggle_process(n))
            btn.pack(side=tk.LEFT, padx=2)
            self.buttons[name] = btn

        tk.Button(btn_frame, text="▶ Запустить все", command=self.start_all, bg="lightgreen").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏹ Остановить все", command=self.stop_all, bg="lightcoral").pack(side=tk.LEFT, padx=5)

        self.log_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=('Segoe UI', 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_area.tag_config('stdout', foreground='black')
        self.log_area.tag_config('stderr', foreground='red')
        self.log_area.tag_config('system', foreground='blue')

        self.log("🔧 JANUS Launcher готов. Используй кнопки для запуска компонентов.\n", 'system')

    def log(self, message: str, tag: str = 'stdout') -> None:
        self.log_area.insert(tk.END, message, tag)
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def toggle_process(self, name: str) -> None:
        if self.running.get(name, False):
            self.stop_process(name)
        else:
            self.start_process(name)

    def start_process(self, name: str) -> None:
        script = self.scripts[name]
        if not os.path.exists(script):
            self.log(f"❌ Файл {script} не найден!\n", 'stderr')
            return

        def target():
            try:
                proc = subprocess.Popen(
                    [sys.executable, script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    encoding='utf-8',
                    errors='replace'
                )
                with self.lock:
                    self.processes[name] = proc
                    self.running[name] = True
                    self.buttons[name].config(text=f"⏹ {name}", bg='lightcoral')

                def read_output(pipe, tag):
                    for line in iter(pipe.readline, ''):
                        if line:
                            self.log(f"[{name}] {line}", tag)
                        else:
                            break
                    pipe.close()

                threading.Thread(target=read_output, args=(proc.stdout, 'stdout'), daemon=True).start()
                threading.Thread(target=read_output, args=(proc.stderr, 'stderr'), daemon=True).start()

                proc.wait()
            except Exception as e:
                self.log(f"[{name}] Ошибка запуска: {e}\n", 'stderr')
            finally:
                with self.lock:
                    if name in self.processes:
                        del self.processes[name]
                    self.running[name] = False
                    self.buttons[name].config(text=f"▶ {name}", bg='SystemButtonFace')
                self.log(f"[{name}] процесс завершён.\n", 'system')

        threading.Thread(target=target, daemon=True).start()
        self.log(f"🔄 Запуск {name}...\n", 'system')

    def stop_process(self, name: str) -> None:
        with self.lock:
            proc = self.processes.get(name)
            if proc and proc.poll() is None:
                proc.terminate()
                self.log(f"⏹ Остановка {name}...\n", 'system')
            else:
                self.log(f"[{name}] уже не запущен.\n", 'system')

    def start_all(self) -> None:
        for name in self.scripts:
            if not self.running.get(name, False):
                self.start_process(name)
                time.sleep(0.5)

    def stop_all(self) -> None:
        for name in list(self.scripts.keys()):
            self.stop_process(name)

    def on_close(self) -> None:
        self.stop_all()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = JanusLauncher(root)
    root.mainloop()