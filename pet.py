# -*- coding: utf-8 -*-
"""pet.py —— 宠物状态机

状态：idle / walk / sleep / happy(撒娇) / eat(吃饭) / dance(跳舞) / sad(低落)
两条隐性状态：hunger(饥饿) energy(精力)—— 饥饿/没精力会自动撒娇喊饿或睡着。

按钮：
  K1 触摸挠痒   → happy + 爱心 + 台词
  K2 喂食       → eat  + 团子 + 台词（回满 hunger）
  K3 睡觉/叫醒  → sleep 切换
  K4 一起玩     → dance + 音符 + 台词
"""
import math as _math
import random
from datetime import datetime

import config as C
from fonts import cjk_available

_CHOOSE = lambda lst: random.choice(lst)


class Pet:
    def __init__(self, name: str = None):
        self.name = name or C.PET_NAME
        self.x = float(C.SCREEN_W // 2)          # 宠物中心 x
        self.facing = 1                           # 朝向 1/-1
        self.mood = "idle"
        self.state = "idle"
        self.phase = random.random()              # 动画相位 0..1
        self.oy = 0                               # 垂直偏移（动画起伏）
        self.particles = []

        self.hunger = 60.0
        self.energy = 50.0

        self.bubble = None
        self.bubble_t = 0.0
        self.eat_t = None
        self.eat_k = 0

        self.night = False
        self.time_str = self._now()

        self.act_t = 0.0                          # 当前行为剩余时长
        self.idle_t = random.uniform(C.IDLE_MIN, C.IDLE_MAX)
        self._zzz_cd = 0.0
        self._night_alarm = False

    # ---------------------------------------------------------------- 工具
    def _now(self):
        now = datetime.now()
        return now.strftime("%H:%M")

    def _update_time(self):
        s = self._now()
        if s != self.time_str:
            self.time_str = s
            h = datetime.now().hour
            self.night = h >= 22 or h < 7

    def _say(self, key):
        if not cjk_available():
            return _CHOOSE(C.LINES[key])[1]
        return _CHOOSE(C.LINES[key])[0]

    def _spawn(self, k, n=1, x=None, y=None):
        cx = self.x if x is None else x
        cy = 96 if y is None else y
        for i in range(n):
            self.particles.append({
                "k": k,
                "x": cx + random.uniform(-10, 10),
                "y": cy - random.uniform(-6, 8),
                "age": 0.0,
                "dur": random.uniform(1.2, 1.8),
                "color": _CHOOSE([C.HEART1, C.HEART2, C.HEART3]),
            })

    # ------------------------------------------------------------ 交互
    def on_touch(self):
        if self.state == "sleep":
            self.wake(); return
        self._enter("happy", "touch", dur=2.4)
        self._spawn("heart", 5)

    def on_feed(self):
        if self.state == "sleep":
            self.wake()
        self.hunger = min(100.0, self.hunger + 45)
        self.eat_t = 2.2
        self.eat_k = random.random()
        self._enter("eat", "feed", dur=2.2)

    def on_sleep(self):
        if self.state == "sleep":
            self.wake()
        else:
            self._enter("sleep", "sleep", dur=-1)

    def on_play(self):
        if self.state == "sleep":
            self.wake(); return
        self.energy = max(0.0, self.energy - 5)
        self._spawn("note", 6)
        self._spawn("sparkle", 4)
        self._enter("dance", "play", dur=3.0)

    def wake(self):
        self._enter("idle", "wake", dur=1.2)
        self.state = "idle"
        self.idle_t = random.uniform(C.IDLE_MIN, C.IDLE_MAX)

    def _enter(self, state, line_key, dur):
        self.state = state
        self.mood = state
        self.act_t = dur
        self.phase = 0.0
        self.bubble = self._say(line_key)
        self.bubble_t = C.BUBBLE_SEC
        self.idle_t = random.uniform(C.IDLE_MIN, C.IDLE_MAX)

    # ------------------------------------------------------------- 主更新
    def tick(self, dt: float):
        self._update_time()
        fpb = self._phase_speed()
        self.phase = (self.phase + dt * fpb) % 1.0

        # 饥饿 / 精力随时间衰减
        self.hunger = max(0.0, self.hunger - C.HUNGER_DROP_PER_MIN * dt / 60)
        if self.state == "sleep":
            self.energy = min(100.0, self.energy + C.SLEEP_RECOVER_PER_MIN * dt / 60)
        else:
            self.energy = max(0.0, self.energy - C.ENERGY_DROP_PER_MIN * dt / 60)

        # 各状态行为
        if self.state == "idle":
            self._tick_idle(dt)
        elif self.state == "walk":
            self._tick_walk(dt)
        elif self.state == "sleep":
            self._tick_sleep(dt)
        else:
            self._tick_act(dt)

        self._update_particles(dt)

    def _phase_speed(self):
        return {
            "dance": 13, "happy": 11, "eat": 7,
            "sleep": 1.5, "walk": 7, "idle": 4,
        }.get(self.state, 4)

    def _bob(self, amp):
        import math
        return round(math.sin(self.phase * math.pi * 2) * amp)

    def _compute_oy(self):
        if self.state in ("happy", "dance"):
            import math
            self.oy = -abs(math.sin(self.phase * math.pi * 2)) * 9
        elif self.state in ("idle", "eat"):
            self.oy = self._bob(2)
        elif self.state == "walk":
            self.oy = self._bob(3)
        elif self.state == "sleep":
            self.oy = 1
        else:
            self.oy = self._bob(1)

    # ---- 行为实现 ----
    def _tick_idle(self, dt):
        self._compute_oy()
        if self.bubble_t > 0:
            self.bubble_t -= dt
            if self.bubble_t <= 0:
                self.bubble = None
            return
        self.idle_t -= dt
        if self.idle_t <= 0:
            self._decide_action()

    def _decide_action(self):
        # 晚上：偶尔说句晚安
        if self.night and random.random() < 0.25:
            self._say_quiet("night")
            self.idle_t = random.uniform(15, 30)
            return
        # 饿了
        if self.hunger < C.HUNGRY_ALARM:
            self._enter("sad", "hungry", dur=2.5)
            self.idle_t = random.uniform(8, 18)
            return
        # 精力见底 → 先撒娇，随后自动睡着
        if self.energy < C.ENERGY_ALARM:
            if not self._night_alarm:
                self._night_alarm = True
                self._enter("sad", "low_energy", dur=2.5)
            else:
                self._enter("sleep", "sleepy", dur=-1)
            return
        if self.energy < 35 and random.random() < 0.3:
            self._enter("sad", "sleepy", dur=1.6)
            self.idle_t = random.uniform(20, 40)
            return
        # 普通随机行为
        r = random.random()
        if r < 0.35:
            self._start_walk()
        elif r < 0.6:
            self._say_quiet("idle")
        else:
            self.idle_t = random.uniform(C.IDLE_MIN, C.IDLE_MAX)

    def _say_quiet(self, key):
        self.bubble = self._say(key)
        self.bubble_t = C.BUBBLE_SEC
        self.idle_t = random.uniform(C.IDLE_MIN + 4, C.IDLE_MAX + 6)

    def _start_walk(self):
        target = random.uniform(C.PET_X_MIN, C.PET_X_MAX)
        if abs(target - self.x) < 10:
            self.idle_t = random.uniform(C.IDLE_MIN, C.IDLE_MAX)
            return
        self._target_x = target
        self.mood = "walk"
        self.state = "walk"

    def _tick_walk(self, dt):
        self._compute_oy()
        t = getattr(self, "_target_x", None)
        if t is None:
            self._to_idle(); return
        dist = t - self.x
        if abs(dist) < C.WALK_SPEED:
            self.x = t
        else:
            self.facing = 1 if dist > 0 else -1
            self.x += _math.copysign(C.WALK_SPEED, dist)
        if self.bubble_t > 0:
            self.bubble_t -= dt
            if self.bubble_t <= 0:
                self.bubble = None
        if abs(dist) < C.WALK_SPEED:
            self._to_idle()

    def _tick_sleep(self, dt):
        self._compute_oy()
        self._zzz_cd -= dt
        if self._zzz_cd <= 0:
            self._zzz_cd = 0.75
            self._spawn("zzz", 1, x=self.x + 10, y=88)
        # 凌晨了强行睡挺久，日间也由按钮唤醒

    def _tick_act(self, dt):
        self._compute_oy()
        self.act_t -= dt
        if self.bubble_t > 0:
            self.bubble_t -= dt
            if self.bubble_t <= 0:
                self.bubble = None
        if self.act_t <= 0:
            self._to_idle()

    def _to_idle(self):
        self.state = "idle"
        self.mood = "idle"
        self.idle_t = random.uniform(C.IDLE_MIN, C.IDLE_MAX)

    # ---- 粒子 ----
    def _update_particles(self, dt):
        for p in self.particles:
            p["age"] += dt
        self.particles = [p for p in self.particles if p["age"] < p["dur"]]