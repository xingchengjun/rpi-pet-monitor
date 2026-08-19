# -*- coding: utf-8 -*-
"""
compress_whale.py — 压缩 codex-pet-DeepSeek-girl 仓库素材，供 128x160 小屏使用。

步骤：
1. 解压已下载的 repo.zip（design/whale_raw/repo.zip）
2. 从预览 GIF 提取各动画帧 -> 裁边 -> 缩到 TARGET -> 去绿描边 -> 归一化画布
3. 量化 <=32 色 -> 输出 design/whale_assets/
     anims/<动画名>/f000.png ...   （每动画的帧序列，尺寸一致，播放不抖动）
     spritesheet_small.png         （压缩后的整表）
     whale_assets.zip              （全部打包）
   并打印 压缩前后体积对比。
"""

import os
import zipfile

from PIL import Image, ImageSequence

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "whale_raw")
REPO_ZIP = os.path.join(RAW, "repo.zip")
EXTRACTED = os.path.join(RAW, "extracted")
OUT = os.path.join(ROOT, "whale_assets")

TARGET = 96          # 目标帧尺寸（最大边 96px，人物更大更醒目）
MAX_COLORS = 32      # 量化色数


def extract():
    if not os.path.isdir(EXTRACTED):
        with zipfile.ZipFile(REPO_ZIP) as z:
            z.extractall(EXTRACTED)
    root = EXTRACTED
    for d in os.listdir(root):
        return os.path.join(root, d)
    return root


def gif_frames(path):
    """从 GIF 提取合成后的完整帧序列（处理透明/局部帧）。"""
    frames = []
    with Image.open(path) as im:
        base = None
        for i, f in enumerate(ImageSequence.Iterator(im)):
            f = f.convert("RGBA")
            if i == 0:
                base = f.copy()
            else:
                base.paste(f, (0, 0), f)
            frames.append(base.copy())
    return frames


def despill(im):
    """去绿边：绿色明显主导的像素（含不透明边缘）压掉绿色通道。
    判定 g 显著大于 r 和 b；白/蓝/灰等非绿像素不受影响。"""
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 0 and g > r + 10 and g > b + 10:
                px[x, y] = (r, max(r, b), b, a)
    return im


def shrink(frame):
    """裁透明边 -> 缩到 TARGET 内 -> 去绿描边。返回 RGBA。"""
    box = frame.getbbox()
    if box:
        frame = frame.crop(box)
    w, h = frame.size
    scale = min(1.0, TARGET / max(w, h))
    if scale < 1.0:
        frame = frame.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                             Image.LANCZOS)
    return despill(frame.convert("RGBA"))


def normalize(anims):
    """把所有帧垫到统一画布并居中 —— 消除逐帧尺寸抖动（重影感来源之一）。"""
    all_frames = [f for fr in anims.values() for f in fr]
    mw = max(f.size[0] for f in all_frames)
    mh = max(f.size[1] for f in all_frames)
    for name, frames in anims.items():
        for i, f in enumerate(frames):
            canvas = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
            canvas.paste(f, ((mw - f.size[0]) // 2, (mh - f.size[1]) // 2), f)
            frames[i] = canvas
    print("归一化画布: %dx%d" % (mw, mh))
    return anims


def quantize_save(anims):
    for name, frames in anims.items():
        d = os.path.join(OUT, "anims", name)
        os.makedirs(d, exist_ok=True)
        for i, f in enumerate(frames):
            q = f.quantize(colors=MAX_COLORS, method=Image.FASTOCTREE)
            q.save(os.path.join(d, "f%03d.png" % i), optimize=True)


def build_small_sheet(anims, cols=8):
    frames = []
    for name in sorted(anims.keys()):
        frames.extend(anims[name])
    if not frames:
        return None
    pad = 2
    fw, fh = frames[0].size
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * fw + (cols + 1) * pad, rows * fh + (rows + 1) * pad),
                      (0, 0, 0, 0))
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        f_rgba = f.convert("RGBA")
        sheet.paste(f_rgba, (pad + c * (fw + pad), pad + r * (fh + pad)), f_rgba)
    return sheet


def make_zip():
    zpath = os.path.join(OUT, "whale_assets.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fns in os.walk(OUT):
            for fn in fns:
                if fn.endswith(".zip"):
                    continue
                p = os.path.join(dp, fn)
                z.write(p, os.path.relpath(p, OUT))
    return zpath


def main():
    os.makedirs(OUT, exist_ok=True)
    root = extract()
    sheet = os.path.join(root, "spritesheet.webp")
    contact = os.path.join(root, "previews", "contact-sheet.png")

    anims = {}
    gifs_dir = os.path.join(root, "previews")
    for fn in sorted(os.listdir(gifs_dir)):
        if fn.endswith(".gif"):
            name = fn[:-4]
            frames = [shrink(f) for f in gif_frames(os.path.join(gifs_dir, fn))]
            anims[name] = frames
            print("gif %-16s %d 帧" % (fn, len(frames)))

    if not anims:
        print("没有可用的 GIF 动画素材")
        return

    normalize(anims)
    quantize_save(anims)

    small = build_small_sheet(anims)
    if small:
        small.save(os.path.join(OUT, "spritesheet_small.png"), optimize=True)

    zpath = make_zip()
    before = (os.path.getsize(sheet) if os.path.exists(sheet) else 0) + \
             (os.path.getsize(contact) if os.path.exists(contact) else 0)
    after = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fns in os.walk(OUT) for f in fns if not f.endswith(".zip"))
    print("=== 体积对比 ===")
    print("原始 webp+contact: %.2f MB" % (before / 1e6))
    print("压缩后素材(不含zip): %.2f MB" % (after / 1e6))
    print("zip: %.2f MB -> %s" % (os.path.getsize(zpath) / 1e6, zpath))


if __name__ == "__main__":
    main()
