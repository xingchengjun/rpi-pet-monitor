# -*- coding: utf-8 -*-
"""
bridge.py — 电脑(Windows)端桥服务：把 DSH / Codex / 系统状态暴露给树莓派。

端点（均需 token，?token= 或 X-Token 头）：
  GET  /health          存活检查
  GET  /status          完整状态 JSON（DSH、Codex、CPU、内存、待审批数）
  POST /approve         批准：向 Codex 终端窗口发送回车
  GET  /                简单说明页

运行：python bridge.py [--config bridge_config.json]
首次运行自动生成默认配置 bridge_config.json，改完 token 再启动。
开机自启：任务计划程序（见 README.md）。

依赖：仅标准库（可选 pip install zstandard 增强 DSH 状态探测）。
"""

import argparse
import ctypes
import ctypes.wintypes
import hmac
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# 控制台可能为 GBK：统一按 UTF-8 + 容错输出，避免 emoji/生僻字崩掉
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

APP_NAME = "dsh-pi-bridge"
DEFAULT_CONFIG = {
    "bind_host": "0.0.0.0",
    "port": 8123,
    "token": "change-me-please",          # 必须改成自己的！树莓派 pet.py 同步
    "codex": {
        "window_title": "codex",          # Codex 终端窗口标题正则（不区分大小写）
        "mode": "window",                 # window=定位窗口再回车 | foreground=直接发前台窗口
        "activate_delay_s": 0.35,
    },
    "activity": {
        "active_window_s": 30,            # 最近 N 秒内有写入 => 工作中
        "recent_window_s": 600,           # 超过 N 秒无写入 => 视为未运行
        "pending_window_s": 3600,         # 待审批提醒持续窗口（1 小时内都提醒）
    },
    "dsh_sessions_dir": None,             # None = ~/.dsh/sessions
    "codex_sessions_dir": None,           # None = ~/.codex/sessions
    "pi_ssh": {                           # 借道树莓派 zstd 解压 DSH 会话（本机无 zstd）
        "host": "192.168.3.16",
        "user": "wxc",
        "password": "123456",
    },
    "debug_tail": False,                  # 状态里附带最新会话尾部片段（排障用）
}

CONFIG = dict(DEFAULT_CONFIG)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_config.json")


# ---------------------------------------------------------------- 工具 -----
def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.log"),
                  "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config():
    global CONFIG
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k == "codex" and isinstance(v, dict):
                    CONFIG["codex"].update(v)
                elif k == "activity" and isinstance(v, dict):
                    CONFIG["activity"].update(v)
                else:
                    CONFIG[k] = v
            log("已加载配置 %s" % CONFIG_PATH)
        except Exception as e:
            log("配置读取失败，使用默认: %s" % e)
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, ensure_ascii=False, indent=2)
        log("已生成默认配置 %s，请修改 token 后重启" % CONFIG_PATH)


def home_dir():
    return os.path.expanduser("~")


