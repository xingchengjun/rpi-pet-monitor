# -*- coding: utf-8 -*-
"""
gen_designs.py — 在 PC 上生成像素草稿与屏幕 mockup 预览图（design/*.png）。

运行：python design/gen_designs.py
输出：
  design/sprite_WHALE.png / sprite_BLOB.png / sprite_SPIRIT.png   (16x16 精灵 x8 放大)
  design/sprite_WHALE_variants.png                               (四态对比)
  design/mockup_pet_screen.png / mockup_monitor_screen.png       (128x160 x4 放大)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pi_client"))

from PIL import Image, ImageDraw  # noqa: E402
import art  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
SCALE = 8      # 精灵放大倍数（预览）
SCALE_M = 4    # 屏幕 mockup 放大倍数


def save_scaled(img, name):
    w, h = img.size
    big = img.resize((w * SCALE, h * SCALE), Image.NEAREST)
    big.save(os.path.join(OUT, name))
    print("saved", name, big.size)


def sprite_sheet():
    """一张图里并排展示三个精灵的 idle 变体。"""
    names = ["WHALE", "BLOB", "SPIRIT"]
    imgs = [art.render_sprite(n, "idle", scale=1) for n in names]
    h = max(i.size[1] for i in imgs)
    gap = 4
    w = sum(i.size[0] for i in imgs) + gap * (len(imgs) + 1)
    canvas = Image.new("RGBA", (w, h), (16, 20, 32))
    x = gap
    for n, i in zip(names, imgs):
        canvas.paste(i, (x, (h - i.size[1]) // 2), i)
        x += i.size[0] + gap
    save_scaled(canvas, "sprite_overview.png")


def variants_sheet():
    """WHALE 的四态对比。"""
    vs = ["idle", "blink", "work", "alert"]
    imgs = [art.render_sprite("WHALE", v, scale=1) for v in vs]
    h = max(i.size[1] for i in imgs)
    gap = 4
    w = sum(i.size[0] for i in imgs) + gap * (len(imgs) + 1)
    canvas = Image.new("RGBA", (w, h), (16, 20, 32))
    x = gap
    for v, i in zip(vs, imgs):
        canvas.paste(i, (x, (h - i.size[1]) // 2), i)
        x += i.size[0] + gap
    save_scaled(canvas, "sprite_WHALE_variants.png")


def mockups():
    # 模拟两种状态数据
    busy = {
        "dsh": {"active": True, "detail": "running"},
        "codex": {"active": False, "awaiting": True, "pending_approvals": 1},
        "system": {"cpu": 42.0, "mem": 63.0, "mem_used_gb": 10.1, "mem_total_gb": 16.0},
    }
    idle = {
        "dsh": {"active": False, "detail": "idle"},
        "codex": {"active": False, "awaiting": False, "pending_approvals": 0},
        "system": {"cpu": 8.0, "mem": 55.0, "mem_used_gb": 8.8, "mem_total_gb": 16.0},
    }
    pet = art.render_sprite("WHALE", "alert", scale=3)
    p1 = art.compose_pet_screen(busy, pet, "14:32", "Whale")
    p2 = art.compose_monitor_screen(busy, "14:32", True)
    p1.resize((128 * SCALE_M, 160 * SCALE_M), Image.NEAREST).save(
        os.path.join(OUT, "mockup_pet_screen.png"))
    p2.resize((128 * SCALE_M, 160 * SCALE_M), Image.NEAREST).save(
        os.path.join(OUT, "mockup_monitor_screen.png"))
    print("saved mockups")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    sprite_sheet()
    variants_sheet()
    mockups()
    print("完成 ->", OUT)
