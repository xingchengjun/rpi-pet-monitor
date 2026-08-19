# -*- coding: utf-8 -*-
"""
art.py — 树莓派桌宠的共享绘制模块（纯 Pillow，无硬件依赖）。

设计原则：
- 所有精灵用像素网格（字符串矩阵 + 调色板）定义，与硬件无关，
  这样同一份素材既能用于树莓派实屏，也能在 PC 上生成预览 PNG。
- 屏幕固定 128x160 竖屏，内部用 RGB 模式 Image 绘制，由调用方上屏。

精灵：WHALE(小鲸鱼) / BLOB(团子) / SPIRIT(蓝精灵)
变体：idle / blink / work / alert（每个精灵至少提供 idle + alert）
外部位图动画：load_whale_anims() 可加载鲸鱼娘素材（assets/whale/anims，
  由 design/compress_whale.py 从 codex-pet-DeepSeek-girl 仓库压缩而来），
  经 whale_frame() 按状态取帧，实现真·鲸鱼娘动画。
"""

import os

from PIL import Image, ImageDraw, ImageFont

SCREEN_W, SCREEN_H = 128, 160

# ---------------------------------------------------------------------------
# 调色板（全精灵共用）
# ---------------------------------------------------------------------------
PALETTE = {
    ".": None,               # 透明
    "k": (24, 24, 32),       # 描边深色
    "B": (24, 74, 168),      # 深蓝
    "b": (61, 139, 255),     # 中蓝
    "c": (127, 184, 255),    # 浅蓝
    "w": (255, 255, 255),    # 白
    "p": (255, 158, 190),    # 粉(腮红)
    "y": (255, 214, 90),     # 黄
    "g": (140, 150, 160),    # 灰
    "o": (255, 122, 90),     # 橙
}