# ---------------------------------------------------------------- 系统状态 --
class SystemStats:
    """ctypes 读取 Windows CPU/内存，无第三方依赖。"""

    def __init__(self):
        self._cpu = 0.0
        self._lock = threading.Lock()
        self._prev_idle = self._prev_total = None
        self._gpu_cache = None
        self._gpu_ts = 0.0
        threading.Thread(target=self._cpu_loop, daemon=True).start()

    def _read_cpu_times(self):
        kernel32 = ctypes.windll.kernel32
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.wintypes.DWORD),
                        ("dwHighDateTime", ctypes.wintypes.DWORD)]
        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        ok = kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel),
                                     ctypes.byref(user))
        if not ok:
            return None
        def to_u64(ft):
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        idle_t = to_u64(idle)
        total = idle_t + to_u64(kernel) + to_u64(user)
        return idle_t, total

    def _cpu_loop(self):
        while True:
            t = self._read_cpu_times()
            if t is not None:
                with self._lock:
                    if self._prev_total is not None and t[1] > self._prev_total:
                        idle_d = t[0] - self._prev_idle
                        total_d = t[1] - self._prev_total
                        self._cpu = max(0.0, 100.0 * (1.0 - idle_d / total_d))
                    self._prev_idle, self._prev_total = t
            time.sleep(1.5)

    def cpu_percent(self):
        with self._lock:
            return round(self._cpu, 1)

    @staticmethod
    def mem_info():
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.wintypes.DWORD),
                        ("dwMemoryLoad", ctypes.wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = MEMORYSTATUSEX()
        ms.dwLength = ctypes.sizeof(ms)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
            return None
        total_gb = ms.ullTotalPhys / 1024.0 ** 3
        used_gb = (ms.ullTotalPhys - ms.ullAvailPhys) / 1024.0 ** 3
        return {"mem": float(ms.dwMemoryLoad),
                "mem_used_gb": round(used_gb, 1),
                "mem_total_gb": round(total_gb, 1)}

    @staticmethod
    def disk_info():
        """C 盘使用率（GetDiskFreeSpaceExW）。"""
        free = ctypes.c_ulonglong(0)
        total = ctypes.c_ulonglong(0)
        if ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p("C:\\"), None,
                ctypes.byref(total), ctypes.byref(free)) and total.value:
            used = total.value - free.value
            return {"disk": round(100.0 * used / total.value, 1),
                    "disk_used_gb": round(used / 1e9, 1),
                    "disk_total_gb": round(total.value / 1e9, 1)}
        return {"disk": 0.0}

    def gpu_info(self):
        """NVIDIA 优先（nvidia-smi），否则 WMI 只给型号；结果缓存 5 秒。"""
        now = time.time()
        if now - self._gpu_ts < 5 and self._gpu_cache is not None:
            return self._gpu_cache
        info = {"gpu": 0.0, "gpu_name": "n/a"}
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,name",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=6)
            if out.returncode == 0 and out.stdout.strip():
                p = [s.strip() for s in out.stdout.strip().splitlines()[0].split(",")]
                info = {"gpu": float(p[0]),
                        "gpu_used_gb": round(float(p[1]) / 1024, 1),
                        "gpu_total_gb": round(float(p[2]) / 1024, 1),
                        "gpu_name": p[3]}
        except Exception:
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_VideoController).Name"],
                    capture_output=True, text=True, timeout=10)
                if out.stdout.strip():
                    info["gpu_name"] = out.stdout.strip().splitlines()[0]
            except Exception:
                pass
        self._gpu_ts = now
        self._gpu_cache = info
        return info

    def snapshot(self):
        info = self.mem_info() or {}
        info["cpu"] = self.cpu_percent()
        info.update(self.disk_info())
        info.update(self.gpu_info())
        return info


# ---------------------------------------------------------------- 状态探测 --
def newest_mtime_under(root, pattern):
    """返回 (最新文件路径, mtime) 或 (None, None)。"""
    best_f, best_t = None, None
    if not root or not os.path.isdir(root):
        return None, None
    try:
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if pattern and not re.search(pattern, fn):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    t = os.path.getmtime(p)
                except OSError:
                    continue
                if best_t is None or t > best_t:
                    best_f, best_t = p, t
    except OSError as e:
        log("遍历目录失败 %s: %s" % (root, e))
    return best_f, best_t


def _freshness(mtime, now):
    """返回 (active, detail)：active=运行中？detail=描述。"""
    aw = CONFIG["activity"]["active_window_s"]
    rw = CONFIG["activity"]["recent_window_s"]
    if mtime is None:
        return False, "no-session"
    age = now - mtime
    if age <= aw:
        return True, "running"
    if age <= rw:
        return False, "recent"
    return False, "idle"


