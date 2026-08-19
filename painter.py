# -*- coding: utf-8 -*-
"""painter.py —— 像素风桌宠绘制

- 布局：顶部状态栏 / 台词气泡 / 中间宠物 / 底部桌面
- 宠物是一只程序化解剖的奶油小猫咪：椭圆身体 + 三角耳 + 可编程表情
- 供给不同 mood/phase 实现 待机/踱步/睡觉/吃饭/跳舞/撒娇/低落 动画
"""
import math

from PIL import Image, ImageDraw

import config as C

# --------------------------------------------------------------------------
# 布局常量
# --------------------------------------------------------------------------
GROUND_Y = 146                      # 桌面顶沿 = 宠物脚踩的地面
DESK_TOP = GROUND_Y - 2
BUBBLE_TOP = 8                      # 台词气泡顶部

R = 0


def _r(n):
    return int(round(n))


# --------------------------------------------------------------------------
class Painter:
    def __init__(self):
        pass

    # ---- 主入口：渲染一帧 ----
    def render(self, pet) -> Image.Image:
        img = Image.new("RGB", (C.SCREEN_W, C.SCREEN_H))
        d = ImageDraw.Draw(img)
        night = pet.night

        cx = _r(pet.x)
        self._draw_background(d, night)
        self._draw_desk(d, night)

        mood = pet.mood
        phase = pet.phase
        if mood == "sleep":
            mood = "sleep"
        self._draw_cat(d, cx, pet.oy, mood, phase, pet.facing)
        self._draw_particles(d, pet.particles)

        if pet.mood == "eat":
            self._draw_dango_hand(d, cx, pet.oy, pet.eat_k)
        if pet.bubble:
            self._draw_bubble(d, pet.bubble, cx)
        self._draw_topbar(d, pet)

        return img

    # ---- 背景 ----
    _stars = [(8, 30), (18, 12), (56, 6), (70, 26), (96, 10), (116, 22), (30, 48), (84, 44)]

    def _draw_background(self, d, night):
        bg = C.BG_NIGHT if night else C.BG_DAY
        d.rectangle([0, 0, C.SCREEN_W - 1, C.SCREEN_H - 1], fill=bg)
        if night:
            # 夜空小星星（按帧号闪烁）
            from time import time as _t
            flick = int(_t() * 2.5)
            for i, (sx, sy) in enumerate(self._stars):
                d.ellipse([sx, sy, sx + 1, sy + 1],
                          fill=(210, 215, 255) if (flick + i) % 3 else (120, 126, 170))
            d.ellipse([110, 6, 122, 18], outline=(220, 225, 255), width=1)
            d.ellipse([114, 6, 124, 16], fill=bg)   # 挖出月牙

    # ---- 桌面 ----
    def _draw_desk(self, d, night):
        top_c = C.DESK_DARK if night else C.DESK_TOP
        d.rectangle([0, DESK_TOP, C.SCREEN_W - 1, C.SCREEN_H - 1], fill=top_c)
        d.line([0, DESK_TOP, C.SCREEN_W - 1, DESK_TOP], fill=C.DESK_HL, width=2)
        # 木纹
        d.line([0, GROUND_Y + 5, C.SCREEN_W - 1, GROUND_Y + 5], fill=tuple(int(v * 0.92) for v in top_c))
        # 桌角盆栽
        self._draw_plant(d, x=10, y=DESK_TOP - 26, night=night)

    def _draw_plant(self, d, x, y, night):
        pot_x0, pot_y0, pot_x1, pot_y1 = x, y + 10, x + 14, y + 26
        pot_c = (92, 66, 92) if night else C.POT
        d.polygon([(pot_x0, pot_y0), (pot_x1, pot_y0), (pot_x0 + 3, pot_y1), (pot_x0 - 2, pot_y1)],
                  fill=pot_c, outline=(60, 40, 36))
        # 叶子
        leaf = C.LEAF_D if night else C.LEAF_L
        leaf2 = C.LEAF_L if night else C.LEAF_D
        d.ellipse([x + 3, y, x + 11, y + 12], fill=leaf)
        d.ellipse([x - 2, y + 4, x + 6, y + 14], fill=leaf2)
        d.polygon([(x + 7, y + 6), (x + 12, y - 6), (x + 14, y + 4)], fill=leaf)

    # ------------------------------------------------------------------
    # 宠物本体
    # ------------------------------------------------------------------
    def _draw_cat(self, d, cx, oy, mood, phase, facing):
        ty = 92 - oy                     # 身体椭圆顶（含动画起伏）
        f = -1 if facing == -1 else 1    # 朝向镜像
        jump = self._jump(oy)

        self._draw_shadow(d, cx, jump)
        if mood == "sleep":
            self._draw_tail(d, cx, ty, phase, mood, f)
        else:
            self._draw_tail(d, cx, ty, phase, mood, f)
        self._draw_ears(d, cx, ty, mood)
        self._draw_body(d, cx, ty, mood, phase, f, jump)
        self._draw_paws(d, cx, ty, mood, phase)
        self._draw_face(d, cx, ty, mood, phase, f)

    def _jump(self, oy):
        # oy<0 说明跳起来了，跳跃高度换算成影子缩小/变淡
        return max(0, -oy) / 9.0 if oy < 0 else 0.0

    def _draw_shadow(self, d, cx, jump):
        w = _r(34 * (1 - 0.5 * jump))
        grey = (0, 0, 0) if jump == 0 else (0, 0, 0)
        y0 = GROUND_Y - 3 + _r(jump * 2)
        d.ellipse([cx - w, y0, cx + w, y0 + 5], fill=grey)

    def _draw_body(self, d, cx, ty, mood, phase, f, jump):
        ox = 0
        # 跳舞时左右摆动
        if mood == "dance":
            ox = _r(math.sin(phase * math.pi) * 3)
        if mood == "happy":
            ox = _r(math.sin(phase * math.pi * 2) * 2)
        x0, x1 = cx + ox - 22, cx + ox + 22
        y0, y1 = ty + 14, ty + 54
        d.ellipse([x0, y0, x1, y1], fill=C.BODY, outline=C.OUTLINE, width=2)
        # 肚皮
        d.ellipse([cx + ox - 10, ty + 37, cx + ox + 10, ty + 52], fill=C.BELLY)
        # 项圈 + 铃铛
        d.rectangle([cx + ox - 12, ty + 40, cx + ox + 12, ty + 44], fill=C.COLLAR)
        bell_y = ty + 44
        d.ellipse([cx + ox - 3, bell_y, cx + ox + 3, bell_y + 6], fill=C.BELL, outline=C.OUTLINE, width=1)
        d.arc([cx + ox - 1, bell_y + 1, cx + ox + 1, bell_y + 2], 180, 360, fill=C.OUTLINE, width=1)

    def _draw_ears(self, d, cx, ty, mood):
        def ear(ax, bx0, bx1):
            d.polygon([(ax, ty + 2), (bx0, ty + 16), (bx1, ty + 16)],
                      fill=C.BODY, outline=C.OUTLINE, width=2)
            inner = (ax - 6, ty + 8)
            ix0, ix1 = bx0 + 4, bx1 - 4
            d.polygon([(inner[0] + 1, ty + 8), (ix0, ty + 15), (ix1, ty + 15)], fill=C.EAR_IN)

        ear(cx - 14, cx - 24, cx - 5)
        ear(cx + 14, cx + 5, cx + 24)

    def _draw_tail(self, d, cx, ty, phase, mood, f):
        active = mood in ("happy", "dance", "eat")
        wag = _r(math.sin(phase * math.pi * 2) * 3) if (active or mood == "walk") else 0
        bx, by = cx + f * 18, ty + 42
        if active:
            tx, ty2 = cx + f * 34, ty + 16 + wag
        else:
            tx, ty2 = cx + f * 32, ty + 34 + wag // 2
        d.line([(bx, by), (cx + f * 27, ty + 40 - wag), (tx, ty2)],
               fill=C.BODY_SHADE, width=8, joint="curve")
        d.line([(bx, by), (cx + f * 27, ty + 40 - wag), (tx, ty2)],
               fill=C.OUTLINE, width=8, joint="curve")
        r = 4
        d.ellipse([tx - r, ty2 - r, tx + r, ty2 + r], fill=C.BODY, outline=C.OUTLINE, width=2)

    def _draw_paws(self, d, cx, ty, mood, phase):
        if mood in ("happy", "dance"):
            return  # 跳起来时脚收起来，靠影子表达
        step = 0
        if mood == "walk":
            step = 2 if (int(phase * 8) % 2 == 0) else -1
        # 睡觉时收成一个小毛球
        if mood == "sleep":
            d.ellipse([cx - 11, ty + 49, cx + 11, ty + 54], fill=C.BODY, outline=C.OUTLINE, width=1)
            return
        for s in (-1, 1):
            px = cx + s * 7
            py = ty + 49 - (_r(step) if s == -1 else 0)
            d.ellipse([px - 4, py, px + 4, py + 5], fill=C.BODY, outline=C.OUTLINE, width=1)

    # ---- 表情 ----
    def _draw_face(self, d, cx, ty, mood, phase, f):
        ey = ty + 28
        blink = phase is not None and mood == "idle" and (int(phase * 20) % 20) > 17
        # 眼睛
        if mood in ("happy", "dance", "eat"):
            self._happy_eye(d, cx - 9 * f, ey)
            self._happy_eye(d, cx + 9 * f, ey)
        elif mood == "sleep":
            self._sleep_eye(d, cx - 9 * f, ey)
            self._sleep_eye(d, cx + 9 * f, ey)
        elif mood in ("sad", "tired"):
            self._open_eye(d, cx - 9 * f, ey, small=True)
            self._open_eye(d, cx + 9 * f, ey, small=True)
            # 眉毛
            for ex in (-1, 1):
                x0 = cx + ex * 14
                y0 = ey - 8
                d.line([(x0, y0 + 2), (x0 - ex * 5, y0 - 2)], fill=C.OUTLINE, width=2)
            if mood == "sad":
                self._tear(d, cx - 9 * f, ey + 4)
        else:
            if blink:
                self._sleep_eye(d, cx - 9 * f, ey)
                self._sleep_eye(d, cx + 9 * f, ey)
            else:
                self._open_eye(d, cx - 9 * f, ey)
                self._open_eye(d, cx + 9 * f, ey)

        # 嘴
        my = ty + 36
        if mood == "sad":
            d.line([(cx - 5, my - 3), (cx, my - 1), (cx + 5, my - 3)], fill=C.OUTLINE, width=2)
        elif mood == "tired":
            d.line([(cx - 4, my - 1), (cx + 4, my - 1)], fill=C.OUTLINE, width=2)
        elif mood == "sleep":
            self._w_mouth(d, cx, my, small=True, open_w=False)
        elif mood in ("happy", "dance"):
            d.ellipse([cx - 6, my - 3, cx + 6, my + 3], fill=C.OUTLINE)
            d.ellipse([cx - 4, my + 1, cx + 4, my + 5], fill=(240, 130, 140))
        elif mood == "eat":
            d.ellipse([cx - 3, my - 2, cx + 3, my + 2], fill=C.OUTLINE)
        else:
            d.arc([cx - 6, my - 4, cx + 6, my + 4], 20, 160, fill=C.OUTLINE, width=2)

        # 胡须 + 腮红
        self._whiskers(d, cx, my, f)
        self._cheeks(d, cx, ty)

    def _open_eye(self, d, x, y, small=False):
        r = 3 if small else 4
        d.ellipse([x - r, y - r, x + r, y + r], fill=C.OUTLINE)
        d.ellipse([x - 1, y - 1, x, y], fill=(255, 255, 255))

    def _sleep_eye(self, d, x, y):
        d.arc([x - 4, y - 3, x + 4, y + 3], 200, 340, fill=C.OUTLINE, width=2)

    def _happy_eye(self, d, x, y):
        d.arc([x - 4, y - 3, x + 4, y + 3], 200, 340, fill=C.OUTLINE, width=2)

    def _w_mouth(self, d, cx, my, small=False, open_w=True):
        r = 2 if small else 3
        for s in (-1, 1):
            x0 = cx + s * (2 if small else 3)
            d.arc([x0 - r, my - r, x0 + r, my + r], 200, 340, fill=C.OUTLINE, width=2)

    def _whiskers(self, d, cx, my, f):
        for i, dy in enumerate((-4, 0, 4)):
            y0 = my + dy
            d.line([(cx + f * 14, y0), (cx + f * 26, y0 + (-2 if dy else 0))],
                   fill=(170, 138, 104), width=1)

    def _cheeks(self, d, cx, ty):
        for s in (-1, 1):
            x0, y0, x1, y1 = cx + s * 15 - 4, ty + 31, cx + s * 15 + 4, ty + 38
            d.ellipse([x0, y0, x1, y1], fill=C.CHEEK)

    def _tear(self, d, x, y):
        d.ellipse([x + 1, y + 2, x + 4, y + 7], fill=(150, 190, 240))
        d.polygon([(x + 2, y + 2), (x + 3, y + 2), (x + 4, y + 7), (x + 1, y + 7)],
                  fill=(150, 190, 240))

    # ---- 吃饭时手里的团子 ----
    def _draw_dango_hand(self, d, cx, oy, k):
        ty = 92 - oy
        x = cx + 14
        y = ty + 40
        d.line([(x, y), (x, y + 16)], fill=C.GRIP, width=2)
        colors = [C.DANGO1, C.DANGO2, C.DANGO3]
        for i, c in enumerate(colors):
            r = [8, 7, 6][i] // 2
            yy = y - i * 5 - r + (2 if i == 2 else 0)
            d.ellipse([x - r, yy, x + r, yy + r + 1], fill=c, outline=C.OUTLINE, width=1)

    # ---- 粒子特效 ----
    def _draw_particles(self, d, parts):
        for p in parts:
            t = p["age"]
            k = p["k"]
            x, y = p["x"], p["y"]
            if t > p["dur"] - 0.35:
                continue  # 结尾淡出
            if k == "heart":
                s = 0.8 + t * 0.35
                self._heart(d, x, y, s, p["color"])
            elif k == "note":
                dy = y - t * 12
                dx = x + math.sin(t * 6) * 4
                d.text((dx, dy), "♪", font=_font13(), fill=C.NOTE)
            elif k == "zzz":
                dy = y - t * 10
                dx = x + math.sin(t * 4) * 2
                d.text((dx, dy), "Z", font=_font13(), fill=C.ZZZ)
            elif k == "sparkle":
                on = int(t * 12) % 2 == 0
                if on:
                    d.line([(x - 3, y), (x + 3, y)], fill=C.SPARKLE, width=1)
                    d.line([(x, y - 3), (x, y + 3)], fill=C.SPARKLE, width=1)

    def _heart(self, d, x, y, s, color):
        x, y, s = float(x), float(y), max(1.0, float(s))
        pts = []
        for a in range(0, 360, 15):
            rad = math.radians(a)
            px = math.sin(rad) * math.sqrt(abs(math.cos(rad)))
            # 心形公式
            kx = 16 * (math.sin(rad) ** 3)
            ky = 13 * math.cos(rad) - 5 * math.cos(2 * rad) - 2 * math.cos(3 * rad) - math.cos(4 * rad)
            pts.append((_r(x + kx * s), _r(y - ky * s)))
        d.polygon(pts, fill=color)

    # ---- 台词气泡 ----
    def _draw_bubble(self, d, text, cx):
        from fonts import wrap_text, font
        f = font(12)
        lines = wrap_text(text, 96, 12)
        line_h = 15
        pad = 8
        w = 104
        x0 = 12
        h = pad * 2 + line_h * len(lines)
        y0 = BUBBLE_TOP
        y1 = y0 + h
        d.rounded_rectangle([x0, y0, x0 + w, y1], radius=9, fill=C.BUBBLE_BG, outline=C.BUBBLE_BDR, width=2)
        # 尾巴
        cx0 = max(x0 + 14, min(x0 + w - 14, cx))
        d.polygon([(cx0 - 6, y1 - 1), (cx0 + 6, y1 - 1), (cx0, y1 + 8)], fill=C.BUBBLE_BG, outline=C.BUBBLE_BDR)
        for i, ln in enumerate(lines):
            d.text((x0 + pad, y0 + pad + i * line_h), ln, font=f, fill=C.TEXT)

    # ---- 顶部状态栏 ----
    def _draw_topbar(self, d, pet):
        d.text((6, 3), pet.time_str, font=_font13(), fill=(C.TEXT[0], C.TEXT[1], C.TEXT[2]))
        icon = {
            "sleep": self._icon_moon,
            "happy": self._icon_heart,
            "dance": self._icon_note,
            "eat": self._icon_dango,
            "sad": self._icon_sad,
        }.get(pet.mood)
        if icon:
            icon(d, 112, 8)

    def _icon_moon(self, d, x, y):
        d.arc([x - 7, y - 7, x + 7, y + 7], 80, 320, fill=C.ZZZ, width=3)

    def _icon_heart(self, d, x, y):
        self._heart(d, x, y - 3, 0.5, C.HEART1)

    def _icon_note(self, d, x, y):
        d.text((x - 5, y - 8), "♪", font=_font13(), fill=C.NOTE)

    def _icon_dango(self, d, x, y):
        d.ellipse([x - 3, y - 6, x + 3, y + 0], fill=C.DANGO1)
        d.ellipse([x - 3, y - 1, x + 3, y + 5], fill=C.DANGO2)

    def _icon_sad(self, d, x, y):
        d.ellipse([x - 3, y - 2, x + 3, y + 4], fill=(150, 190, 240))


_font_cache = {}


def _font13():
    if 13 not in _font_cache:
        from fonts import font
        _font_cache[13] = font(13)
    return _font_cache[13]