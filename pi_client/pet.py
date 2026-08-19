# -*- coding: utf-8 -*-
"""
pet.py — 树莓派 4B + ST7735S 128x160 桌宠状态屏主程序。

功能：
- 轮询 PC 端桥服务（bridge.py）获取 DSH/Codex 状态、待审批数、CPU/内存
- 两屏 UI：桌宠屏 ⇄ 系统监控屏（空闲时 K1/K2 切换）
- 有待审批时：K1 = 批准（让桥向 Codex 终端发回车），屏幕显示徽标
- K3 = 立即刷新，K4 = 背光开关
- 断线自动重连，开机 systemd 自启

依赖：pip install luma.lcd gpiozero
接线见 README.md（默认 GPIO 见下方 CONFIG）。
"""

import json
import os
import queue
import sys
import threading
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------- 配置 -----
CONFIG = {
    # 桥服务地址（PC 局域网 IP:端口，token 与 bridge_config.json 保持一致）
    "bridge_url": "http://192.168.3.8:8123",
    "token": "change-me-please",
    "poll_interval_s": 2.0,
    # 活动判定：桥返回的 last_activity 超过该秒数视为空闲（桥侧也有该阈值）
    "pet_name": "Whale",          # 屏幕角落显示的名字
    "pet_sprite": "WHALE",        # WHALE / BLOB / SPIRIT（sprite_source=builtin 时）
    "sprite_source": "auto",      # auto=有鲸鱼娘素材就用(assets/whale)，否则用内置像素
                                  # whale=强制鲸鱼娘 | builtin=强制内置像素
    "backlight_pin": None,        # BLK 若接 GPIO 则填引脚号（如 26），否则 None
    # ST7735 引脚（BCM 编号）与显示参数，与 README 接线表一致，可改
    "lcd": {
        "dc": 24,
        "rst": 25,
        "rotation": 2,            # 实测屏幕倒置 -> 2=旋转180°；0/1/2/3 可选
        "bgr": False,             # 实测红蓝对调 -> 本面板是 RGB，用 False
        "invert": False,          # 白屏/黑屏反相时改 True
        "spi_speed": 16000000,    # SPI 时钟 Hz（提速减少刷屏撕裂/重影）
    },
    # 按键 BCM 引脚（K1 最靠近屏幕）
    "buttons": {"K1": 5, "K2": 6, "K3": 13, "K4": 19},
}

# 当前会话内可被按键覆盖的开关
_backlight_on = True