def dsh_status(now):
    root = CONFIG["dsh_sessions_dir"] or os.path.join(home_dir(), ".dsh", "sessions")
    newest, mt = newest_mtime_under(root, r"session\.jsonl\.zstd$")
    active, detail = _freshness(mt, now)
    out = {"active": active, "detail": detail, "last_activity": mt,
           "age_s": round(now - mt, 1) if mt else None, "sessions": 0,
           "awaiting": False, "pending_approvals": 0}
    if newest:
        out["newest"] = newest.replace(home_dir(), "~")
        out["sessions"] = _count_dsh_sessions(root)
        # 待审批检测（借道树莓派 zstd 解压，带缓存；仅 1 小时窗口内有效）
        if now - mt <= CONFIG["activity"].get("pending_window_s", 3600):
            n = _dsh_pending_via_pi(newest, mt, os.path.getsize(newest))
            out["pending_approvals"] = n
            out["awaiting"] = n > 0
            if n > 0:
                out["detail"] = "awaiting-approval"
    if CONFIG["debug_tail"]:
        out["tail"] = _zstd_tail(newest)
    return out


# ---- DSH 待审批检测（本机无 zstd，借道树莓派 zstd CLI 解压尾部）----
_PI_CACHE = {"key": None, "ts": 0.0, "pending": 0}
_PI_QUIET_S = 3.0          # 文件停写 N 秒才判定可能待审批
_PI_MIN_INTERVAL = 6.0     # 两次解压最小间隔


def _dsh_pending_via_pi(path, mtime, size):
    now = time.time()
    key = (path, round(mtime, 1), size)
    if _PI_CACHE["key"] == key and now - _PI_CACHE["ts"] < 20:
        return _PI_CACHE["pending"]
    if now - mtime < _PI_QUIET_S or now - _PI_CACHE["ts"] < _PI_MIN_INTERVAL:
        return _PI_CACHE["pending"]
    cfg = CONFIG.get("pi_ssh") or {}
    if not cfg.get("host"):
        return 0
    try:
        import paramiko
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(cfg["host"], username=cfg["user"], password=cfg["password"], timeout=6)
        sftp = cli.open_sftp()
        sftp.put(path, "/tmp/pet_sess.zst")
        sftp.close()
        _, out, _ = cli.exec_command(
            "zstd -dc /tmp/pet_sess.zst 2>/dev/null | tail -c 400000", timeout=90)
        tail = out.read().decode("utf-8", "replace")
        cli.close()
        n = _dsh_pending_parse(tail)
        _PI_CACHE.update(key=key, ts=now, pending=n)
        log("DSH 待审批检测 -> %d" % n)
        return n
    except Exception as e:
        log("DSH 借道解压失败: %s" % e)
        return 0


def _dsh_pending_parse(tail):
    """尾部"未闭环且需要用户响应"的工具调用数。

    用户响应型：ask_user_question（问答）或带 sandbox_permissions / justification
    （审批升级）。普通工具（pwsh/web_search 等）执行中不计数，避免误报红屏。
    """
    calls = {}          # cid -> [is_user_wait, resolved]
    order = []
    for line in tail.splitlines():
        try:
            obj = json.loads(line)
        except Exception:
            continue
        t = obj.get("type")
        if t == "tool/call":
            d = obj.get("data") or {}
            cid = d.get("callId")
            if not cid:
                continue
            args = d.get("arguments") or ""
            name = d.get("name") or ""
            user_wait = (name == "ask_user_question" or bool(
                re.search(r"sandbox_permissions|justification|danger-full-access", args)))
            if cid not in calls:
                calls[cid] = [user_wait, False]
                order.append(cid)
        elif t == "tool/result":
            cid = ((obj.get("data") or {}).get("message") or {}).get("source", {}).get("callId")
            if cid in calls:
                calls[cid][1] = True
    # 只统计文件末尾连续未闭环且属于"用户响应型"的调用
    count = 0
    for cid in reversed(order):
        user_wait, resolved = calls[cid]
        if not resolved and user_wait:
            count += 1
        elif not resolved:
            break      # 末尾是普通工具在执行中：不报
        else:
            break      # 末尾已闭环：不报
    return count


def _count_dsh_sessions(root):
    n = 0
    if os.path.isdir(root):
        for dirpath, dirs, _ in os.walk(root):
            for d in dirs:
                if d.startswith("session-"):
                    n += 1
    return n


