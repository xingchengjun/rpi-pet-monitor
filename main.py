# -*- coding: utf-8 -*-
"""main.py —— 树莓派桌宠主程序

用法：
    python3 main.py                  # 默认在 TFT 屏上运行（树莓派）
    python3 main.py --mode preview   # 电脑上用窗口预览（无硬件）
    python3 main.py --mode dump      # 把动画帧导出 PNG

按键 → 交互：
    K1 触摸        K2 喂食      K3 睡觉/叫醒      K4 一起玩
"""
import argparse
import signal
import sys
import time
from queue import Queue

import config as C
from backend import make_display
from painter import Painter
from pet import Pet


def parse_args():
    ap = argparse.ArgumentParser(description="ST7735S 桌宠")
    ap.add_argument("--mode", choices=["tft", "preview", "dump"], default="tft",
                    help="tft=真机屏幕 preview=窗口预览 dump=导出PNG")
    ap.add_argument("--scale", type=int, default=3, help="preview 窗口缩放倍数")
    ap.add_argument("--outdir", default="out_png", help="dump 模式输出目录")
    return ap.parse_args()


def setup_buttons(queue: Queue):
    """用 gpiozero 把四个按键事件推入队列（仅树莓派模式使用）"""
    from gpiozero import Button

    actions = {
        "K1": lambda p: p.on_touch(),
        "K2": lambda p: p.on_feed(),
        "K3": lambda p: p.on_sleep(),
        "K4": lambda p: p.on_play(),
    }

    def _mk(pin, name):
        b = Button(pin, pull_up=True, bounce_time=0.06)
        b.when_pressed = lambda: queue.put((actions[name], name))
        return b

    return [_mk(PIN, NAME) for NAME, PIN in C.BUTTONS.items()]


def main():
    args = parse_args()

    disp = make_display(args.mode, scale=args.scale, outdir=args.outdir)
    pet = Pet()
    painter = Painter()

    queue = Queue()
    buttons = None
    if args.mode == "tft":
        try:
            buttons = setup_buttons(queue)
        except Exception as e:
            print(f"[warn] 按键初始化失败（继续运行，仅显示）: {e}")

    def _shutdown(sig, frm):
        print("\n再见，桌宠睡着了…")
        disp.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    prev = time.perf_counter()
    print(f"桌宠 {pet.name} 已启动（模式 {args.mode}），Ctrl+C 退出")

    try:
        while True:
            now = time.perf_counter()
            dt = min(now - prev, 0.2)
            prev = now

            # 处理按键
            while not queue.empty():
                fn, name = queue.get()
                fn(pet)
                print(f"[按键] {name} → {pet.state}")

            pet.tick(dt)
            disp.show(painter.render(pet))
            time.sleep(max(0.0, C.FRAME_MS / 1000 - (time.perf_counter() - now)))
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()