# -*- coding: utf-8 -*-
"""
st7735_driver.py — ST7735S 128x160 直连驱动（不依赖 luma.lcd / RPi.GPIO）。

背景：Debian 13 (trixie) 上 RPi.GPIO+lgpio 后端损坏，luma.lcd 无法初始化。
本驱动用 spidev 发数据 + python3-gpiod（libgpiod v2，系统自带）控制 DC/RST，
lgpio 作为 gpiod 不可用时的后备。接口与 luma 兼容：dev.display(PIL Image)。

接线：CS=CE0(SPI0), SCL=GPIO11, SDA=GPIO10, DC=GPIO24, RST=GPIO25, BLK 可接 GPIO。
"""

import time

import spidev
from PIL import Image

W, H = 128, 160

# 旋转 -> MADCTL（竖屏 128x160 默认 rotation=0）
_MADCTL = {0: 0x00, 1: 0x60, 2: 0xC0, 3: 0xA0}


class _Gpio:
    """gpiod v2 优先，lgpio 后备。"""

    def __init__(self):
        self._mod = None
        self._chip = None
        self._req = None
        self._h = None
        try:
            import gpiod
            self._mod = "gpiod"
            self._chip = gpiod.Chip("/dev/gpiochip0")
        except Exception:
            try:
                import lgpio
                self._mod = "lgpio"
                self._h = lgpio.gpiochip_open(0)
            except Exception as e:
                raise RuntimeError("无可用的 GPIO 后端: %s" % e)

    def claim_outputs(self, pins):
        """pins: {bcm: 初始电平 0/1}"""
        if self._mod == "gpiod":
            import gpiod
            cfg = {p: gpiod.LineSettings(
                direction=gpiod.line.Direction.OUTPUT,
                output_value=(gpiod.line.Value.ACTIVE if v else gpiod.line.Value.INACTIVE))
                for p, v in pins.items()}
            self._req = self._chip.request_lines(cfg, consumer="st7735")
        else:
            import lgpio
            for p, v in pins.items():
                lgpio.gpio_claim_output(self._h, p, 1 if v else 0)

    def write(self, pin, value):
        if self._mod == "gpiod":
            import gpiod
            self._req.set_value(pin, gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE)
        else:
            import lgpio
            lgpio.gpio_write(self._h, pin, 1 if value else 0)

    def close(self):
        try:
            if self._mod == "gpiod" and self._req is not None:
                self._req.release()
            elif self._mod == "lgpio" and self._h is not None:
                import lgpio
                lgpio.gpiochip_close(self._h)
        except Exception:
            pass


class ST7735:
    def __init__(self, dc=24, rst=25, backlight=None, rotation=0, bgr=True,
                 invert=True, spi_speed=8000000):
        self.dc, self.rst, self.bl = dc, rst, backlight
        self.rotation = rotation % 4
        self.bgr = bgr
        self.invert = invert
        self._spi = spidev.SpiDev()
        self._spi.open(0, 0)
        self._spi.max_speed_hz = spi_speed
        self._spi.mode = 0
        self.gpio = _Gpio()
        pins = {dc: 0, rst: 1}
        if backlight is not None:
            pins[backlight] = 1
        self.gpio.claim_outputs(pins)
        self._init_panel()

    # ---- 底层 ----
    def _cmd(self, byte):
        self.gpio.write(self.dc, 0)
        self._spi.xfer2([byte])

    def _data(self, buf):
        self.gpio.write(self.dc, 1)
        self._spi.xfer2(buf if isinstance(buf, list) else [buf])

    # ---- ST7735S 初始化序列 ----
    def _init_panel(self):
        self.gpio.write(self.rst, 0)
        time.sleep(0.12)
        self.gpio.write(self.rst, 1)
        time.sleep(0.12)

        seq = [
            (0x01, None),                        # SWRESET
            (0x11, None),                        # SLPOUT
            (0xB1, [0x01, 0x2C, 0x2D]),          # FRMCTR1
            (0xB2, [0x01, 0x2C, 0x2D]),          # FRMCTR2
            (0xB3, [0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D]),  # FRMCTR3
            (0xB4, [0x07]),                      # INVCTR
            (0xC0, [0xA2, 0x02, 0x84]),          # PWCTR1
            (0xC1, [0xC5]),                      # PWCTR2
            (0xC2, [0x0A, 0x00]),                # PWCTR3
            (0xC3, [0x8A, 0x2A]),                # PWCTR4
            (0xC4, [0x8A, 0xEE]),                # PWCTR5
            (0xC5, [0x0E]),                      # VMCTR1
            (0x36, [_MADCTL[self.rotation] | (0x08 if self.bgr else 0x00)]),  # MADCTL
            (0x3A, [0x05]),                      # COLMOD 16bit
            (0xE0, [0x02, 0x1C, 0x07, 0x12, 0x37, 0x32, 0x29, 0x2D,
                    0x29, 0x25, 0x2B, 0x39, 0x00, 0x01, 0x03, 0x10]),  # GMCTRP1
            (0xE1, [0x03, 0x1D, 0x07, 0x06, 0x2E, 0x2C, 0x29, 0x2D,
                    0x2E, 0x2E, 0x37, 0x3F, 0x00, 0x00, 0x02, 0x10]),  # GMCTRN1
            (0x13, None),                        # NORON
            (0x21 if self.invert else 0x20, None),  # INVON / INVOFF
            (0x29, None),                        # DISPON
        ]
        for cmd, data in seq:
            self._cmd(cmd)
            if data is not None:
                self._data(data)
            if cmd == 0x01:
                time.sleep(0.15)
            elif cmd == 0x11:
                time.sleep(0.5)
            elif cmd == 0x13:
                time.sleep(0.01)
        time.sleep(0.1)

    # ---- 上屏 ----
    def display(self, img):
        if img.size != (W, H):
            img = img.resize((W, H))
        rgb = img.convert("RGB")
        px = rgb.load()

        # 转 RGB565
        buf = bytearray(W * H * 2)
        i = 0
        for y in range(H):
            for x in range(W):
                r, g, b = px[x, y]
                v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                buf[i] = v >> 8
                buf[i + 1] = v & 0xFF
                i += 2

        # 地址窗
        self._cmd(0x2A)
        self._data([0x00, 0x00, 0x00, W - 1])
        self._cmd(0x2B)
        self._data([0x00, 0x00, 0x00, H - 1])
        self._cmd(0x2C)
        self.gpio.write(self.dc, 1)
        # spidev 单次最多 ~4096 字节，分块发送
        chunk = 4096
        for i in range(0, len(buf), chunk):
            self._spi.writebytes(buf[i:i + chunk])

    def close(self):
        try:
            self._spi.close()
        finally:
            self.gpio.close()
