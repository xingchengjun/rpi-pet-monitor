# -*- coding: utf-8 -*-
"""
test_lcd.py — 硬件自检（接线后先跑这个）。
1) 依次显示 红/绿/蓝/白/黑 纯色（确认颜色与接线）
2) 显示网格（确认旋转方向与偏移）
3) 按键测试：按 K1-K4，屏幕显示按下了哪个键（确认按键与引脚）
退出：Ctrl+C
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw  # noqa: E402

CONFIG = {
    "lcd": {"dc": 24, "rst": 25, "rotation": 2, "bgr": False, "invert": False},
    "buttons": {"K1": 5, "K2": 6, "K3": 13, "K4": 19},
}


def display():
    from st7735_driver import ST7735
    return ST7735(dc=CONFIG["lcd"]["dc"], rst=CONFIG["lcd"]["rst"],
                  rotation=CONFIG["lcd"]["rotation"], bgr=CONFIG["lcd"]["bgr"],
                  invert=CONFIG["lcd"]["invert"])


def fill(dev, rgb, text=None):
    img = Image.new("RGB", (128, 160), rgb)
    if text:
        d = ImageDraw.Draw(img)
        d.text((8, 8), text, fill=(0, 0, 0) if sum(rgb) > 380 else (255, 255, 255))
    dev.display(img)


def grid(dev):
    img = Image.new("RGB", (128, 160), (20, 20, 30))
    d = ImageDraw.Draw(img)
    for x in range(0, 128, 16):
        d.line([x, 0, x, 159], fill=(60, 90, 140))
    for y in range(0, 160, 16):
        d.line([0, y, 127, y], fill=(60, 90, 140))
    d.rectangle([0, 0, 127, 159], outline=(255, 255, 255))
    dev.display(img)


def buttons(dev):
    from gpiozero import Button
    img = Image.new("RGB", (128, 160), (10, 14, 24))
    d = ImageDraw.Draw(img)
    d.text((10, 60), "press K1-K4", fill=(255, 255, 255))
    dev.display(img)
    pressed = {k: Button(pin, pull_up=True, bounce_time=0.05)
               for k, pin in CONFIG["buttons"].items()}
    try:
        while True:
            for k, b in pressed.items():
                if b.is_pressed:
                    img = Image.new("RGB", (128, 160), (10, 14, 24))
                    d = ImageDraw.Draw(img)
                    d.text((40, 60), ">> %s <<" % k, fill=(255, 220, 80))
                    d.text((20, 90), "released to continue", fill=(150, 150, 150))
                    dev.display(img)
                    while b.is_pressed:
                        time.sleep(0.02)
    except KeyboardInterrupt:
        pass


def main():
    dev = display()
    print("屏幕已初始化。3 秒后开始纯色测试...")
    time.sleep(3)
    for name, rgb in [("RED", (255, 0, 0)), ("GREEN", (0, 255, 0)),
                      ("BLUE", (0, 0, 255)), ("WHITE", (255, 255, 255)),
                      ("BLACK", (0, 0, 0))]:
        print("显示 %s，看屏幕是否一致（红蓝颠倒改 bgr=False）" % name)
        fill(dev, rgb, name)
        time.sleep(1.5)
    print("显示网格，确认旋转（不对改 rotation=0/90/180/270）")
    grid(dev)
    time.sleep(4)
    print("按键测试：依次按 K1-K4（键值应从左到右对应 5/6/13/19）")
    buttons(dev)
    print("完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("退出")
