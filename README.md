# 树莓派桌宠状态屏（ST7735S 128x160 + K1-K4）

在树莓派 4B + 1.8 寸 ST7735S 小屏上监控**电脑上的 DSH / Codex 状态**，桌宠式 UI + 按键远程操作。

本仓库包含两套可运行程序：

| 程序 | 目录 | 说明 |
|---|---|---|
| **监控桌宠（新版，本项目核心）** | `pc_bridge/` + `pi_client/` | DSH/Codex 状态监控、待审批远程批准、桌宠/监控双屏 |
| **猫咪桌宠（旧版，纯互动）** | 根目录 `main.py` 等 | 宠物养成/互动，无监控；存档文档见 `README_pet_cat.md` |

> 两套程序共用同一块屏幕与按键。监控版为当前主线，猫咪版作为宠物形态备选（精灵可选）。

## 快速体验（电脑上，无需任何硬件）

```powershell
pip install pillow
# 1. 生成鲸鱼娘/内置精灵的屏幕预览帧（preview_out/ 下 128x160 PNG）
python pi_client/pet.py --preview-frames 12
# 2. 弹出实时预览窗口（模拟 待审批→工作→空闲 状态循环，1/2 切屏，ESC 退出）
python pi_client/pet.py --preview-window 30
```

```
┌─ 电脑 Windows ──────────────────────────┐   ┌─ 树莓派 4B ───────────────────────┐
│  bridge.py (桥服务, 开机自启, token)     │   │  pet.py (systemd 自启, 断线重连)    │
│  ├ DSH 状态 ← ~/.dsh/sessions/*.zstd    │◄─►│  ├ 轮询 /status (2s, 带 token)      │
│  ├ Codex 状态+待审批 ← ~/.codex/sessions │HTTP│  ├ ST7735 128x160 竖屏 (spidev+gpiod 直连) │
│  ├ PC CPU/内存 (ctypes, 零依赖)          │   │  ├ 像素桌宠 + 双屏 UI (Pillow)      │
│  └ POST /approve → Codex 终端发回车      │   │  └ K1-K4 按键 (GPIO 消抖)          │
└──────────────────────────────────────────┘   └───────────────────────────────────┘
```

## 目录结构

```
pc_bridge/
  bridge.py               # 电脑端桥服务（仅标准库，可选 zstandard）
  bridge_config.json      # 桥配置（含 token，与树莓派端一致）
  install_bridge_task.ps1 # 注册 Windows 登录自启任务
  bridge.log              # 运行日志（自动生成）
pi_client/
  pet.py                  # 树莓派主程序（--preview-frames / --preview-window 预览模式）
  art.py                  # 像素素材 + 屏幕合成 + 鲸鱼娘动画加载
  pet_config.json         # 树莓派端配置（bridge_url / token / 宠物选择）
  test_lcd.py             # 硬件自检（纯色/网格/按键）
  install.sh              # 树莓派一键安装（SPI+依赖+自启）
  requirements.txt
  pet.service             # systemd 自启样例
  assets/whale/anims/     # 鲸鱼娘压缩素材（9 组动画 57 帧）
design/
  gen_designs.py          # PC 上生成精灵/屏幕预览 PNG
  compress_whale.py       # 压缩鲸鱼娘素材脚本
  whale_assets/           # 压缩产物（anims + zip）
  whale_raw/              # 下载的原始仓库（可删）
  *.png                   # 设计稿
README_pet_cat.md         # 旧版猫咪桌宠存档文档
```

## 硬件接线（ST7735S 模块，排针从左到右：GND VCC SCL SDA RST DC CS BLK K4 K3 K2 K1）

| 模块针脚 | 树莓派 (BCM) | 说明 |
|---|---|---|
| GND | Pin 6 (GND) | |
| VCC | Pin 1 (3.3V) | **严禁接 5V** |
| SCL | GPIO11 (Pin 23) | SPI SCLK |
| SDA | GPIO10 (Pin 19) | SPI MOSI |
| RST | GPIO25 (Pin 22) | |
| DC | GPIO24 (Pin 18) | |
| CS | GPIO8 (Pin 24) | SPI CE0 |
| BLK | Pin 1 (3.3V) 或 GPIO26 | 背光；接 GPIO 可按键 K4 开关（pet.py 里 `backlight_pin`） |
| K4 | GPIO19 (Pin 35) | 按键（低电平触发，内部上拉） |
| K3 | GPIO13 (Pin 33) | |
| K2 | GPIO6 (Pin 31) | |
| K1 | GPIO5 (Pin 29) | 最靠近屏幕的按键 |

> 引脚在 `pi_client/pet.py` 的 `CONFIG` 里可改。若实测按键是"按下接 VCC"，把 `pull_up=True` 改成 `pull_down=True`。

## 按键逻辑

| 按键 | 有 Codex 待审批时 | 空闲时 |
|---|---|---|
| K1 | **批准**（桥向 Codex 终端发回车） | 桌宠屏 ⇄ 监控屏 |
| K2 | 桌宠屏 ⇄ 监控屏 | 桌宠屏 ⇄ 监控屏 |
| K3 | 立即刷新 | 立即刷新 |
| K4 | 背光开关 | 背光开关 |

## 部署

### 1. 电脑端（Windows，python 3.9+）

```powershell
cd pc_bridge
python bridge.py                 # 直接启动（bridge_config.json 已含 token）
# 需要改的配置在 bridge_config.json：
#   codex.window_title 改成你 Codex 终端的窗口标题（默认匹配 "codex"）
#   codex.mode: window=定位窗口再回车(推荐) | foreground=直接发前台窗口
#   token 已预生成，两端一致；想换就同时改 bridge_config.json 与 pi_client/pet_config.json
python bridge.py
```

