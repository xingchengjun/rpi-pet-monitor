# DSH/Codex 状态屏 —— 电脑端桥服务（bridge.py）

> 这个仓库原名《树莓派桌宠状态屏（ST7735S + K1-K4）》。树莓派已撤下，
> 现在的**客户端是 ESP32**（见独立仓库 [esp32-pet-monitor](https://github.com/xingchengjun/esp32-pet-monitor)）。
> 本仓库保留下来的核心是 **电脑端桥服务 `pc_bridge/bridge.py`**——ESP32 依赖它才能获知
> DSH / Codex 状态并远程批准。树莓派客户端代码（`pi_client/`）保留存档，已不再使用。

```
┌─ 电脑 Windows ───────────────────────────┐         ┌─ ESP32 (esp32-pet-monitor) ─┐
│  pc_bridge/bridge.py (桥, 开机自启)        │  HTTP   │  esp32_pet.ino                │
│  ├ DSH 状态 ← ~/.dsh/sessions/*.zstd     │◄───────►│  ├ 轮询 /status (2s, token)    │
│  ├ Codex 状态+待审批 ← ~/.codex/sessions │  +token │  ├ ST7789 240x240 屏          │
│  ├ PC CPU/内存/GPU/磁盘 (ctypes 零依赖)   │         │  ├ 桌宠屏 + 设备屏            │
│  └ POST /approve → Codex 窗口发回车       │         │  └ 单键: 长按=批准/刷新       │
└──────────────────────────────────────────┘         └────────────────────────────┘
```

## 它做什么

`pc_bridge/bridge.py` 跑在**电脑（Windows）**上，用**仅标准库**读取本机 DSH / Codex 的实时状态与待审批数，
通过 HTTP + token 暴露给 ESP32：

- **DSH 状态**：读取 `~/.dsh/sessions/**/session-*/session.jsonl.zstd`（zstd 压缩），判断 `active` 与 `pending_approvals`。
  本机用 `C:/msys64/ucrt64/bin/zstd.exe` 本地解压（树莓派已撤，不再借道 SSH）。
- **Codex 状态**：读取 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`，判断 `active`、`awaiting`、`pending_approvals`。
  待审批 = 会话尾部存在"已请求但无输出"的工具调用（`sandbox_permissions` / `ask_user_question` 等）。
- **系统状态**：CPU / 内存 / GPU / 磁盘使用率（`ctypes` 读 Windows，零第三方依赖；GPU 用 `nvidia-smi`，否则 WMI 只给型号）。
- **批准**：`POST /approve` 向 Codex 终端（前台窗口或按标题定位的窗口）发送回车，完成一次审批。

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 存活检查（无需 token） |
| GET | `/status?token=…` | 完整状态 JSON（`dsh`、`codex`、`system`、`bridge`） |
| POST | `/approve?token=…` | 批准；可选 body `{"probe": true}` 只探测不真正发键 |
| GET | `/` | 简要说明页 |

鉴权：`?token=` 或请求头 `X-Token`，需与 `bridge_config.json` 里的 `token` 一致。

## 运行（Windows，Python 3.9+）

```powershell
pip install zstandard   # 可选：增强 DSH 会话探测；不装也可用本机 zstd.exe
cd pc_bridge
python bridge.py        # 首次运行自动生成 bridge_config.json，改好 token 再启动
```

自检：`curl http://127.0.0.1:8123/status?token=你的token` 应返回 JSON。

**开机自启**：
```powershell
powershell -ExecutionPolicy Bypass -File pc_bridge\install_bridge_task.ps1
```
卸载：`schtasks /Delete /TN "DSH-Pi-Bridge" /F`

**防火墙放行 8123**（ESP32 才能连上）：
```
netsh advfirewall firewall add rule name="dsh-pi-bridge" dir=in action=allow protocol=TCP localport=8123
```

## 配置（bridge_config.json）

| 键 | 说明 |
|---|---|
| `port` | 监听端口（默认 8123；**ESP32 端需一致**） |
| `token` | 三端一致（桥 / ESP32 / 树莓派）；**务必改默认值** |
| `codex.window_title` | Codex 终端窗口标题正则（不区分大小写） |
| `codex.mode` | `foreground`=直接发前台窗口（用前把 Codex 窗口点到最前）\| `window`=按标题定位窗口再回车(config 必填) |
| `activity.active_window_s` | 最近 N 秒内有写入 ⇒ 工作中（默认 30） |
| `activity.recent_window_s` | 超过 N 秒无写入 ⇒ 视为未运行（默认 600） |
| `activity.pending_window_s` | 待审批提醒持续窗口（默认 3600） |
| `dsh_sessions_dir` / `codex_sessions_dir` | 会话目录覆盖；`null` = 默认 `~/.dsh`、`~/.codex` |
| `debug_tail` | 状态里附带最新会话尾部片段（排障用，默认 false） |

> `pi_ssh`（借道树莓派 zstd 解压）已废弃：本机直接用 `zstd.exe` 本地解压，无需树莓派。

## 目录结构（本仓库相关）

```
pc_bridge/bridge.py               桥服务（仅标准库）
pc_bridge/bridge_config.json      配置（含 token，已 .gitignore）
pc_bridge/bridge_config.json.example  配置模板（占位符，可入库）
pc_bridge/install_bridge_task.ps1 Windows 登录自启脚本
pi_client/pet.py                  树莓派客户端（已停用，保留存档）
design/compress_whale.py          鲸鱼娘素材压缩管线（生成 ESP32 的 whale_frames.h）
design/gen_designs.py             精灵/屏幕预览 PNG 生成
```

## 与 ESP32 客户端的关系

ESP32 端在独立仓库 [esp32-pet-monitor](https://github.com/xingchengjun/esp32-pet-monitor)。
其 `esp32_pet/esp32_pet.ino` 顶部的 `BRIDGE_HOST / BRIDGE_PORT / BRIDGE_TOKEN` 必须与本桥一致。

## 安全提示

- **务必改 token**：桥监听 `0.0.0.0`，局域网内任何知道 token 的设备都能批准你的 Codex 操作。
- 含真实凭据的文件（`pc_bridge/bridge_config.json`、`pi_client/pet_config.json`、`esp32_client/`）已加入 `.gitignore`，不会入库。

## 鲸鱼娘动画素材（默认启用，供 ESP32 用）

素材来自 [codex-pet-DeepSeek-girl](https://github.com/xpy12367/codex-pet-DeepSeek-girl)（**无许可协议**，仅限个人自用，勿商用/再分发）。
`design/compress_whale.py` 会把原始帧压缩/转成 RGB565，再 `gen_whale_c.py` 生成 ESP32 的 `whale_frames.h`。
该资源及生成物不入库（见 `.gitignore`），需本地素材后自行生成。
