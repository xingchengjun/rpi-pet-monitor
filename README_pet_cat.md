# 树莓派桌宠 🐱（ST7735S 128x160 TFT + K1~K4 按键）

> 本文件是**旧版猫咪桌宠**（纯互动宠物，无监控功能）的存档说明。
> 新版 DSH/Codex 监控体系见根目录 `README.md`。

在树莓派 4B + ST7735S 128x160 TFT 小屏上实现的一只"桌面宠物"：

- 一只程序化像素奶油小猫咪，坐在木桌角，会**眨眼、走路、睡觉、跳舞、撒娇、喊饿**
- 台词气泡 + 时间状态栏 + 夜晚星空背景
- K1~K4 四个按键互动（触摸 / 喂食 / 睡觉 / 一起玩）
- 仿照《DeepSeek 鲸鱼娘桌宠》的"状态机 + 交互 + 随机行为"思路，做成了嵌入式小屏版

```
┌──────────────────────────┐
│ 14:32           🐱      │  ← 时间 / 心情图标
│ ┌────────────────────┐   │
│ │  喵呜~ 最喜欢主人！  │  │  ← 台词气泡
│ └──────────┬─────────┘   │
│            │            │
│          👂🐱👂         │  ← 宠物（眨眼/走路/睡觉/跳舞）
│      ┌──────┐           │
│  🌱  │ 木桌 │           │  ← 桌面 + 盆栽
└──────────────────────────┘
```

## 特性一览

| 交互 | 效果 |
| --- | --- |
| 自动行为 | 随机待机 / 屏幕内踱步 / 说话，饥饿、精力自动衰减 |
| K1 触摸 | 撒娇跳跃 + 爱心 + 随机台词 |
| K2 喂食 | 团子 + 开心吃饭 + 回满饥饿 |
| K3 睡觉/叫醒 | 睡觉回精力（Zzz），低精力会自动睡着 |
| K4 一起玩 | 跳舞 + 音符 + 撒星光 |
| 夜晚模式 | 22:00~7:00 深蓝夜空 + 星星月亮，宠物会说晚安 |
| 台词 | 中文优先，无中文字体自动退英文（可自定义） |

## 目录结构

```
树莓派屏幕/
├── main.py         # 主程序入口
├── demo.py         # 无硬件演示（电脑上预览 / 导出 PNG）
├── test_lcd.py     # 硬件自检（颜色/网格/按键）
├── config.py       # ★ 所有配置：引脚、按键、颜色、台词、参数
├── pet.py          # 宠物状态机
├── painter.py      # 绘制：宠物/背景/气泡/特效
├── fonts.py        # 中文字体自动检测
├── backend.py      # 显示后端（TFT/窗口预览/PNG导出）
├── requirements.txt
├── install.sh      # 树莓派一键安装
└── README.md
```

## 一、接线（ST7735S 128x160）

| 屏幕引脚 | 树莓派 BCM | 物理引脚 | 说明 |
| --- | --- | --- | --- |
| VCC | - | 1 (3.3V) | 3.3V |
| GND | - | 6 | 地 |
| SCL / SK | GPIO11 | 23 | SPI SCLK |
| SDA / SI | GPIO10 | 19 | SPI MOSI |
| RES / RS | GPIO24 | 18 | 复位 |
| A0 / DC | GPIO25 | 22 | 数据/命令 |
| CS | GPIO8 | 24 | SPI CE0 |
| BLK / LED | GPIO18 | 12 | 背光（若模块跳线已接3.3V则省略） |

四个按键：一端接 GPIO，另一端接 **GND**（内部上拉）：
K1=GPIO17(物理11)  K2=GPIO27(物理13)  K3=GPIO22(物理15)  K4=GPIO23(物理16)

所有引脚都可在 `config.py` 里改（`BUTTONS` / `GPIO_*` / `ROTATE` / `H_OFFSET` / `V_OFFSET`）。

## 二、安装

树莓派（Raspberry Pi OS 官方系统）：

```bash
sudo bash install.sh
# 会自动：装依赖 + 启用 SPI（修改 config.txt，需要重启一次）
sudo reboot
```

重启后：

```bash
# 1. 硬件自检：红绿蓝白黑 → 网格 → 按键方块
python3 test_lcd.py

# 2. 跑桌宠
python3 main.py
```

> 不想改系统的话也可以手动装：`sudo apt install python3-pil python3-spidev python3-gpiozero python3-luma.lcd fonts-noto-cjk`

**电脑上预览（不需要任何硬件，Windows/Mac 都行）：**

```bash
pip install Pillow
python demo.py --window     # 弹出窗口实时预览 20 秒动画
python demo.py              # 导出 PNG 帧到 out_png/
python main.py --mode preview   # 用真实主逻辑 + 按键模拟预览
```

> demo 用时间轴自动演示：撒娇 → 吃饭 → 跳舞 → 喊饿 → 睡觉 → 起床 → 踱步

## 三、接线 / 显示不对怎么办？

| 现象 | 处理 |
| --- | --- |
| 颜色红蓝颠倒 | `config.py` 里 `RGB_ORDER = False` |
| 画面旋转了 90° | 调 `ROTATE = 0/1/2/3` |
| 画面整体偏移几个像素 | 调 `H_OFFSET` / `V_OFFSET`（-2~2） |
| 白花花看不清 | 用 `test_lcd.py` 逐个看纯色，确认 CS/DC/RES 没接错 |
| 中文台词变成方框 | `sudo apt install fonts-noto-cjk`；没装时自动用英文台词 |

## 四、自定义

- 宠物名字：`config.py` → `PET_NAME`
- 按键功能 / 引脚：`config.py` → `BUTTONS`
- 台词：`config.py` → `LINES`（每条中英文成对）
- 节奏 / 数值：`config.py` 顶部参数（`FRAME_MS`、`WALK_SPEED`、`HUNGER_DROP_PER_MIN`…）
- 配色：`config.py` → 主题配色区

## 五、开机自启（可选）

```bash
crontab -e
# 加一行：
@reboot cd /home/pi/树莓派屏幕 && python3 main.py >/dev/null 2>&1 &
```

## 依赖说明

- **树莓派真机**：Pillow / spidev / gpiozero / luma.lcd（驱动 ST7735S）
- **电脑预览**：只需要 Pillow（tkinter 自带），完全不需要树莓派硬件

## 致谢

创意参考 [DeepSeek 鲸鱼娘桌宠](https://blog.csdn.net/qq_45707187/article/details/163761507)（状态机 + 事件驱动 + 随机行为的设计思路），本项目为嵌入式小屏重制，代码与素材均为本仓库原创。