**开机自启**：`powershell -ExecutionPolicy Bypass -File pc_bridge\install_bridge_task.ps1`（注册登录时自启任务，卸载用 `schtasks /Delete /TN "DSH-Pi-Bridge" /F`）。

**防火墙**：放行 TCP 8123（入站，专用网络），否则树莓派连不上：
`netsh advfirewall firewall add rule name="dsh-pi-bridge" dir=in action=allow protocol=TCP localport=8123`

自检：电脑上 `curl http://192.168.3.8:8123/status?token=你的token` 应返回 JSON。

### 2. 树莓派端（Raspberry Pi OS Lite）

```bash
# 把 pi_client/ 整个目录拷贝到树莓派（U盘/scp 均可），然后：
cd pi_client
bash install.sh        # 启用SPI + 装依赖 + 拷贝到 ~/pet + 注册自启（首次需重启）
# 编辑 ~/pet/pet_config.json：bridge_url 改成电脑 IP:端口（token 两端已一致）
sudo reboot            # 首次启用 SPI 必须重启
# 重启后先自检硬件：
cd ~/pet && python3 test_lcd.py      # 纯色/网格/按键测试
# 正式运行：
python3 pet.py          # 或已注册的 sudo systemctl start pet
```

**开机自启**：`sudo cp pet.service /etc/systemd/system/ && sudo systemctl enable --now pet`

## 状态判定逻辑（bridge 侧，阈值可在 bridge_config.json 调整）

| 项 | 判定 |
|---|---|
| DSH active | `~/.dsh/sessions/**/session-*/session.jsonl.zstd` 最近 30s 内有写入 |
| Codex active | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` 最近 30s 内有写入 |
| Codex 待审批 | 最新会话尾部存在"已请求但无输出"的 function_call（10 分钟内活跃才计） |

> Codex 待审批检测依赖事件流格式，不同 Codex 版本字段可能有差异。
> 若显示不准：把 `bridge_config.json` 里 `debug_tail: true`，重启后
> `curl .../status` 看 `codex.tail` 的原始事件，把内容发来校准检测器。

## 精灵选择与设计稿

`design/*.png` 里有 3 款内置像素精灵（小鲸鱼 / 团子 / 蓝精灵）及双屏 mockup 预览。
选定后改 `pi_client/pet_config.json` 的 `sprite_source`（`builtin` + `pet_sprite` = WHALE/BLOB/SPIRIT）。
旧版猫咪（根目录）作为备选形态。

## 鲸鱼娘动画素材（默认启用）

`pi_client/assets/whale/anims/` 内置了从 [codex-pet-DeepSeek-girl](https://github.com/xpy12367/codex-pet-DeepSeek-girl)
仓库压缩来的真·鲸鱼娘动画（9 组：待机/等待/左右跑/挥手/跳跃/失败/审查，共 57 帧，
单帧 32px，原始 5.54MB → 0.12MB，约 45 倍压缩）。

- 程序自动检测：`pet.py` 的 `sprite_source` 设为 `auto`（默认）时，素材存在就优先用鲸鱼娘；可改 `whale`（强制）或 `builtin`（强制内置像素）。
- 状态联动：待机→idle 动画，工作→running，待审批→waiting，8fps 循环播放。
- 压缩/再生成：`design/compress_whale.py`（需 `design/whale_raw/repo.zip`，重新生成后 robocopy 到 `pi_client/assets/whale/anims/`）。
- **注意**：该仓库未带 license（非官方同人项目），素材仅限个人自用，勿商用/再分发。

## 故障排查

| 症状 | 处理 |
|---|---|
| 屏幕花屏/偏色/偏移 | 直连驱动 `pi_client/st7735_driver.py`，调 `pet.py` 的 `CONFIG["lcd"]`：`bgr`（True/False）、`invert`（颜色反相）、`rotation`（0/1/2/3）、`spi_speed` |
| 屏幕不亮但程序在跑 | 检查 BLK 是否接 3.3V；VCC 是否 3.3V；`journalctl -u pet -n 20` 看初始化报错 |
| 按键无反应 | 检查 K1-K4 接线与 `CONFIG["buttons"]` 引脚；gpiozero 报错看 journalctl |
| 屏上 OFFLINE | 桥没启动 / token 不一致 / 防火墙没放行 / IP 写错 |
| GPIO busy / GPIO not allocated | Debian 13 的 RPi.GPIO 已弃用；本项目用 `st7735_driver.py`（spidev+gpiod）绕开，勿再用 luma.lcd |
| 按键批准 | 已开启（`approve_enabled: true`）。桥为前台模式：**按 K1 前把 Codex/ChatGPT 窗口点到最前**，K1 = 向该窗口发回车 = 批准；探测：`POST /approve {"probe":true}` |
| Python 报 GBK 编码错 | 桥已内置 UTF-8 容错；树莓派端若出现请贴日志 |

## 安全提示

- **务必改默认 token**：桥监听 0.0.0.0，局域网内任何设备知道 token 都能批准你的 Codex 操作。
- 屏幕/按键全部 3.3V 电平，勿接 5V 排针。

## 下一步（需要你/实机的部分）

- [ ] 打开 `preview_out/*.png` 或跑 `python pi_client/pet.py --preview-window 30` 确认鲸鱼娘效果
- [ ] 按接线表接好硬件 → `test_lcd.py` 自检 → 实机跑 `pet.py`
- [ ] 告诉我你 Codex 终端的窗口标题（`bridge_config.json` 的 `codex.window_title`），让"按键批准"生效
- [ ] 实际触发一次 Codex 审批，校准"待审批"检测（`debug_tail`）