# ---------------------------------------------------------------------------
# 精灵像素网格
# ---------------------------------------------------------------------------
SPRITES = {
    # ---------------- 小鲸鱼（参考项目的鲸鱼娘风格，蓝色系） ----------------
    "WHALE": {
        "idle": [
            "................",
            "......kkkk......",
            ".....kbbbbk.....",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbwkbbwkbbb.",
            ".kbbbbwwbwwbbbb.",
            ".kbbbbbbbbbbbbk.",
            ".kbbbwwwwwwbbbbk",
            ".kbbbwwwwwwbbbbk",
            ".kbbbpbbbbpbbbko",
            "..kbbbbbbbbbbko.",
            "...kbbbbbbbbko..",
            "....kkkkkkkko...",
            "...........o....",
        ],
        "blink": [
            "................",
            "......kkkk......",
            ".....kbbbbk.....",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbkkbbkkbbb.",
            ".kbbbbbbbbbbbbb.",
            ".kbbbbbbbbbbbbk.",
            ".kbbbwwwwwwbbbbk",
            ".kbbbwwwwwwbbbbk",
            ".kbbbpbbbbpbbbko",
            "..kbbbbbbbbbbko.",
            "...kbbbbbbbbko..",
            "....kkkkkkkko...",
            "...........o....",
        ],
        "work": [
            "................",
            "......kkkk......",
            ".....kbbbbk.....",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbwkbbwkbbb.",
            ".kbbbbwwbwwbbbb.",
            ".kbbbwwwwwwbbbbk",
            ".kbbbwwwwwwbbbbk",
            ".kbbbybbbbbybbko",
            ".kbbbpbbbbpbbbko",
            "..kbbbbbbbbbbko.",
            "...kbbbbbbbbko..",
            "....kkkkkkkko...",
            "...........o....",
        ],
        "alert": [
            "................",
            ".....y....y.....",
            "......y..y......",
            ".....ybbby......",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbwkbbwkbbb.",
            ".kbbbbwwbwwbbbb.",
            ".kbbbwwwwwwbbbbk",
            ".kbbbwwwwwwbbbbk",
            ".kbbbpbbbbpbbbko",
            "..kbbbbbbbbbbko.",
            "...kbbbbbbbbko..",
            "....kkkkkkkko...",
            "...........o....",
        ],
    },
    # ---------------- 团子（简单圆润，适合当备选） -------------------------
    "BLOB": {
        "idle": [
            "................",
            ".....kkkkkk.....",
            "...kkwwwwwwkk...",
            "..kwwwwwwwwwwk..",
            ".kwwwwwwwwwwwwk.",
            ".kwwkwwwwwwkwwk.",
            ".kwwkwwwwwwkwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwppwwwwwwppwk.",
            ".kwwwwwwwwwwwwk.",
            "..kwwwwwwwwwwk..",
            "...kkwwwwwwkk...",
            ".....kkkkkk.....",
            "................",
            "................",
        ],
        "blink": [
            "................",
            ".....kkkkkk.....",
            "...kkwwwwwwkk...",
            "..kwwwwwwwwwwk..",
            ".kwwwwwwwwwwwwk.",
            ".kwwkkwwwwkkwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwppwwwwwwppwk.",
            ".kwwwwwwwwwwwwk.",
            "..kwwwwwwwwwwk..",
            "...kkwwwwwwkk...",
            ".....kkkkkk.....",
            "................",
            "................",
        ],
        "work": [
            "................",
            ".....kkkkkk.....",
            "...kkwwwwwwkk...",
            "..kwwwwwwwwwwk..",
            ".kwwwwwwwwwwwwk.",
            ".kwwkwwwwwwkwwk.",
            ".kwwkwwwwwwkwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwyyyyyyyywwk.",
            "..kwwwwwwwwwwk..",
            "...kkwwwwwwkk...",
            ".....kkkkkk.....",
            "................",
            "................",
        ],
        "alert": [
            "................",
            ".....y....y.....",
            "......y..y......",
            ".....kkkkkk.....",
            "...kkwwwwwwkk...",
            "..kwwwwwwwwwwk..",
            ".kwwkwwwwwwkwwk.",
            ".kwwkwwwwwwkwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwwwwwwwwwwwk.",
            ".kwwwwwwwwwwwwk.",
            "..kwwwwwwwwwwk..",
            "...kkwwwwwwkk...",
            ".....kkkkkk.....",
            "................",
            "................",
        ],
    },
    # ---------------- 蓝精灵（竖版，有天线，适合状态感） --------------------
    "SPIRIT": {
        "idle": [
            ".......kk.......",
            "......kbbk......",
            ".......kk.......",
            ".......kk.......",
            "......kbbk......",
            ".....kbbbbk.....",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbwkbbwkbbk.",
            ".kbbbbwwbwwbbbk.",
            ".kbbbwwwwwwbbbk.",
            ".kbbbpbbbbpbbbk.",
            "..kbbbbbbbbbbk..",
            "...kkbbbbbbkk...",
            ".....kkkkkk.....",
        ],
        "blink": [
            ".......kk.......",
            "......kbbk......",
            ".......kk.......",
            ".......kk.......",
            "......kbbk......",
            ".....kbbbbk.....",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbkkbbkkbbk.",
            ".kbbbbbbbbbbbbk.",
            ".kbbbwwwwwwbbbk.",
            ".kbbbpbbbbpbbbk.",
            "..kbbbbbbbbbbk..",
            "...kkbbbbbbkk...",
            ".....kkkkkk.....",
        ],
        "work": [
            ".......kk.......",
            "......kbbk......",
            ".......kk.......",
            ".......kk.......",
            "......kbbk......",
            ".....kbbbbk.....",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbwkbbwkbbk.",
            ".kbbbbwwbwwbbbk.",
            ".kbbbwwwwwwbbbk.",
            ".kbbbybbbbpbbbk.",
            "..kbbbbbbbbbbk..",
            "...kkbbbbbbkk...",
            ".....kkkkkk.....",
        ],
        "alert": [
            ".......yy.......",
            "......ybbk......",
            ".......kk.......",
            ".......kk.......",
            "......kbbk......",
            ".....kbbbbk.....",
            "....kbbbbbbk....",
            "...kbbbbbbbbk...",
            "..kbbbbbbbbbbk..",
            ".kbbbbwkbbwkbbk.",
            ".kbbbbwwbwwbbbk.",
            ".kbbbwwwwwwbbbk.",
            ".kbbbpbbbbpbbbk.",
            "..kbbbbbbbbbbk..",
            "...kkbbbbbbkk...",
            ".....kkkkkk.....",
        ],
    },
}

# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------
def _font(size=8, bold=False):
    """优先找系统 TTF（PC 预览更好看），找不到退回内置位图字体。
    中文：Windows 用微软雅黑，树莓派用 Noto Sans CJK（apt 装 fonts-noto-cjk）。"""
    if bold:
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_sprite(name, variant="idle", scale=3):
    """把像素网格渲染成 RGBA Image（scale 倍放大，默认 3 倍=48px 见方）。"""
    grid = SPRITES[name][variant]
    h, w = len(grid), len(grid[0])
    img = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            color = PALETTE.get(ch)
            if color is None:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    px[x * scale + dx, y * scale + dy] = color + (255,)
    return img


# ---------------------------------------------------------------------------
# 外部位图动画（鲸鱼娘素材，由 compress_whale.py 生成）
# ---------------------------------------------------------------------------
WHALE_ANIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "assets", "whale", "anims")