def _zstd_tail(path, nbytes=2048):
    """可选：zstandard 解压会话尾部片段（需要 pip install zstandard）。"""
    if not path:
        return None
    try:
        import zstandard as zstd
        dctx = zstd.ZstdDecompressor()
        with open(path, "rb") as f:
            # 直接解压整个文件（会话一般不大），取尾部
            data = dctx.decompress(f.read())
        text = data.decode("utf-8", errors="replace")
        return text[-nbytes:]
    except Exception as e:
        return "zstd-error: %s" % e


def codex_status(now):
    root = CONFIG["codex_sessions_dir"] or os.path.join(home_dir(), ".codex", "sessions")
    newest, mt = newest_mtime_under(root, r"rollout-.*\.jsonl$")
    active, detail = _freshness(mt, now)
    out = {"active": active, "detail": detail, "last_activity": mt,
           "age_s": round(now - mt, 1) if mt else None,
           "awaiting": False, "pending_approvals": 0}
    if newest and CONFIG["debug_tail"]:
        out["tail"] = _codex_tail(newest)
    # 待审批：只要在 pending 窗口内（默认 1h）都算，与"是否活跃"无关
    if newest and (now - mt) <= CONFIG["activity"].get("pending_window_s", 3600):
        pending = _codex_pending(newest)
        out["pending_approvals"] = pending
        out["awaiting"] = pending > 0
        if pending > 0:
            out["detail"] = "awaiting-approval"
    return out


def _codex_tail(path, nbytes=2048):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - nbytes))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return None


def _codex_pending(path, tail_bytes=384 * 1024):
    """扫描最新 rollout jsonl 尾部，统计"已请求但未闭环"的函数调用。

    Codex 事件流两种版本兼容：
      v1: response_item.item.type == "function_call"
      v2: response_item.payload.type == "function_call"
    待审批特征：request_permissions 调用（向用户请求权限）或任何函数调用
    之后没有对应 function_call_output —— 会话停在审批处不再写入。
    """
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - tail_bytes))
            raw = f.read().decode("utf-8", errors="replace")
    except OSError as e:
        log("codex 会话读取失败: %s" % e)
        return 0

    pending = {}          # call_id -> True(已闭环)
    order = []            # 出现顺序
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") != "response_item":
            continue
        item = obj.get("item") or obj.get("payload") or {}
        it = item.get("type")
        cid = item.get("call_id")
        if it == "function_call" and cid:
            if cid not in pending:
                pending[cid] = False
                order.append(cid)
        elif it == "function_call_output" and cid:
            pending[cid] = True

    # 只统计文件末尾连续未闭环的调用（中间的已完成调用不算）
    count = 0
    for cid in reversed(order):
        if pending.get(cid) is False:
            count += 1
        else:
            break
    return count


# ---------------------------------------------------------------- 回车注入 --
def _enum_windows():
    user32 = ctypes.windll.user32
    result = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        result.append((hwnd, buf.value, pid.value))
        return True

    user32.EnumWindows(cb, 0)
    return result


def _find_codex_window(title_regex):
    pat = re.compile(title_regex, re.I)
    matches = []
    for hwnd, title, pid in _enum_windows():
        if pat.search(title):
            matches.append((hwnd, title, pid))
    if not matches:
        return None, None
    # 优先非最小化窗口
    user32 = ctypes.windll.user32
    for hwnd, title, pid in matches:
        if not user32.IsIconic(hwnd):
            return hwnd, title
    return matches[0][0], matches[0][1]


def _force_foreground(hwnd):
    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)
    if user32.GetForegroundWindow() != hwnd:
        # ALT 键技巧：先模拟一次 Alt 按下抬起，解除前台锁
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)          # VK_MENU down
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)          # VK_MENU up
        time.sleep(0.05)
        user32.SetForegroundWindow(hwnd)
    return user32.GetForegroundWindow() == hwnd


def _send_enter():
    user32 = ctypes.windll.user32
    VK_RETURN = 0x0D
    KEYEVENTF_KEYUP = 0x0002
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)


