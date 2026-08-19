# -*- coding: utf-8 -*-
"""backend.py —— 显示后端

- TFTDisplay   树莓派 + ST7735S（依赖 luma.lcd，仅树莓派上可用）
- PreviewDisplay  本机窗口预览（tkinter，Windows/Mac/Linux 都能用，开发调试用）
- DumpDisplay  把每一帧存成 PNG（离线渲染视频素材 / 调试）
"""
import os

import config as C


class TFTDisplay:
    def __init__(self):
        from luma.core.interface.serial import spi
        from luma.lcd.device import st7735
        self.serial = spi(
            port=C.SPI_PORT, device=C.SPI_CS,
            cs=0,                      # SPI slave select
            gpio_DC=C.GPIO_DC,
            gpio_BCLK=11,              # SCLK（BCM 11）
            gpio_RST=C.GPIO_RST,
        )
        kw = dict(width=C.SCREEN_W, height=C.SCREEN_H,
                  rotate=C.ROTATE, h_offset=C.H_OFFSET, v_offset=C.V_OFFSET)
        # 部分模块颜色顺序相反 / 需要反色，这里容错传入
        for k, v in (("bgr", not C.RGB_ORDER), ("inverse", False)):
            if v:
                kw[k] = v
        try:
            self.device = st7735(self.serial, **kw)
        except TypeError:
            kw.pop("bgr", None)
            kw.pop("inverse", None)
            self.device = st7735(self.serial, **kw)
        # 背光
        if C.GPIO_BL:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(C.GPIO_BL, GPIO.OUT)
                GPIO.output(C.GPIO_BL, GPIO.HIGH)
            except Exception:
                pass

    def show(self, img):
        self.device.display(img)

    def close(self):
        try:
            self.device.cleanup()
        except Exception:
            pass


class PreviewDisplay:
    """tkinter 窗口预览（用于在电脑上调试效果）"""

    def __init__(self, scale=3, title="桌宠预览（点击窗口右上角 X 退出）"):
        import tkinter as tk
        from PIL import ImageTk
        self.tk = tk
        self.ImageTk = ImageTk
        self.scale = scale
        self.root = tk.Tk()
        self.root.title(title)
        w, h = C.SCREEN_W * scale, C.SCREEN_H * scale
        self.root.geometry(f"{w}x{h}")
        self.canvas = tk.Canvas(self.root, width=w, height=h,
                                highlightthickness=0, bg="black")
        self.canvas.pack()
        self.photo = None
        self.root.update()

    def show(self, img):
        im = img.resize((C.SCREEN_W * self.scale, C.SCREEN_H * self.scale),
                        self.ImageTk.Image.NEAREST)
        self.photo = self.ImageTk.PhotoImage(im)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.root.update()
        # 让用户还能通过主循环干活
        self.root.update()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


class DumpDisplay:
    """把每一帧保存为 out_dirs/xxxx.png"""

    def __init__(self, outdir="out_png"):
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.n = 0

    def show(self, img):
        img.save(os.path.join(self.outdir, f"{self.n:05d}.png"))
        self.n += 1
        if self.n % 20 == 0:
            print(f"[dump] 已保存 {self.n} 帧")

    def close(self):
        print(f"[dump] 完成，共 {self.n} 帧 → {self.outdir}/")


def make_display(mode: str, **kw):
    if mode == "tft":
        return TFTDisplay()
    if mode == "preview":
        return PreviewDisplay(scale=kw.get("scale", 3))
    if mode == "dump":
        return DumpDisplay(outdir=kw.get("outdir", "out_png"))
    raise ValueError(f"未知显示模式: {mode}")