# 状态 -> 动画名映射（素材里的 9 个标准动画）
STATE_ANIM = {
    "idle": "idle",
    "blink": "idle",
    "work": "running",
    "alert": "waiting",
}


def load_whale_anims(anim_dir=WHALE_ANIM_DIR):
    """加载 assets/whale/anims/<动画名>/fNNN.png，返回 {动画名: [帧Image]}。"""
    anims = {}
    if not os.path.isdir(anim_dir):
        return anims
    try:
        for name in sorted(os.listdir(anim_dir)):
            d = os.path.join(anim_dir, name)
            if not os.path.isdir(d):
                continue
            frames = []
            for fn in sorted(os.listdir(d)):
                if fn.endswith(".png"):
                    with Image.open(os.path.join(d, fn)) as im:
                        frames.append(im.convert("RGBA").copy())
            if frames:
                anims[name] = frames
    except Exception:
        return {}
    return anims


def whale_frame(anims, state, now, fps=8.0):
    """按状态和时间取一帧（循环播放），素材缺失时返回 None。"""
    if not anims:
        return None
    name = STATE_ANIM.get(state, "idle")
    frames = anims.get(name) or anims.get("idle")
    if not frames:
        return None
    idx = int(now * fps) % len(frames)
    return frames[idx]


# ---------------------------------------------------------------------------
# 屏幕合成（128x160，供 pet.py 实屏 & gen_designs.py 预览共用）
# 布局：背景=PANTONE 状态色（屏幕素质差，用高饱和色）
#   空闲=PANTONE 281C 蓝 / 工作=PANTONE 2300C 绿 / 待审批=PANTONE 200C 红
#   内容：左上=deepseek 右上=时间(橙) 左中=智能体 中央下=人物(胶囊模糊底衬)
#   第二屏：四个圆角矩形仪表（左上名称/右下百分比/下半按百分比填充）
# ---------------------------------------------------------------------------
C_TIME = (255, 127, 39)       # 橙（时间，各底色均可见）
C_BADGE = (206, 17, 38)       # 红（徽标/警示）

STATE_BG = {
    "offline": (52, 56, 66),
    "idle": (0, 32, 91),          # PANTONE 281 C 蓝
    "work": (0, 163, 92),         # PANTONE 2300 C 绿
    "alert": (206, 17, 38),       # PANTONE 200 C 红
}

# 每状态的前景色：蓝/红/灰底用白字，绿底用深色字
STATE_FG = {
    "offline": (230, 235, 240),
    "idle": (255, 255, 255),
    "work": (10, 30, 60),
    "alert": (255, 255, 255),
}


def _screen_state(status):
    """alert=有待审批 / work=工作 / idle=空闲 / offline=离线"""
    if status is None:
        return "offline"
    if (int(status.get("codex", {}).get("pending_approvals", 0) or 0) > 0
            or status.get("codex", {}).get("awaiting")
            or int(status.get("dsh", {}).get("pending_approvals", 0) or 0) > 0
            or status.get("dsh", {}).get("awaiting")):
        return "alert"
    if status.get("codex", {}).get("active") or status.get("dsh", {}).get("active"):
        return "work"
    return "idle"


def _pending_total(status):
    if status is None:
        return 0
    return (int(status.get("codex", {}).get("pending_approvals", 0) or 0)
            + int(status.get("dsh", {}).get("pending_approvals", 0) or 0))


def _agent_label(status):
    """当前运行的智能体名（含 DSH 待审批）。"""
    if status is None:
        return "离线"
    cod = status.get("codex", {})
    dsh = status.get("dsh", {})
    if dsh.get("awaiting"):
        return "DSH 待审批"
    if cod.get("awaiting"):
        return "codex 待审批"
    if cod.get("active") and dsh.get("active"):
        return "codex + DSH"
    if cod.get("active"):
        return "codex"
    if dsh.get("active"):
        return "DSH"
    return "空闲"


def _capsule_blur(img, cx, cy, w, h, color=(255, 255, 255, 150)):
    """胶囊型高斯模糊底衬：白色胶囊 -> 高斯模糊 -> 合成到背景。"""
    from PIL import ImageFilter
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        radius=h // 2, fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(radius=12))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))