# ---------------------------------------------------------------- 日志 -----
def log(msg):
    print("[pet %s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def load_pet_config():
    """从同目录 pet_config.json 覆盖默认配置（token/bridge_url 等）。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pet_config.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        for k in ("bridge_url", "token", "pet_name", "sprite_source",
                  "backlight_pin", "poll_interval_s", "pet_sprite"):
            if k in user:
                CONFIG[k] = user[k]
        log("已加载配置 %s" % path)
    except Exception as e:
        log("pet_config.json 读取失败（用默认配置）: %s" % e)


# ---------------------------------------------------------------- 桥通信 ----
def fetch_status():
    """GET /status，失败返回 None。"""
    url = CONFIG["bridge_url"] + "/status?token=" + urllib.parse.quote(CONFIG["token"])
    req = urllib.request.Request(url, headers={"User-Agent": "pi-pet/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None


def send_approve():
    """POST /approve，让桥向 Codex 终端发回车（批准）。"""
    url = CONFIG["bridge_url"] + "/approve"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json",
                 "X-Token": CONFIG["token"],
                 "User-Agent": "pi-pet/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- 轮询线程 --
def poller(status_holder, evt_queue):
    """每 poll_interval_s 拉一次状态，写入共享 dict；状态变化时投递 UI 事件。"""
    last_sig = None
    while True:
        st = fetch_status()
        with status_holder["lock"]:
            status_holder["data"] = st
            status_holder["ts"] = time.time()
        # 状态特征变化 -> 通知主循环刷新/切宠物表情
        if st is None:
            sig = "offline"
        else:
            sig = "p%d|d%d|c%d" % (
                int(st.get("codex", {}).get("pending_approvals", 0) or 0),
                1 if st.get("dsh", {}).get("active") else 0,
                1 if st.get("codex", {}).get("active") else 0,
            )
        if sig != last_sig:
            last_sig = sig
            try:
                evt_queue.put_nowait(("refresh", sig))
            except queue.Full:
                pass
        time.sleep(CONFIG["poll_interval_s"])


# ---------------------------------------------------------------- 按键 ----
def setup_buttons():
    """返回 {key: Button}。luma/GPIO 失败时返回 None 让程序进入"仅显示"模式。"""
    try:
        from gpiozero import Button
    except Exception as e:
        log("gpiozero 不可用，按键禁用: %s" % e)
        return None
    btns = {}
    for name, pin in CONFIG["buttons"].items():
        try:
            # 低电平触发（按下接地），软件消抖 60ms
            btns[name] = Button(pin, pull_up=True, bounce_time=0.06)
        except Exception as e:
            log("按键 %s 初始化失败: %s" % (name, e))
    return btns or None


def attach_button_handlers(buttons, evt_queue):
    if not buttons:
        return
    for name, btn in buttons.items():
        btn.when_pressed = lambda n=name: _press(n, evt_queue)


def _press(name, evt_queue):
    try:
        evt_queue.put_nowait(("key", name))
    except queue.Full:
        pass


# ---------------------------------------------------------------- 屏幕 ----
def setup_display():
    """初始化 ST7735（直连驱动，不依赖 luma/RPi.GPIO），失败返回 None。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from st7735_driver import ST7735
        l = CONFIG["lcd"]
        dev = ST7735(dc=l["dc"], rst=l["rst"], rotation=l["rotation"],
                     bgr=l["bgr"], invert=l["invert"], spi_speed=l["spi_speed"])
        log("ST7735 驱动初始化成功 128x160 (rotation=%d)" % l["rotation"])
        return dev
    except Exception as e:
        log("屏幕初始化失败（检查接线/spi 权限/GPIO 占用）: %s" % e)
        return None


def set_backlight(dev, on):
    global _backlight_on
    _backlight_on = on
    # BLK 接 GPIO 时用 gpiozero LED 控制；默认接 3.3V 常亮，这里仅记录
    if CONFIG["backlight_pin"] is not None:
        try:
            from gpiozero import LED
            led = LED(CONFIG["backlight_pin"])
            if on:
                led.on()
            else:
                led.off()
        except Exception as e:
            log("背光控制失败: %s" % e)


# ---------------------------------------------------------------- 预览模式 ----
def _preview_status(step):
    """预览用模拟状态：循环 待审批 -> 工作中 -> 空闲。"""
    phase = step % 12
    if phase < 4:
        return {"dsh": {"active": False}, "codex": {"active": False,
                "awaiting": True, "pending_approvals": 1},
                "system": {"cpu": 45, "mem": 60, "mem_used_gb": 9.6, "mem_total_gb": 15.8}}
    if phase < 8:
        return {"dsh": {"active": True}, "codex": {"active": True,
                "awaiting": False, "pending_approvals": 0},
                "system": {"cpu": 80, "mem": 66, "mem_used_gb": 10.4, "mem_total_gb": 15.8}}
    return {"dsh": {"active": False}, "codex": {"active": False,
            "awaiting": False, "pending_approvals": 0},
            "system": {"cpu": 6, "mem": 55, "mem_used_gb": 8.7, "mem_total_gb": 15.8}}


def _preview_variant(step):
    ph = step % 12
    return "alert" if ph < 4 else ("work" if ph < 8 else ("blink" if ph % 2 else "idle"))


def run_preview_frames(count):
    """把两屏各渲染 count 帧存到 preview_out/（无需硬件，PC 可直接看）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import art
    whale_anims = art.load_whale_anims()
    pet_imgs = {v: art.render_sprite(CONFIG["pet_sprite"], v, scale=3)
                for v in ("idle", "blink", "work", "alert")}
    use_whale = CONFIG["sprite_source"] == "whale" or (
        CONFIG["sprite_source"] == "auto" and bool(whale_anims))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "preview_out")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    for i in range(count):
        now = t0 + i * 0.12
        st = _preview_status(i)
        if use_whale:
            pet = art.whale_frame(whale_anims, _preview_variant(i), now) or pet_imgs["idle"]
        else:
            pet = pet_imgs[_preview_variant(i)]
        clock = time.strftime("%H:%M", time.localtime(now))
        art.compose_pet_screen(st, pet, clock, CONFIG["pet_name"]).save(
            os.path.join(out, "pet_%03d.png" % i))
        art.compose_monitor_screen(st, clock, True).save(
            os.path.join(out, "mon_%03d.png" % i))
    log("预览帧已生成 -> %s (%d 组)" % (out, count))


def run_preview_window(seconds=20):
    """tkinter 实时预览窗口（无硬件）。ESC 退出，1/2 切换两屏。"""
    import tkinter as tk
    from PIL import ImageTk
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import art
    whale_anims = art.load_whale_anims()
    pet_imgs = {v: art.render_sprite(CONFIG["pet_sprite"], v, scale=3)
                for v in ("idle", "blink", "work", "alert")}
    use_whale = CONFIG["sprite_source"] == "whale" or (
        CONFIG["sprite_source"] == "auto" and bool(whale_anims))

    root = tk.Tk()
    root.title("Pi Pet Preview (128x160 x2)")
    label = tk.Label(root)
    label.pack()
    state = {"screen": "pet", "step": 0, "quit": False}

    def on_key(e):
        if e.keysym == "Escape":
            state["quit"] = True
            root.destroy()
        elif e.keysym in ("1", "2"):
            state["screen"] = "pet" if e.keysym == "1" else "monitor"

    root.bind("<Key>", on_key)

    def tick():
        if state["quit"]:
            return
        now = time.time()
        i = state["step"]
        st = _preview_status(i)
        if use_whale:
            pet = art.whale_frame(whale_anims, _preview_variant(i), now) or pet_imgs["idle"]
        else:
            pet = pet_imgs[_preview_variant(i)]
        clock = time.strftime("%H:%M")
        if state["screen"] == "pet":
            img = art.compose_pet_screen(st, pet, clock, CONFIG["pet_name"])
        else:
            img = art.compose_monitor_screen(st, clock, True)
        img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
        label._img = ImageTk.PhotoImage(img)  # noqa: SLF001  (持引用防 GC)
        label.config(image=label._img)
        state["step"] += 1
        root.after(120, tick)

    root.after(120, tick)
    root.after(int(seconds * 1000), root.destroy)
    root.mainloop()


# ---------------------------------------------------------------- 主循环 ----
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="树莓派桌宠状态屏")
    ap.add_argument("--preview-frames", type=int, default=0,
                    help="无硬件：渲染 N 组预览帧到 preview_out/")
    ap.add_argument("--preview-window", type=float, default=0,
                    help="无硬件：弹出实时预览窗口（秒数）")
    args = ap.parse_args(argv)

    load_pet_config()

    if args.preview_frames > 0:
        run_preview_frames(args.preview_frames)
        return
    if args.preview_window > 0:
        run_preview_window(args.preview_window)
        return

    import urllib.parse  # noqa: F401  (fetch_status 用到)

    status_holder = {"lock": threading.Lock(), "data": None, "ts": 0.0}
    evt_queue = queue.Queue(maxsize=16)

    dev = setup_display()
    buttons = setup_buttons()
    attach_button_handlers(buttons, evt_queue)
    set_backlight(dev, True)

    t = threading.Thread(target=poller, args=(status_holder, evt_queue), daemon=True)
    t.start()
    log("已启动，轮询 %s，宠物=%s" % (CONFIG["bridge_url"], CONFIG["pet_sprite"]))

    screen = "pet"            # pet | monitor
    blink_t = 0.0
    blink = False
    last_draw = 0.0
    approve_cooldown = 0.0
    pi_ok = True

    # 导入 art（放同目录）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import art

    # 预渲染内置像素变体 + 尝试加载鲸鱼娘素材
    pet_imgs = {
        v: art.render_sprite(CONFIG["pet_sprite"], v, scale=3)
        for v in ("idle", "blink", "work", "alert")
    }
    whale_anims = art.load_whale_anims()
    use_whale = CONFIG["sprite_source"] == "whale" or (
        CONFIG["sprite_source"] == "auto" and bool(whale_anims))
    if use_whale and whale_anims:
        log("使用鲸鱼娘动画素材: %s" % ", ".join(sorted(whale_anims.keys())))
    else:
        log("使用内置像素精灵: %s" % CONFIG["pet_sprite"])

    while True:
        now = time.time()

        # ---- 处理事件 ----
        try:
            while True:
                kind, payload = evt_queue.get_nowait()
                if kind == "key":
                    name = payload
                    with status_holder["lock"]:
                        st = status_holder["data"]
                    pending = 0
                    if st:
                        pending = int(st.get("codex", {}).get("pending_approvals", 0) or 0)
                    if name == "K1":
                        if (pending > 0 and CONFIG.get("approve_enabled")
                                and now > approve_cooldown):
                            approve_cooldown = now + 2.0
                            log("K1 -> 批准 (向 Codex 发回车)")
                            r = send_approve()
                            log("approve 结果: %s" % r)
                        else:
                            screen = "monitor" if screen == "pet" else "pet"
                            log("K1 -> 切换界面: %s" % screen)
                    elif name == "K2":
                        screen = "monitor" if screen == "pet" else "pet"
                        log("K2 -> 切换界面: %s" % screen)
                    elif name == "K3":
                        log("K3 -> 立即刷新")
                        with status_holder["lock"]:
                            status_holder["data"] = fetch_status()
                    elif name == "K4":
                        set_backlight(dev, not _backlight_on)
                        log("K4 -> 背光 %s" % ("开" if _backlight_on else "关"))
                elif kind == "refresh":
                    log("状态变化: %s" % payload)
        except queue.Empty:
            pass

        # ---- 每 0.25s 重绘一次（顺带动画节拍） ----
        if now - last_draw >= 0.25:
            last_draw = now
            if now - blink_t > 2.4:
                blink_t = now
                blink = True
            elif now - blink_t > 0.25:
                blink = False

            with status_holder["lock"]:
                st = status_holder["data"]

            if st is None:
                pi_ok = False
                variant = "alert"
            else:
                pi_ok = True
                cod = st.get("codex", {})
                dsh = st.get("dsh", {})
                if (cod.get("awaiting") or int(cod.get("pending_approvals", 0) or 0) > 0
                        or dsh.get("awaiting") or int(dsh.get("pending_approvals", 0) or 0) > 0):
                    variant = "alert"
                elif cod.get("active") or dsh.get("active"):
                    variant = "work"
                elif blink:
                    variant = "blink"
                else:
                    variant = "idle"

            clock_str = time.strftime("%H:%M")
            # 取宠物当前帧（鲸鱼娘动画按时间取帧 / 内置像素按状态取）
            if use_whale:
                pet_frame = art.whale_frame(whale_anims, variant, now) or pet_imgs[variant]
            else:
                pet_frame = pet_imgs[variant]
            if screen == "pet":
                frame = art.compose_pet_screen(st, pet_frame, clock_str,
                                               CONFIG["pet_name"])
            else:
                frame = art.compose_monitor_screen(st, clock_str, pi_ok)

            if dev is not None:
                dev.display(frame)
            else:
                # 无屏调试模式：打印状态摘要
                if int(now) % 3 == 0:
                    s = "OFFLINE" if st is None else "P%d cpu%d%% mem%d%%" % (
                        int(st.get("codex", {}).get("pending_approvals", 0) or 0),
                        int(st.get("system", {}).get("cpu", 0) or 0),
                        int(st.get("system", {}).get("mem", 0) or 0),
                    )
                    log("[no-lcd] %s | %s" % (screen, s))

        time.sleep(0.05)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        log("退出")
