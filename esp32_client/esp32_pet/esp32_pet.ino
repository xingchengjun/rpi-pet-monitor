/*
 * esp32_pet.ino — ESP32 + ST7789 240x240 WiFi 桌宠状态屏（TFT_eSPI 版）
 *
 * 功能：轮询电脑端桥（bridge.py）获取 DSH/Codex 状态与待审批数，
 *       状态色背景 + 鲸鱼娘动画 + 设备状态田字仪表；单按钮远程批准。
 *
 * 依赖库（Arduino 库管理器安装）：
 *   - TFT_eSPI（作者 Bodmer）—— 引脚/分辨率在库的 User_Setup.h 里配置！
 *   - ArduinoJson (v6)
 *
 * User_Setup.h 关键配置（已在你机器上配好，可亮的那套）：
 *   #define ST7789_DRIVER
 *   #define TFT_WIDTH 240 / TFT_HEIGHT 240
 *   #define TFT_MOSI 23 / TFT_SCLK 18 / TFT_DC 2 / TFT_RST 4 / TFT_CS -1
 *   #define TFT_RGB_ORDER TFT_RGB（或 TFT_BGR，按实际颜色调）
 * 接线：SCK→GPIO18  SDA→GPIO23  RES→GPIO4  DC→GPIO2  BLK→3V3（背光常亮）
 *       或 BLK 接 GPIO 并在 User_Setup.h 加 #define TFT_BL <引脚>（可按键关背光）
 * 模式按钮：GPIO0（接 GND；短按切屏，长按批准/刷新）—— 可改 BTN_MODE
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include "fonts_cn.h"
#include "whale_frames.h"

// ================= 配置（改这里） =================
const char* WIFI_SSID = "202";
const char* WIFI_PASS = "13865520711";
const char* BRIDGE_HOST = "192.168.3.8";   // 电脑 IP
const int   BRIDGE_PORT = 8123;
const char* BRIDGE_TOKEN = "c440337ac660451abb9cb9f95f27e909";   // 与 bridge_config.json 一致
#define POLL_MS 2000                        // 轮询间隔
#define ANIM_MS 250                         // 动画帧间隔（放慢 2 倍，原 125）

// 模式切换按钮（接 GND，内部上拉）
#define BTN_MODE 0

// ================= 全局 =================
TFT_eSPI tft = TFT_eSPI();

// PANTONE 状态色
#define C_IDLE  tft.color565(0, 32, 91)       // 281C 蓝（空闲）
#define C_WORK  tft.color565(0, 163, 92)      // 2300C 绿（工作）
#define C_ALERT tft.color565(206, 17, 38)     // 200C 红（待审批）
#define C_OFF   tft.color565(52, 56, 66)      // 灰（离线）
#define C_ORANGE tft.color565(255, 127, 39)   // 时间橙

DynamicJsonDocument doc(2048);
int screen = 0;          // 0=桌宠 1=设备状态
unsigned long lastPoll = 0, lastAnim = 0;
int state = 3;           // 0 idle 1 work 2 alert 3 offline
int pending = 0, cpu = 0, mem = 0, gpu = 0, disk = 0;
char agent[24] = "离线";
char clockStr[8] = "--:--";

// ================= 文本绘制（12x16 位图字体） =================
const glyph_t* findGlyph(const char* utf8) {
    for (int i = 0; i < GLYPH_COUNT; i++) {
        if (strcmp(GLYPHS[i].ch, utf8) == 0) return &GLYPHS[i];
    }
    return NULL;
}

int textWidth(const char* s) {
    int w = 0;
    while (*s) {
        char ch[4] = {0}; int n = 1;
        if ((*s & 0xE0) == 0xC0) n = 2;
        else if ((*s & 0xF0) == 0xE0) n = 3;
        memcpy(ch, s, n); s += n;
        const glyph_t* g = findGlyph(ch);
        w += (g ? g->w : 12);
    }
    return w;
}

void drawStr(int x, int y, const char* s, uint16_t color) {
    int cx = x;
    tft.startWrite();
    while (*s) {
        char ch[4] = {0}; int n = 1;
        if ((*s & 0xE0) == 0xC0) n = 2;
        else if ((*s & 0xF0) == 0xE0) n = 3;
        memcpy(ch, s, n); s += n;
        const glyph_t* g = findGlyph(ch);
        if (g) {
            for (int row = 0; row < g->h; row++) {
                // 每行 4 字节（32 位），大端
                uint32_t bits = ((uint32_t)g->data[row * 4] << 24)
                              | ((uint32_t)g->data[row * 4 + 1] << 16)
                              | ((uint32_t)g->data[row * 4 + 2] << 8)
                              | (uint32_t)g->data[row * 4 + 3];
                int run = 0;
                for (int col = 0; col <= g->w; col++) {
                    bool on = (col < g->w) && (bits & (0x80000000 >> col));
                    if (on) run++;
                    else if (run) { tft.fillRect(cx + col - run, y + row, run, 1, color); run = 0; }
                }
            }
            cx += g->w;
        } else cx += 16;
    }
    tft.endWrite();
}

// ================= 鲸鱼绘制（TFT_eSPI pushImage + 0x0000 颜色键透明） =================
// 按状态选动画帧，贴底放大显示
void drawWhaleFrame() {
    const char* an = animName(state);
    int ai = 0;
    for (int i = 0; i < WHALE_ANIM_COUNT; i++)
        if (strcmp(WHALE_ANIMS[i].name, an) == 0) ai = i;
    int fc = WHALE_ANIMS[ai].count;
    int idx = (millis() / ANIM_MS) % fc;
    int x = (240 - WHALE_W) / 2;
    int y = 240 - WHALE_H;                    // 贴屏幕底部
    tft.pushImage(x, y, WHALE_W, WHALE_H, WHALE_ANIMS[ai].frames[idx], 0x0000);
}

// ================= 状态 =================
uint16_t bgColor(int st) {
    switch (st) { case 0: return C_IDLE; case 1: return C_WORK; case 2: return C_ALERT; default: return C_OFF; }
}
uint16_t fgColor(int st) { return (st == 1) ? tft.color565(10, 30, 60) : tft.color565(255, 255, 255); }

const char* animName(int st) {
    if (st == 2) return "waiting";
    if (st == 1) return "running";
    return "idle";
}

// ================= 桥通信 =================
bool fetchStatus() {
    HTTPClient http;
    String url = String("http://") + BRIDGE_HOST + ":" + BRIDGE_PORT
               + "/status?token=" + BRIDGE_TOKEN;
    http.begin(url);
    http.setTimeout(3500);
    int code = http.GET();
    if (code != 200) { http.end(); return false; }
    String body = http.getString();
    http.end();
    DeserializationError err = deserializeJson(doc, body);
    if (err) return false;

    int cpend = doc["codex"]["pending_approvals"] | 0;
    bool caw = doc["codex"]["awaiting"] | false;
    int dpend = doc["dsh"]["pending_approvals"] | 0;
    bool daw = doc["dsh"]["awaiting"] | false;
    pending = cpend + dpend;
    if (pending > 0 || caw || daw) state = 2;
    else if ((doc["codex"]["active"] | false) || (doc["dsh"]["active"] | false)) state = 1;
    else state = 0;

    cpu = doc["system"]["cpu"] | 0;
    mem = doc["system"]["mem"] | 0;
    gpu = doc["system"]["gpu"] | 0;
    disk = doc["system"]["disk"] | 0;

    if (daw) snprintf(agent, sizeof(agent), "DSH 待审批");
    else if (caw) snprintf(agent, sizeof(agent), "codex 待审批");
    else if ((doc["codex"]["active"] | false) && (doc["dsh"]["active"] | false))
        snprintf(agent, sizeof(agent), "codex + DSH");
    else if (doc["codex"]["active"] | false) snprintf(agent, sizeof(agent), "codex");
    else if (doc["dsh"]["active"] | false) snprintf(agent, sizeof(agent), "DSH");
    else snprintf(agent, sizeof(agent), "空闲");
    return true;
}

bool approve() {
    HTTPClient http;
    String url = String("http://") + BRIDGE_HOST + ":" + BRIDGE_PORT
               + "/approve?token=" + BRIDGE_TOKEN;
    http.begin(url);
    http.setTimeout(3500);
    int code = http.POST("{}");
    http.end();
    return (code == 200);
}

// ================= 界面 =================
void drawBadge() {
    if (pending <= 0) return;
    char b[8]; snprintf(b, sizeof(b), "!%d", pending);
    int w = textWidth(b) + 8;
    int x = 240 - 10 - w, y = 30;
    tft.fillRoundRect(x, y, w, 30, 8, tft.color565(255, 255, 255));
    drawStr(x + 4, y + 3, b, C_ALERT);
}

void drawPetScreen() {
    uint16_t bg = bgColor(state), fg = fgColor(state);
    tft.fillScreen(bg);
    // 左上：智能体（替代原 deepseek 位置）；右上：时间
    char line[32]; snprintf(line, sizeof(line), "智能体: %s", agent);
    drawStr(8, 4, line, fg);
    int tw = textWidth(clockStr);
    drawStr(240 - 8 - tw, 4, clockStr, C_ORANGE);
    drawBadge();
    drawWhaleFrame();                       // 大鲸鱼贴底
}

void drawGauge(int x, int y, int w, int h, const char* title, int pct,
               uint16_t color, uint16_t fg, const char* extra) {
    tft.drawRoundRect(x, y, w, h, 8, fg);
    int fh = (h - 2) * pct / 100;
    if (fh > 0) tft.fillRect(x + 2, y + h - fh, w - 4, fh, color);
    drawStr(x + 5, y + 4, title, fg);
    char pctTxt[8]; snprintf(pctTxt, sizeof(pctTxt), "%d%%", pct);
    drawStr(x + w - 5 - textWidth(pctTxt), y + h - 28, pctTxt, fg);
    if (extra && extra[0]) drawStr(x + 5, y + h - 28, extra, fg);
}

void drawDeviceScreen() {
    uint16_t bg = bgColor(state), fg = fgColor(state);
    tft.fillScreen(bg);
    drawStr(8, 4, "设备状态", fg);
    int tw = textWidth(clockStr);
    drawStr(240 - 8 - tw, 4, clockStr, C_ORANGE);
    if (pending > 0) { char b[16]; snprintf(b, sizeof(b), "%d 待审批", pending); drawStr(240 - 10 - textWidth(b), 32, b, C_ALERT); }
    if (state == 3) { drawStr(10, 90, "桥离线", fg); return; }

    int margin = 6, gap = 8;
    int cw = (240 - margin * 2 - gap) / 2;
    int ch = (236 - 40 - gap) / 2;
    drawGauge(margin, 40, cw, ch, "CPU", cpu, tft.color565(90, 170, 250), fg, NULL);
    drawGauge(margin + cw + gap, 40, cw, ch, "内存", mem, tft.color565(110, 230, 140), fg, NULL);
    drawGauge(margin, 40 + ch + gap, cw, ch, "GPU", gpu, tft.color565(200, 140, 255), fg, NULL);
    drawGauge(margin + cw + gap, 40 + ch + gap, cw, ch, "磁盘", disk, tft.color565(255, 200, 70), fg, NULL);
}

// ================= 按键（单按钮：短按切屏 / 长按批准或刷新） =================
void handleButtons() {
    if (digitalRead(BTN_MODE) == LOW) {
        delay(40);
        if (digitalRead(BTN_MODE) != LOW) return;
        unsigned long t0 = millis();
        while (digitalRead(BTN_MODE) == LOW && millis() - t0 < 1200) delay(10);
        bool longPress = (millis() - t0) >= 1000;
        while (digitalRead(BTN_MODE) == LOW) delay(10);
        if (longPress) {
            if (pending > 0) approve();
            else fetchStatus();
        } else {
            screen = 1 - screen;
        }
    }
}

// ================= 时间 =================
void updateClock() {
    struct tm ti;
    if (getLocalTime(&ti, 200)) {
        strftime(clockStr, sizeof(clockStr), "%H:%M", &ti);
    } else if (doc["ts"]) {
        time_t t = doc["ts"] | 0;
        t += 8 * 3600;
        struct tm* p = gmtime(&t);
        snprintf(clockStr, sizeof(clockStr), "%02d:%02d", p->tm_hour, p->tm_min);
    }
}

// ================= 主流程 =================
void setup() {
    Serial.begin(115200);
    tft.init();
    tft.setRotation(0);
    tft.setSwapBytes(true);      // 鲸鱼 RGB565 数据按 BGR 面板换字节（修复花屏）

    // 开机自检：白屏 0.3s（能看到白闪=屏幕与 SPI 正常）
    tft.fillScreen(0xFFFF);
    delay(300);
    tft.fillScreen(C_OFF);
    Serial.println("TFT init OK");

    pinMode(BTN_MODE, INPUT_PULLUP);

    drawStr(10, 100, "连接 WiFi...", 0xFFFF);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(200);
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("WiFi connected");
        configTime(8 * 3600, 0, "pool.ntp.org", "ntp.aliyun.com");
        drawStr(10, 120, "已连接", 0xFFFF);
    } else {
        Serial.println("WiFi FAILED");
        drawStr(10, 120, "WiFi 失败", tft.color565(255, 80, 80));
    }
    delay(800);
}

// 增量渲染：状态变化才整屏重绘（不闪）；动画节拍只推鲸鱼帧
int lastKey = -1;
int lastScreen = -1;

int statusKey() {
    int k = state * 100000 + pending * 1000 + cpu * 10 + mem;
    k = k * 10 + gpu;
    k = k * 10 + disk;
    k = k * 10 + (clockStr[3] - '0');   // 分钟变化也重绘
    return k;
}

void loop() {
    if (millis() - lastPoll >= POLL_MS) {
        lastPoll = millis();
        fetchStatus();
        updateClock();
    }
    handleButtons();
    if (screen != lastScreen) {         // 切屏立即整屏重绘
        lastScreen = screen;
        lastKey = -1;
    }
    if (millis() - lastAnim >= ANIM_MS) {
        lastAnim = millis();
        int key = statusKey();
        if (key != lastKey) {
            lastKey = key;
            if (screen == 0) drawPetScreen();
            else drawDeviceScreen();
        } else if (screen == 0) {
            drawWhaleFrame();           // 背景不变，只换鲸鱼帧，不闪
        }
    }
    if (WiFi.status() != WL_CONNECTED && millis() - lastPoll > 15000) {
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASS);
    }
}