def compose_pet_screen(status, pet_img, clock_str, pet_name):
    """第一屏：PANTONE 状态色背景 + 人物（胶囊模糊）+ 顶部文字。"""
    state = _screen_state(status)
    fg = STATE_FG[state]
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), STATE_BG[state])
    d = ImageDraw.Draw(img)
    f8 = _font(8)
    f9 = _font(9, bold=True)

    # 左上：deepseek；右上：时间（橙）
    d.text((6, 4), "deepseek", font=f9, fill=fg)
    tw = d.textlength(clock_str, font=f9)
    d.text((128 - tw - 6, 4), clock_str, font=f9, fill=C_TIME)
    # 待审批徽标（白底红字，各底色均醒目）
    n = _pending_total(status)
    if n > 0:
        badge = " !%d " % n
        bw = len(badge) * 8 + 4
        d.rounded_rectangle([128 - bw - 3, 15, 125, 26], radius=4, fill=(255, 255, 255))
        d.text((128 - bw + 1, 16), badge, font=f8, fill=C_BADGE)

    # 左中：智能体
    d.text((6, 20), "智能体: " + _agent_label(status), font=f8, fill=fg)
    if n > 0:
        d.text((86, 20), "AWAIT!", font=f9, fill=(255, 255, 255))

    # 中央下：人物（纯色背景，无渐变）
    pw, ph = pet_img.size
    px, py = (SCREEN_W - pw) // 2, 40
    img.paste(pet_img, (px, py), pet_img)

    # 底部：cpu
    sys_info = status.get("system", {}) if status else {}
    d.text((6, 152), "cpu %d%%" % int(sys_info.get("cpu", 0) or 0), font=f8, fill=fg)
    return img


def compose_monitor_screen(status, clock_str, pi_ok):
    """第二屏（设备状态）：四个圆角矩形仪表，左上名称/右下百分比/下半按百分比填充。"""
    state = _screen_state(status)
    fg = STATE_FG[state]
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), STATE_BG[state])
    d = ImageDraw.Draw(img)
    f8 = _font(8)
    f9 = _font(9, bold=True)

    d.text((6, 4), "deepseek", font=f9, fill=fg)
    tw = d.textlength(clock_str, font=f9)
    d.text((128 - tw - 6, 4), clock_str, font=f9, fill=C_TIME)
    d.text((6, 20), "设备状态", font=f9, fill=fg)
    n = _pending_total(status)
    if n > 0:
        d.text((86, 20), "%d 待审批" % n, font=f9, fill=(255, 255, 255))

    if status is None:
        d.text((8, 60), "桥离线，无法获取状态", font=f8, fill=fg)
        d.text((8, 74), "检查电脑端 bridge 与 token", font=f8, fill=fg)
        return img

    sys_info = status.get("system", {})
    gpu_extra = None
    if sys_info.get("gpu_total_gb"):
        gpu_extra = "%.0f/%.0fG" % (sys_info.get("gpu_used_gb", 0), sys_info.get("gpu_total_gb", 0))
    elif sys_info.get("gpu_name"):
        gpu_extra = (str(sys_info["gpu_name"]))[:5]
    rows = [
        ("CPU", int(sys_info.get("cpu", 0) or 0), (90, 170, 250), None),
        ("内存", int(sys_info.get("mem", 0) or 0), (110, 230, 140),
         "%.0f/%.0fG" % (sys_info.get("mem_used_gb", 0), sys_info.get("mem_total_gb", 0))),
        ("GPU", int(sys_info.get("gpu", 0) or 0), (200, 140, 255), gpu_extra),
        ("磁盘", int(sys_info.get("disk", 0) or 0), (255, 200, 70),
         "%.0f/%.0fG" % (sys_info.get("disk_used_gb", 0), sys_info.get("disk_total_gb", 0))),
    ]

    # 田字 2x2 布局：四个圆角矩形仪表
    margin, gap = 3, 3
    cell_w = (SCREEN_W - margin * 2 - gap) // 2
    cell_h = (SCREEN_H - 38 - margin * 2 - gap) // 2
    for i, (title, pct, color, extra) in enumerate(rows):
        col, row = i % 2, i // 2
        x = margin + col * (cell_w + gap)
        y = 38 + margin + row * (cell_h + gap)
        # 圆角矩形外框（上半透明）
        d.rounded_rectangle([x, y, x + cell_w, y + cell_h], radius=8,
                            outline=fg, width=1)
        # 下半按百分比填充
        fill_h = max(0, int((cell_h - 2) * pct / 100.0))
        if fill_h > 0:
            d.rounded_rectangle([x + 2, y + cell_h - fill_h, x + cell_w - 2, y + cell_h - 1],
                                radius=5, fill=color)
        # 左上名称，右下百分比
        d.text((x + 5, y + 3), title, font=f8, fill=fg)
        pct_txt = "%d%%" % pct
        d.text((x + cell_w - 5 - len(pct_txt) * 6, y + cell_h - 11), pct_txt,
               font=f8, fill=fg)
        if extra:
            d.text((x + 5, y + cell_h - 11), extra, font=f8, fill=fg)
    return img
