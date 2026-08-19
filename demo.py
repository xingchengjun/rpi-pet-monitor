# -*- coding: utf-8 -*-
"""demo.py —— 无硬件离线演示 / 动画帧导出

在电脑上即可运行，用来预览桌宠长什么样：
    python demo.py --window     # 弹出 tkinter 窗口实时预览
    python demo.py              # 导出 PNG 到 out_png/ 看静态帧

脚本会自动演示：待机 → 撒娇 → 吃饭 → 跳舞 → 闹饿 → 睡觉 → 起床 → 踱步
"""
import argparse
import time

from backend import make_display
from painter import Painter
from pet import Pet


def script(pet, t):
    """按时间轴触发交互，演示各种状态"""
    if 1.0 <= t < 1.01:
        pet.on_touch()
    if 3.0 <= t < 3.01:
        pet.on_feed()
    if 5.0 <= t < 5.01:
        pet.on_play()
    if 8.0 <= t < 8.01:
        pet.hunger = 10
        pet._enter("sad", "hungry", dur=2.5)
    if 11.0 <= t < 11.01:
        pet.on_sleep()
    if 15.0 <= t < 15.01:
        pet.on_sleep()
    if 17.0 <= t < 17.01:
        pet._start_walk()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", action="store_true", help="用 tkinter 窗口实时预览")
    ap.add_argument("--seconds", type=float, default=20, help="跑多久（秒）")
    ap.add_argument("--outdir", default="out_png")
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

    mode = "preview" if args.window else "dump"
    disp = make_display(mode, scale=args.scale, outdir=args.outdir)
    pet = Pet()
    painter = Painter()

    end = args.seconds
    t0 = time.perf_counter()
    prev = t0
    n = 0
    while True:
        now = time.perf_counter()
        dt = now - prev
        prev = now
        t = now - t0
        if t >= end:
            break
        script(pet, t)
        pet.tick(dt)
        disp.show(painter.render(pet))
        n += 1
        # 统一按 ~20fps 节奏
        time.sleep(max(0.0, 0.05 - (time.perf_counter() - now)))

    disp.close()
    print(f"演示结束：{n} 帧，输出到 {args.outdir}/ 或窗口")


if __name__ == "__main__":
    main()