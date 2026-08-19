# ESP32-C3 mini + ST7789 240x240 WiFi 桌宠状态屏

树莓派版的 WiFi 轻量版：ESP32-C3 mini 通过 WiFi 轮询电脑端桥服务，
显示 DSH/Codex 状态、待审批提醒、设备状态（CPU/内存/GPU/磁盘），按键远程批准。

```
电脑(bridge.py)  ←WiFi HTTP+token→  ESP32-C3 mini → ST7789 240x240
```

## 依赖库（Arduino 库管理器安装）
- **Adafruit GFX Library**
- **Adafruit ST7789 Library**
- **ArduinoJson** (v6)

## 接线（ST7789 240x240，按实际连接）

| 屏幕引脚 | ESP32-C3 mini GPIO | 说明 |
|---|---|---|
| SCK | **GPIO5** | SPI 时钟 |
| SDA (MOSI) | **GPIO1** | SPI 数据 |
| RES | **GPIO2** | 复位 |
| DC | **GPIO3** | 数据/命令 |
| BLK | **GPIO10** | 背光（常亮/可按键 K4 关） |
| CS | **GND** | 板上唯一 SPI 设备，直接接地 |
| VCC | 3V3 | |
| GND | GND | |

按键（K1-K4，接 GND，内部上拉，**可改代码 BTN_* 引脚**）：
K1=GPIO4  K2=GPIO6  K3=GPIO7  K4=GPIO8

> ESP32-C3 的 GPIO11/12 是 flash 引脚勿用；GPIO18/19 是 USB 勿用。若按键与屏有冲突按需换。

## 配置与烧录

1. 打开 `esp32_pet.ino`，改顶部配置：
   - `WIFI_SSID` / `WIFI_PASS`
   - `BRIDGE_HOST`（电脑 IP，如 192.168.3.8）、`BRIDGE_TOKEN`（与 bridge_config.json 一致）
2. Arduino IDE：开发板选 **ESP32C3 Dev Module**（需装 esp32 板支持包）；USB 选择对应串口
3. 上传，串口监视器看 `连接 WiFi...` → `已连接`
4. 电脑端确保 bridge.py 在运行（token 一致）

## 按键逻辑

| 按键 | 有待审批时 | 空闲时 |
|---|---|---|
| K1 | **批准**（POST /approve，桥向电脑前台窗口发回车） | 桌宠屏 ⇄ 设备屏 |
| K2 | 桌宠屏 ⇄ 设备屏 | 桌宠屏 ⇄ 设备屏 |
| K3 | 立即刷新 | 立即刷新 |
| K4 | 背光开关 | 背光开关 |

## 界面（240x240 方形布局）

- **背景状态色**：空闲=281C 蓝 / 工作=2300C 绿 / 待审批=200C 红 / 离线=灰
- **桌宠屏**：左上 deepseek、右上时间(橙)、智能体名、中央鲸鱼娘动画（idle/running/waiting）、底部 cpu%
- **设备屏**：田字 2x2 圆角仪表（左上名称、右下百分比、下半按百分比填充）
- 待审批时红色徽标 `!N`

## 素材与字库（自动生成，勿手改）

- `whale_frames.h`：鲸鱼娘 18 帧（idle/running/waiting）RGB565，透明=0x0000 颜色键
  生成：`python esp32_client/tools/gen_whale_c.py`
  （素材来自 codex-pet-DeepSeek-girl，无许可协议，仅个人使用，故不入库）
- `fonts_cn.h`：12x16 中文字库（57 字形，Noto/雅黑渲染）
  生成：`python esp32_client/tools/gen_font_cn.py`

## 备注
- 时间走 NTP（UTC+8），未同步时用桥的 `ts` 兜底
- DSH/Codex 任一待审批 → 红背景 + `!N` 徽标 + waiting 动画
- 桥的 DSH 审批检测借道树莓派 zstd 解压（树莓派版专属），ESP32 只读桥的结果，无需感知
