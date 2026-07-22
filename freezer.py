#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FREEZER v2.1 - Modern UI
"""

import sys, os, subprocess, webbrowser

# ── Auto-install deps ────────────────────────────────────────────────────────
def _ensure(pkg, import_as=None):
    import_as = import_as or pkg
    try:
        __import__(import_as)
    except ImportError:
        print(f"[FREEZER] Установка {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

_ensure("psutil")
_ensure("pynput")
_ensure("customtkinter")

import customtkinter as ctk
import ctypes, ctypes.wintypes
import json, threading, time
import psutil
from pynput import keyboard as pynkb, mouse as pynms

# ── Windows API ──────────────────────────────────────────────────────────────
ntdll    = ctypes.WinDLL("ntdll")
kernel32 = ctypes.windll.kernel32

def _open_proc(pid: int):
    return kernel32.OpenProcess(0x1F0FFF, False, pid)

def suspend_process(pid: int):
    h = _open_proc(pid)
    if h:
        ntdll.NtSuspendProcess(h)
        kernel32.CloseHandle(h)

def resume_process(pid: int):
    h = _open_proc(pid)
    if h:
        ntdll.NtResumeProcess(h)
        kernel32.CloseHandle(h)

def find_pid(name: str):
    n = name.lower()
    if not n.endswith(".exe"):
        n += ".exe"
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if p.info["name"] and p.info["name"].lower() == n:
                return p.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

# ── Settings ─────────────────────────────────────────────────────────────────
_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freezer.json")
_DEFAULTS = {"process": "hl2.exe", "duration_ms": 500, "hotkey": None}

def load_cfg() -> dict:
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                d = _DEFAULTS.copy(); d.update(json.load(f)); return d
        except Exception:
            pass
    return _DEFAULTS.copy()

def save_cfg(cfg: dict):
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ── App ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class FreezerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg    = load_cfg()
        self.frozen = False
        self.binding = False
        self._lock  = threading.Lock()
        self._kb    = None
        self._ms    = None

        self.title("FREEZER")
        self.geometry("400x700")
        self.resizable(False, False)
        self.configure(fg_color="#080C18") # Темно-синий фон

        self._build_ui()
        self._apply_cfg()
        self._start_listeners()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ── Header ──
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(hdr, text="FREEZER", font=("Arial", 20, "bold"), text_color="#3B82F6").pack(side="left")
        ctk.CTkLabel(hdr, text="v2.1", font=("Arial", 12), text_color="#64748B").pack(side="left", padx=5, pady=(5,0))
        
        # ── Telegram Ad Banner ──
        tg_frame = ctk.CTkFrame(self, fg_color="#141E33", corner_radius=12)
        tg_frame.pack(fill="x", padx=20, pady=(10, 15))
        
        tg_btn = ctk.CTkButton(tg_frame, text="📢 тгк с новостями", font=("Arial", 14, "bold"), 
                               fg_color="transparent", text_color="#60A5FA", hover_color="#1E2D4A",
                               command=lambda: webbrowser.open("https://t.me/darexshadowxd"))
        tg_btn.pack(fill="x", pady=12, padx=10)
        
        # ── Status & Manual Freeze ──
        self.status_lbl = ctk.CTkLabel(self, text="Нажмите для заморозки", font=("Arial", 14), text_color="#64748B")
        self.status_lbl.pack(pady=(10, 10))

        self.power_btn = ctk.CTkButton(self, text="❄ ЗАМОРОЗИТЬ", font=("Arial", 13, "bold"), 
                                       width=160, height=36, corner_radius=18,
                                       fg_color="#0E1525", hover_color="#141E33",
                                       border_width=2, border_color="#1E2D4A", text_color="#3B82F6",
                                       command=self._manual_freeze)
        self.power_btn.pack(pady=(0, 30))

        # ── Main Card (Settings) ──
        card = ctk.CTkFrame(self, fg_color="#0E1525", corner_radius=20)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        card_title = ctk.CTkLabel(card, text="ТЕКУЩИЕ НАСТРОЙКИ", font=("Arial", 11, "bold"), text_color="#64748B")
        card_title.pack(anchor="w", padx=20, pady=(20, 10))

        # Process Entry
        proc_frame = ctk.CTkFrame(card, fg_color="transparent")
        proc_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(proc_frame, text="Процесс", font=("Arial", 14)).pack(side="left")
        self.proc_var = ctk.StringVar()
        self.proc_e = ctk.CTkEntry(proc_frame, textvariable=self.proc_var, width=150, fg_color="#141E33", border_width=0)
        self.proc_e.pack(side="right")

        # Duration Entry
        dur_frame = ctk.CTkFrame(card, fg_color="transparent")
        dur_frame.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(dur_frame, text="Задержка (мс)", font=("Arial", 14)).pack(side="left")
        self.dur_var = ctk.StringVar()
        self.dur_e = ctk.CTkEntry(dur_frame, textvariable=self.dur_var, width=150, fg_color="#141E33", border_width=0)
        self.dur_e.pack(side="right")

        # Divider
        ctk.CTkFrame(card, height=1, fg_color="#1E2D4A").pack(fill="x", padx=20, pady=10)

        # Hotkey bind
        hk_frame = ctk.CTkFrame(card, fg_color="transparent")
        hk_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(hk_frame, text="Хоткей", font=("Arial", 14)).pack(side="left")
        
        self.bind_btn = ctk.CTkButton(hk_frame, text="—", width=110, fg_color="#3B82F6", hover_color="#60A5FA", command=self._start_bind)
        self.bind_btn.pack(side="right")
        
        self.clr_btn = ctk.CTkButton(hk_frame, text="✕", width=30, fg_color="#F87171", hover_color="#ef4444", command=self._clear_hk)
        self.clr_btn.pack(side="right", padx=(0, 10))

        # ── Bottom Nav ──
        nav = ctk.CTkFrame(self, fg_color="#0E1525", corner_radius=20, height=70)
        nav.pack(fill="x", padx=20, pady=(0, 20))
        nav.pack_propagate(False)
        
        ctk.CTkButton(nav, text="Главная", fg_color="#1E2D4A", text_color="#3B82F6", width=100, corner_radius=15).pack(side="left", padx=(25, 10), pady=15)
        ctk.CTkButton(nav, text="Сохранить", fg_color="transparent", text_color="#64748B", width=100, hover_color="#141E33", command=self._save).pack(side="left", padx=10, pady=15)
        # Добавлена команда открытия конфигурации
        ctk.CTkButton(nav, text="Настройки", fg_color="transparent", text_color="#64748B", width=100, hover_color="#141E33", command=self._open_settings).pack(side="left", padx=(10, 25), pady=15)

    def _apply_cfg(self):
        self.proc_var.set(self.cfg.get("process", ""))
        self.dur_var.set(str(self.cfg.get("duration_ms", 500)))
        hk = self.cfg.get("hotkey")
        if hk:
            self.bind_btn.configure(text=hk)

    def _save(self):
        self.cfg["process"] = self.proc_var.get().strip()
        try: self.cfg["duration_ms"] = max(1, int(self.dur_var.get()))
        except ValueError: self.cfg["duration_ms"] = 500
        save_cfg(self.cfg)
        self.status_lbl.configure(text="✓ Настройки сохранены", text_color="#4ADE80")
        self.after(1500, lambda: self.status_lbl.configure(text="Нажмите для заморозки", text_color="#64748B"))

    def _open_settings(self):
        # Открывает файл freezer.json в Блокноте
        if os.path.exists(_SETTINGS_PATH):
            os.startfile(_SETTINGS_PATH)
        else:
            self.status_lbl.configure(text="✗ Конфиг еще не создан", text_color="#F87171")
            self.after(2000, lambda: self.status_lbl.configure(text="Нажмите для заморозки", text_color="#64748B"))

    def _manual_freeze(self):
        self._do_freeze()

    def _do_freeze(self):
        if self.frozen or self.binding: return
        proc = self.proc_var.get().strip()
        if not proc:
            self.status_lbl.configure(text="✗ Укажите процесс", text_color="#F87171")
            return
        
        try: ms = max(1, int(self.dur_var.get()))
        except ValueError: ms = 500
        
        pid = find_pid(proc)
        if not pid:
            self.status_lbl.configure(text=f"✗ Процесс не найден", text_color="#F87171")
            self.after(2000, lambda: self.status_lbl.configure(text="Нажмите для заморозки", text_color="#64748B"))
            return
            
        threading.Thread(target=self._freeze_thread, args=(pid, ms), daemon=True).start()

    def _freeze_thread(self, pid: int, ms: int):
        if not self._lock.acquire(blocking=False): return
        try:
            self.frozen = True
            self.after(0, lambda: self.status_lbl.configure(text="❄ ЗАМОРОЖЕН", text_color="#BAE6FD"))
            self.after(0, lambda: self.power_btn.configure(border_color="#3B82F6", text_color="#BAE6FD"))

            suspend_process(pid)
            time.sleep(ms / 1000.0)
            resume_process(pid)

        except Exception:
            self.after(0, lambda: self.status_lbl.configure(text="✗ ОШИБКА (ПРАВА?)", text_color="#F87171"))
        finally:
            self.frozen = False
            self.after(0, lambda: self.status_lbl.configure(text="Нажмите для заморозки", text_color="#64748B"))
            self.after(0, lambda: self.power_btn.configure(border_color="#1E2D4A", text_color="#3B82F6"))
            self._lock.release()

    # ── Hotkey binding ──
    def _start_bind(self):
        self.binding = True
        self.bind_btn.configure(text="Жду...", fg_color="#FB923C")

    def _finish_bind(self, key_name: str):
        self.binding = False
        self.cfg["hotkey"] = key_name
        self.after(0, lambda: self.bind_btn.configure(text=key_name, fg_color="#3B82F6"))

    def _clear_hk(self):
        self.binding = False
        self.cfg["hotkey"] = None
        self.bind_btn.configure(text="—", fg_color="#3B82F6")

    # ── Listeners ──
    def _start_listeners(self):
        self._kb = pynkb.Listener(on_press=self._on_key)
        self._kb.daemon = True
        self._kb.start()

        self._ms = pynms.Listener(on_click=self._on_click)
        self._ms.daemon = True
        self._ms.start()

    def _on_key(self, key):
        try:
            name = key.name.upper() if hasattr(key, "name") and key.name else None
            if name is None: name = str(key).strip("'").upper()
        except Exception: return

        if self.binding:
            if name in ("ESC", "ESCAPE"):
                self.binding = False
                hk = self.cfg.get("hotkey")
                self.after(0, lambda: self.bind_btn.configure(text=hk if hk else "—", fg_color="#3B82F6"))
                return
            self.after(0, lambda n=name: _finish_bind_safely(self, n))
            return

        hk = self.cfg.get("hotkey")
        if hk and name == hk.upper() and not self.frozen:
            self._do_freeze()

    def _on_click(self, x, y, button, pressed):
        if not pressed: return
        if button == pynms.Button.x1: bname = "MOUSE4"
        elif button == pynms.Button.x2: bname = "MOUSE5"
        else: return

        if self.binding:
            self.after(0, lambda n=bname: _finish_bind_safely(self, n))
            return

        hk = self.cfg.get("hotkey")
        if hk and bname == hk.upper() and not self.frozen:
            self._do_freeze()

    def _on_close(self):
        self._save()
        if self._kb: self._kb.stop()
        if self._ms: self._ms.stop()
        self.destroy()

def _finish_bind_safely(app, n):
    app._finish_bind(n)

if __name__ == "__main__":
    if sys.platform != "win32":
        print("FREEZER работает только на Windows!")
        sys.exit(1)
    app = FreezerApp()
    app.mainloop()
    
