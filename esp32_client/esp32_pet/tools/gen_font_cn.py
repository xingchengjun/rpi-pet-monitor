# -*- coding: utf-8 -*-
"""
gen_font_cn.py — 生成 ESP32 中文字库 fonts_cn.h（12x16 单色位图，PROGMEM）。
字符集来自 TEXTS（界面用到的全部字符串），用微软雅黑渲染后 1-bit 化打包。
输出：esp32_client/fonts_cn.h
"""
import os
import string

from PIL import Image, ImageDraw, ImageFont

CELL_W, CELL_H = 12, 16
FONT_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "DroidSansFallbackFull.ttf"),  # Apache 2.0，优先
    "C:/Windows/Fonts/msyh.ttc",                                                          # 兜底
]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts_cn.h")

TEXTS = [
    "deepseek", "智能体: ", "空闲", "离线", "DSH 待审批", "codex 待审批",
    "codex + DSH", "设备状态", "待审批", "CPU", "内存", "GPU", "磁盘",
    "cpu ", "桥离线", "AWAIT!", "连接 WiFi...", "已连接", "WiFi 失败",
    "0123456789", ":!%+ /.-",
]


def collect_chars():
    """全部可打印 ASCII + 中文，避免启动/状态文字缺字形。"""
    chars = set(string.printable)
    for t in TEXTS:
        for ch in t:
            chars.add(ch)
    for c in list(chars):
        if c in "\t\n\r\x0b\x0c":
            chars.discard(c)
    return sorted(chars)


def render(ch, font):
    img = Image.new("L", (CELL_W, CELL_H), 0)
    d = ImageDraw.Draw(img)
    d.text((0, 0), ch, font=font, fill=255)
    rows = []
    for y in range(CELL_H):
        row = 0
        for x in range(CELL_W):
            if img.getpixel((x, y)) > 127:
                row |= (0x8000 >> x)
        rows.append(row)
    return bytes(b for r in rows for b in (r >> 8, r & 0xFF))


def main():
    font = None
    for p in FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(p, 15)   # 15px 渲染进 12x16 格
            print("字体:", p)
            break
        except Exception:
            continue
    if font is None:
        raise SystemExit("找不到可用字体")
    chars = collect_chars()
    lines = ["// 自动生成（gen_font_cn.py），勿手改。12x16 单色位图，每行 2 字节大端。",
             "#pragma once",
             "#include <Arduino.h>",
             "struct glyph_t { const char* ch; uint8_t w; uint8_t h; const uint8_t* data; };",
             ""]
    entries = []
    for ch in chars:
        data = render(ch, font)
        name = "g_" + "".join("%02X" % b for b in ch.encode("utf-8"))
        lines.append("static const uint8_t %s[%d] PROGMEM = {%s};" % (
            name, len(data), ",".join(str(b) for b in data)))
        # C 字符串转义（引号/反斜杠必须转义，否则编译报错）
        esc = ch.replace("\\", "\\\\").replace('"', '\\"')
        entries.append('    {"%s", %d, %d, %s},' % (esc, CELL_W, CELL_H, name))
    lines.append("")
    lines.append("static const glyph_t GLYPHS[] PROGMEM = {")
    lines.extend(entries)
    lines.append("};")
    lines.append("static const int GLYPH_COUNT = sizeof(GLYPHS) / sizeof(glyph_t);")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("fonts_cn.h 生成完毕：%d 个字形 -> %s" % (len(chars), OUT))


if __name__ == "__main__":
    main()
