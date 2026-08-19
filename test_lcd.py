#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_lcd.py —— 硬件自检（真机调试用）

在树莓派上运行：python3 test_lcd.py
  1. 依次显示 红/绿/蓝/白/黑 纯色，检查屏幕接线与颜色顺序
  2. 显示 128x160 网格 + 中心红点，检查偏移/旋转是否正确
  3. 长条显示按键状态：按下 K1~K4 对应方块变亮
  4. 按 Ctrl+C 退出

参数：
  --mode raw   只测屏幕（不测按键）
"""
import argparse
import sys
import time

import config as C


def show_color(dev, rgb, name):
    from PIL import Image
    img = Image.new("RGB", (C.SCREEN_W, C.SCREEN_H), rgb)
    dev.display(img)
    print(f"[屏幕] {name} {rgb}")
    time.sleep(1.2)


def show_grid(dev):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (C.SCREEN_W, C.SCREEN_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([1, 1, C.SCREEN_W - 2, C.SCREEN_H - 2], outline=(0, 0, 0), width=2)
    for x in range(0, C.SCREEN_W, 8):
        d.line([x, 0, x, C.SCREEN_H], fill=(180, 180, 180))
    for y in range(0, C.SCREEN_H, 8):
        d.line([0, y, C.SCREEN_W, y], fill=(180, 180, 180))
    d.rectangle([C.SCREEN_W // 2 - 2, C.SCREEN_H // 2 - 2,
                 C.SCREEN_W // 2 + 2, C.SCREEN_H // 2 + 2], fill=(255, 0, 0))
    dev.display(img)
    print("[屏幕] 网格 + 中心红点（检查偏移/旋转）")
    time.sleep(3)


def show_buttons(dev):
    from PIL import Image, ImageDraw
    try:
        from gpiozero import Button
    except ImportError:
        print("[按键] 无 gpiozero，跳过按键测试")
        return
    btns = {name: Button(pin, pull_up=True, bounce_time=0.05)
            for name, pin in C.BUTTONS.items()}
    img = Image.new("RGB", (C.SCREEN_W, C.SCREEN_H), (20, 20, 20))
    d = ImageDraw.Draw(img)
    xs = [8, 40, 72, 104]
    print("[按键] 按下 K1~K4 对应方块会变亮，Ctrl+C 退出")
    try:
        while True:
            for name, x in zip(C.BUTTONS, xs):
                on = btns[name].is_pressed
                c = (0, 255, 80) if on else (60, 60, 60)
                d.rectangle([x, 70, x + 24, 94], fill=c)
            dev.display(img)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["screen", "buttons", "all"], default="all")
    args = ap.parse_args()

    from backend import TFTDisplay
    dev = TFTDisplay()
    try:
        if args.mode in ("screen", "all"):
            show_color(dev, (255, 0, 0), "红")
            show_color(dev, (0, 255, 0), "绿")
            show_color(dev, (0, 0, 255), "蓝")
            show_color(dev, (255, 255, 255), "白")
            show_color(dev, (0, 0, 0), "黑")
            show_grid(dev)
        if args.mode in ("buttons", "all"):
            show_buttons(dev)
    finally:
        dev.close()


if __name__ == "__main__":
    main()