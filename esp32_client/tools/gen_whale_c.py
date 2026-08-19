# -*- coding: utf-8 -*-
"""
gen_whale_c.py — 把鲸鱼娘帧转成 ESP32 用的 RGB565 C 数组（PROGMEM）。
透明像素 -> 0x0000（颜色键，绘制时跳过，露出状态底色）。
动画：idle / running / waiting（映射 空闲/工作/待审批）。
输出：esp32_client/whale_frames.h
"""
import glob
import os

from PIL import Image

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "pi_client", "assets", "whale", "anims")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "whale_frames.h")
ANIMS = ["idle", "running", "waiting"]


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def frame_to_565(path):
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    out = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = im.getpixel((x, y))
            if a < 128:
                out.append(0x0000)          # 透明 -> 颜色键
            else:
                out.append(rgb565(r, g, b))
    return out


def main():
    lines = ["// 自动生成（gen_whale_c.py），勿手改。RGB565，透明=0x0000。",
             "#pragma once",
             "#include <Arduino.h>",
             "#define WHALE_W %d",
             "#define WHALE_H %d",
             ""]
    w = h = None
    anims = []
    for anim in ANIMS:
        d = os.path.join(ASSETS, anim)
        frames = sorted(glob.glob(os.path.join(d, "*.png")))
        if not frames:
            print("缺少动画:", anim)
            continue
        for i, fp in enumerate(frames):
            if w is None:
                with Image.open(fp) as im:
                    w, h = im.size
            data = frame_to_565(fp)
            lines.append("static const uint16_t w_%s_%d[%d] PROGMEM = {%s};" % (
                anim, i, len(data), ",".join(str(v) for v in data)))
        anims.append((anim, len(frames)))
    lines[3] = lines[3] % w
    lines[4] = lines[4] % h
    lines.append("")
    for anim, n in anims:
        lines.append("static const uint16_t* const w_%s_frames[%d] PROGMEM = {%s};" % (
            anim, n, ",".join("w_%s_%d" % (anim, i) for i in range(n))))
    lines.append("")
    lines.append("struct whale_anim_t { const char* name; int count; const uint16_t** frames; };")
    lines.append("static const whale_anim_t WHALE_ANIMS[%d] = {" % len(anims))
    for anim, n in anims:
        lines.append('    {"%s", %d, w_%s_frames},' % (anim, n, anim))
    lines.append("};")
    lines.append("static const int WHALE_ANIM_COUNT = sizeof(WHALE_ANIMS) / sizeof(whale_anim_t);")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("whale_frames.h 生成完毕：%dx%d x %d 帧 -> %s" % (w, h, sum(n for _, n in anims), OUT))


if __name__ == "__main__":
    main()
