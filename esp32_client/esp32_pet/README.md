# ESP32 + ST7789 240x240 WiFi 桌宠状态屏（TFT_eSPI 版）

ESP32 通过 WiFi 轮询电脑端桥服务，显示 DSH/Codex 状态、待审批提醒、
设备状态（CPU/内存/GPU/磁盘），单按钮远程批准。

```
电脑(bridge.py)  ←WiFi HTTP+token→  ESP32 → ST7789 240x240
```

## 依赖库（Arduino 库管理器安装）
- **TFT_eSPI**（作者 Bodmer）—— 引脚/分辨率在它的 `User_Setup.h` 里配置
- **ArduinoJson** (v6)

## ✅ 已验证能亮的配置（普通 ESP32 Dev Module）

**接线**：
| 屏幕引脚 | ESP32 GPIO | 说明 |
|---|---|---|
| SCK | **GPIO18** | SPI 时钟 |
| SDA (MOSI) | **GPIO23** | SPI 数据 |
| RES | **GPIO4** | 复位 |
| DC | **GPIO2** | 数据/命令 |
| BLK | **3V3** | 背光常亮（或接 GPIO 以便按键关） |
| VCC | 3V3 | |
| GND | GND | |
| CS | 无（-1） | 本模块无 CS，TFT_eSPI 设为 -1 |

**User_Setup.h**（`D:\Documents\Arduino\libraries\TFT_eSPI\User_Setup.h`）关键配置：
```cpp
#define ST7789_DRIVER
#define TFT_WIDTH   240
#define TFT_HEIGHT  240
#define TFT_MISO    -1
#define TFT_MOSI    23
#define TFT_SCLK    18
#define TFT_CS      -1
#define TFT_DC      2
#define TFT_RST     4
// #define TFT_BL    26   // 背光接 GPIO 时启用
#define TFT_RGB_ORDER TFT_RGB   // 颜色反了换成 TFT_BGR
#define SPI_FREQUENCY 27000000  // 不稳就降 16000000 / 10000000
```

## 模式按钮
**GPIO0 → GND**（内部上拉，可改代码 `BTN_MODE`）：
- **短按**：桌宠屏 ⇄ 设备屏
- **长按（>1s）**：有待审批时 = 批准（POST /approve，桥向电脑前台窗口发回车）；否则 = 刷新

## Token
`BRIDGE_TOKEN` = `pc_bridge/bridge_config.json` 里的 `"token"`（三端一致：桥/ESP32/树莓派）。

## 界面（240x240）
- 背景状态色：空闲=281C 蓝 / 工作=2300C 绿 / 待审批=200C 红 / 离线=灰
- 桌宠屏：左上 deepseek、右上时间(橙)、智能体名、中央鲸鱼娘动画（idle/running/waiting）、底部 cpu%
- 设备屏：田字 2x2 圆角仪表（左上名称/右下百分比/下半按百分比填充）
- 待审批：白色 `!N` 徽标

## 素材与字库（自动生成，勿手改）
- `whale_frames.h`：鲸鱼娘 18 帧 RGB565，透明=0x0000（TFT_eSPI pushImage 颜色键）
  生成：`python esp32_client/esp32_pet/tools/gen_whale_c.py`
  （素材来自 codex-pet-DeepSeek-girl，无许可协议，仅个人使用，故不入库）
- `fonts_cn.h`：12x16 中文字库（119 字形，Droid Sans Fallback，Apache 2.0）
  生成：`python esp32_client/esp32_pet/tools/gen_font_cn.py`

## 排障速查
| 现象 | 处理 |
|---|---|
| 上传失败/No serial data | 关串口监视器；按住 BOOT 再上传，见 Connecting 松手；或 Upload Speed 改 115200；或先"工具→擦除 Flash" |
| 白屏/黑屏 | 查接线（SCK/SDA 对调试）；User_Setup.h 的 ST7789_DRIVER / SPI 频率 / RGB 顺序 |
| 串口看不到打印 | 工具 → USB CDC On Boot → Enabled（C3） |
| WiFi FAILED | 检查 SSID/密码、桥是否在跑、token 是否一致 |
| 崩溃重启（Guru Meditation） | 确认开发板选对（ESP32 Dev Module）；TFT_eSPI 与核心版本匹配；BLK 别接 5V |

> 注：ESP32-C3 mini 也可以跑本固件，但需把 User_Setup.h 的引脚改成 C3 实际接线
> （如 SCK=5/MOSI=1/DC=3/RST=2），并在 IDE 里选 ESP32C3 Dev Module。
> 本项目实测在普通 ESP32 Dev Module + 18/23/2/4 上点亮成功。