def do_approve(probe=False):
    """批准：前台模式=向当前前台窗口发回车；window 模式=定位标题窗口再回车。
    返回 (ok, detail)。probe=True 时不真正发键，只返回目标信息。"""
    if sys.platform != "win32":
        return False, "approve 仅支持 Windows（桥应跑在电脑上）"
    cfg = CONFIG["codex"]
    if cfg["mode"] == "window":
        hwnd, title = _find_codex_window(cfg["window_title"])
        if hwnd is None:
            return False, "找不到标题匹配 '%s' 的窗口" % cfg["window_title"]
        if probe:
            return True, "probe: window-mode 目标窗口 '%s'" % title
        if not _force_foreground(hwnd):
            return False, "无法激活窗口 '%s'（被系统前台锁拦截）" % title
        time.sleep(cfg["activate_delay_s"])
        _send_enter()
        return True, "已向窗口 '%s' 发送回车" % title
    # foreground 模式：直接发给当前前台窗口
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if probe:
        return True, "probe: foreground-mode 当前前台窗口 hwnd=%d（按 K1 前请把 Codex 窗口点到最前）" % hwnd
    _send_enter()
    return True, "已向前台窗口发送回车 (hwnd=%d)" % hwnd


# ---------------------------------------------------------------- HTTP ----
SYS = SystemStats()
STATUS_CACHE = {"data": None, "ts": 0.0}
CACHE_LOCK = threading.Lock()
CACHE_TTL = 1.5


def build_status():
    now = time.time()
    return {
        "ok": True,
        "ts": now,
        "dsh": dsh_status(now),
        "codex": codex_status(now),
        "system": SYS.snapshot(),
        "bridge": {"name": APP_NAME, "time": time.strftime("%Y-%m-%d %H:%M:%S")},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = APP_NAME

    def _authed(self):
        q = parse_qs(urlparse(self.path).query)
        token = (q.get("token") or [None])[0] or self.headers.get("X-Token")
        if not token or not hmac.compare_digest(token, CONFIG["token"]):
            self._json({"ok": False, "error": "unauthorized"}, 401)
            return False
        return True

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._json({"ok": True, "app": APP_NAME})
            return
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                ("%s\nGET /status  POST /approve  (token 必填)\n" % APP_NAME).encode())
            return
        if path == "/status":
            if not self._authed():
                return
            with CACHE_LOCK:
                if STATUS_CACHE["data"] and time.time() - STATUS_CACHE["ts"] < CACHE_TTL:
                    data = STATUS_CACHE["data"]
                else:
                    data = build_status()
                    STATUS_CACHE["data"] = data
                    STATUS_CACHE["ts"] = time.time()
            self._json(data)
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/approve":
            if not self._authed():
                return
            probe = False
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    probe = bool(body.get("probe"))
            except Exception:
                pass
            ok, detail = do_approve(probe=probe)
            log("approve%s -> ok=%s %s" % ("(probe)" if probe else "", ok, detail))
            self._json({"ok": ok, "detail": detail}, 200 if ok else 409)
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def log_message(self, fmt, *args):
        log("[http] " + (fmt % args))


def main():
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--config", default=None, help="配置文件路径")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args()
    global CONFIG_PATH, CONFIG
    if args.config:
        CONFIG_PATH = args.config
    load_config()
    if args.host:
        CONFIG["bind_host"] = args.host
    if args.port:
        CONFIG["port"] = args.port
    if CONFIG["token"] == "change-me-please":
        log("[!] 警告：token 仍是默认值，请修改 %s 后再对外使用" % CONFIG_PATH)

    srv = ThreadingHTTPServer((CONFIG["bind_host"], CONFIG["port"]), Handler)
    log("桥已启动 http://%s:%d  (token=%s)" % (
        CONFIG["bind_host"], CONFIG["port"], "***" if CONFIG["token"] != "change-me-please" else "默认!"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("退出")


if __name__ == "__main__":
    main()
