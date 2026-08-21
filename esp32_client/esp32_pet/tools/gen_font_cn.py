# -*- coding: utf-8 -*-
"""
gen_font_cn.py — 生成 ESP32 中文字库 fonts_cn.h（12x16 单色位图，PROGMEM）。
字符集来自 TEXTS（界面用到的全部字符串），用微软雅黑渲染后 1-bit 化打包。
输出：esp32_client/fonts_cn.h
"""
import os
import string

from PIL import Image, ImageDraw, ImageFont

CELL_W, CELL_H = 28, 28        # 汉字22px高约21px，需28格子完整容纳+垂直居中
FONT_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "NotoSansCJK-Regular.ttc"),  # 含拉丁+数字+CJK，OFL
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "DroidSansFallbackFull.ttf"),  # 兜底
    "C:/Windows/Fonts/msyh.ttc",
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
    """渲染字形，返回 (实际宽度, 位图数据)。
    裁到 bbox 本身（避免右侧裁切）；垂直居中；每行 4 字节（32 位）大端。"""
    img = Image.new("L", (CELL_W, CELL_H), 0)
    d = ImageDraw.Draw(img)
    d.text((0, 0), ch, font=font, fill=255)
    bbox = img.getbbox()
    w = 1
    glyph = None
    if bbox:
        w = max(1, min(CELL_W, bbox[2] - bbox[0]))
        g = img.crop((bbox[0], bbox[1], bbox[2], bbox[3]))   # 紧致字形
        gw, gh = g.size
        # 垂直居中到 CELL_H
        canvas = Image.new("L", (gw, CELL_H), 0)
        oy = max(0, (CELL_H - gh) // 2)
        canvas.paste(g, (0, oy))
        glyph = canvas
    rows = []
    for y in range(CELL_H):
        row = 0
        for x in range(w):
            if glyph and glyph.getpixel((x, y)) > 127:
                row |= (0x80000000 >> x)
        rows.append(row)
    return w, bytes(b for r in rows for b in (r >> 24, (r >> 16) & 0xFF, (r >> 8) & 0xFF, r & 0xFF))


def load_cjk_font(path, size):
    """Noto CJK ttc 固定用 SC(简体,索引2)，避免其他面字形异常。"""
    for idx in (2, 0, 1, 3):
        try:
            f = ImageFont.truetype(path, size, index=idx)
            name = f.getname()[0]
            if "SC" in name.upper() or idx == 0:
                print("用面 idx=%d: %s" % (idx, name))
                return f
        except Exception:
            continue
    return ImageFont.truetype(path, size)


def main():
    font = None
    for p in FONT_CANDIDATES:
        try:
            font = load_cjk_font(p, 22)   # 22px 渲染进 16x24 格
            print("字体:", p)
            break
        except Exception:
            continue
    if font is None:
        raise SystemExit("找不到可用字体")
    chars = collect_chars()
    lines = ["// 自动生成（gen_font_cn.py），勿手改。24x24 单色位图，每行 3 字节大端。",
             "#pragma once",
             "#include <Arduino.h>",
             "struct glyph_t { const char* ch; uint8_t w; uint8_t h; const uint8_t* data; };",
             ""]
    entries = []
    for ch in chars:
        w, data = render(ch, font)
        name = "g_" + "".join("%02X" % b for b in ch.encode("utf-8"))
        lines.append("static const uint8_t %s[%d] = {%s};" % (
            name, len(data), ",".join(str(b) for b in data)))
        # C 字符串转义（引号/反斜杠必须转义，否则编译报错）
        esc = ch.replace("\\", "\\\\").replace('"', '\\"')
        entries.append('    {"%s", %d, %d, %s},' % (esc, w, CELL_H, name))
    lines.append("")
    lines.append("static const glyph_t GLYPHS[] = {")
    lines.extend(entries)
    lines.append("};")
    lines.append("static const int GLYPH_COUNT = sizeof(GLYPHS) / sizeof(glyph_t);")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("fonts_cn.h 生成完毕：%d 个字形 -> %s" % (len(chars), OUT))


if __name__ == "__main__":
    main()
