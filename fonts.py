# -*- coding: utf-8 -*-
"""中文字体自动检测：优先找系统自带中文字体，找不到就退回默认字体（英文）"""
import os
from PIL import ImageFont

_CANDIDATES = [
    # Windows
    r"C:/Windows/Fonts/msyh.ttc",
    r"C:/Windows/Fonts/msyh.ttf",
    r"C:/Windows/Fonts/simhei.ttf",
    r"C:/Windows/Fonts/simsun.ttc",
    r"C:/Windows/Fonts/Deng.ttf",
    # macos
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    # Linux / 树莓派
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/oh-my-rpi/bin/rpi-fonts/NotoSansCJK-Regular.ttc",
]

_FONT_PATH = None
for _p in _CANDIDATES:
    if os.path.exists(_p):
        _FONT_PATH = _p
        break


def cjk_available() -> bool:
    """是否找到了支持中文的字体"""
    if not _FONT_PATH:
        return False
    name = os.path.basename(_FONT_PATH).lower()
    if any(k in name for k in ("dejavu",)):
        return False
    return True


def font(size: int = 12):
    """返回指定字号字体；优先中文字体，否则用 Pillow 内置字体。"""
    if _FONT_PATH:
        try:
            return ImageFont.truetype(_FONT_PATH, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_text(draw, xy, text, size=12, fill=None, anchor=None):
    """画文字：中文优先、自动带 1px 描边阴影让文字更清晰"""
    f = font(size)
    x, y = xy
    if fill is None:
        fill = (66, 50, 40)
    if anchor is not None:
        # 用深色画一层偏移作为描边
        sx = {"lm": 0, "mm": 0, "rm": 0}.get(anchor, 0)
        draw.text((x - 1, y), text, font=f, fill=(255, 255, 255, 120), anchor=anchor)
        draw.text((x + 1, y), text, font=f, fill=(255, 255, 255, 120), anchor=anchor)
        draw.text((x, y - 1), text, font=f, fill=(255, 255, 255, 120), anchor=anchor)
        draw.text((x, y + 1), text, font=f, fill=(255, 255, 255, 120), anchor=anchor)
    else:
        draw.text((x - 1, y), text, font=f, fill=(255, 255, 255, 120))
        draw.text((x + 1, y), text, font=f, fill=(255, 255, 255, 120))
        draw.text((x, y - 1), text, font=f, fill=(255, 255, 255, 120))
        draw.text((x, y + 1), text, font=f, fill=(255, 255, 255, 120))
    draw.text((x, y), text, font=f, fill=fill, anchor=anchor)


def wrap_text(text, max_width, size=12):
    """按像素宽度对文字换行（逐字符累加，兼容中西文）"""
    f = font(size)
    lines = []
    cur = ""
    for ch in text:
        trial = cur + ch
        w = f.getlength(trial)
        if w > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines