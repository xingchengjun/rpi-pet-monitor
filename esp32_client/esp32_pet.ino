/*
 * esp32_pet.ino — ESP32-C3 mini + ST7789 240x240 WiFi 桌宠状态屏
 *
 * 功能：轮询电脑端桥（bridge.py）获取 DSH/Codex 状态与待审批数，
 *       显示状态色背景 + 鲸鱼娘动画 + 设备状态田字仪表；按键远程批准。
 *
 * 依赖库（Arduino 库管理器安装）：
 *   - Adafruit GFX Library
 *   - Adafruit ST7789 Library
 *   - ArduinoJson (v6)
 *
 * 接线（按用户实接）：
 *   SCK  -> GPIO5     SDA(MOSI) -> GPIO1
 *   RES  -> GPIO2     DC -> GPIO3
 *   BLK  -> GPIO10    CS -> GND（板上唯一 SPI 设备）
 * 按键（可改 BTN_*）：
 *   K1=GPIO4  K2=GPIO6  K3=GPIO7  K4=GPIO8 （接 GND，内部上拉）
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include "fonts_cn.h"
#include "whale_frames.h"

// ================= 配置（改这里） =================
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASS";
const char* BRIDGE_HOST = "192.168.3.8";   // 电脑 IP
const int   BRIDGE_PORT = 8123;
const char* BRIDGE_TOKEN = "YOUR_TOKEN";   // 与 bridge_config.json 一致
#define POLL_MS 2000                        // 轮询间隔
#define ANIM_MS 125                         // 动画帧间隔 (8fps)

// 屏幕引脚
#define TFT_SCK 5
#define TFT_MOSI 1
#define TFT_DC  3
#define TFT_RST 2
#define TFT_BLK 10

// 按键引脚（低电平触发）
#define BTN_K1 4
#define BTN_K2 6
#define BTN_K3 7
#define BTN_K4 8

// ================= 全局 =================
Adafruit_ST7789 tft = Adafruit_ST7789(&SPI, -1 /*CS=GND*/, TFT_DC, TFT_RST);

// PANTONE 状态色
#define C_IDLE  tft.color565(0, 32, 91)       // 281C 蓝（空闲）
#define C_WORK  tft.color565(0, 163, 92)      // 2300C 绿（工作）
#define C_ALERT tft.color565(206, 17, 38)     // 200C 红（待审批）
#define C_OFF   tft.color565(52, 56, 66)      // 灰（离线）
#define C_ORANGE tft.color565(255, 127, 39)   // 时间橙

DynamicJsonDocument doc(2048);
int screen = 0;          // 0=桌宠 1=设备状态
bool backlight = true;
unsigned long lastPoll = 0, lastAnim = 0;
int state = 3;           // 0 idle 1 work 2 alert 3 offline
int pending = 0, cpu = 0, mem = 0, gpu = 0, disk = 0;
char agent[24] = "离线";
char clockStr[8] = "--:--";

// ================= 文本绘制（12x16 位图字体，startWrite 批量） =================
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
                uint16_t bits = (g->data[row * 2] << 8) | g->data[row * 2 + 1];
                // 行内连续位 -> fillRect 批量
                int run = 0;
                for (int col = 0; col <= g->w; col++) {
                    bool on = (col < g->w) && (bits & (0x8000 >> col));
                    if (on) run++;
                    else if (run) { tft.fillRect(cx + col - run, y + row, run, 1, color); run = 0; }
                }
            }
            cx += g->w;
        } else cx += 12;
    }
    tft.endWrite();
}

// ================= 鲸鱼绘制（RGB565 + 0x0000 颜色键） =================
void drawWhale(const uint16_t* frame) {
    int x = (240 - WHALE_W) / 2, y = 55;
    tft.startWrite();
    for (int yy = 0; yy < WHALE_H; yy++) {
        int run = -1;
        for (int xx = 0; xx <= WHALE_W; xx++) {
            bool opaque = (xx < WHALE_W) && (frame[yy * WHALE_W + xx] != 0x0000);
            if (opaque && run < 0) run = xx;
            if ((!opaque || xx == WHALE_W) && run >= 0) {
                int len = xx - run;
                tft.setAddrWindow(x + run, y + yy, len, 1);
                tft.writePixels(&frame[yy * WHALE_W + run], len, true, false);
                run = -1;
            }
        }
    }
    tft.endWrite();
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
    int x = 240 - 10 - w, y = 4;
    tft.fillRoundRect(x, y, w, 18, 6, tft.color565(255, 255, 255));
    drawStr(x + 4, y + 1, b, C_ALERT);
}

void drawHeader(uint16_t fg) {
    drawStr(10, 6, "deepseek", fg);
    int tw = textWidth(clockStr);
    drawStr(240 - 10 - tw, 6, clockStr, C_ORANGE);
}

void drawPetScreen() {
    uint16_t bg = bgColor(state), fg = fgColor(state);
    tft.fillScreen(bg);
    drawHeader(fg);
    drawBadge();
    char line[32]; snprintf(line, sizeof(line), "智能体: %s", agent);
    drawStr(10, 30, line, fg);
    // 鲸鱼（按状态选动画）
    const char* an = animName(state);
    int ai = 0;
    for (int i = 0; i < WHALE_ANIM_COUNT; i++)
        if (strcmp(WHALE_ANIMS[i].name, an) == 0) ai = i;
    int fc = WHALE_ANIMS[ai].count;
    int idx = (millis() / ANIM_MS) % fc;
    drawWhale(WHALE_ANIMS[ai].frames[idx]);
    // 底部 cpu
    char cpuTxt[24]; snprintf(cpuTxt, sizeof(cpuTxt), "cpu %d%%", cpu);
    drawStr(10, 224, cpuTxt, fg);
}

void drawGauge(int x, int y, int w, int h, const char* title, int pct,
               uint16_t color, uint16_t fg, const char* extra) {
    tft.drawRoundRect(x, y, w, h, 8, fg);
    int fh = (h - 2) * pct / 100;
    if (fh > 0) tft.fillRect(x + 2, y + h - fh, w - 4, fh, color);
    drawStr(x + 5, y + 3, title, fg);
    char pctTxt[8]; snprintf(pctTxt, sizeof(pctTxt), "%d%%", pct);
    drawStr(x + w - 5 - textWidth(pctTxt), y + h - 20, pctTxt, fg);
    if (extra && extra[0]) drawStr(x + 5, y + h - 20, extra, fg);
}

void drawDeviceScreen() {
    uint16_t bg = bgColor(state), fg = fgColor(state);
    tft.fillScreen(bg);
    drawHeader(fg);
    drawStr(10, 30, "设备状态", fg);
    if (pending > 0) { char b[16]; snprintf(b, sizeof(b), "%d 待审批", pending); drawStr(240 - 10 - textWidth(b), 30, b, C_ALERT); }
    if (state == 3) { drawStr(10, 80, "桥离线", fg); return; }

    int margin = 6, gap = 8;
    int cw = (240 - margin * 2 - gap) / 2;
    int ch = (236 - 44 - gap) / 2;
    drawGauge(margin, 44, cw, ch, "CPU", cpu, tft.color565(90, 170, 250), fg, NULL);
    drawGauge(margin + cw + gap, 44, cw, ch, "内存", mem, tft.color565(110, 230, 140), fg, NULL);
    drawGauge(margin, 44 + ch + gap, cw, ch, "GPU", gpu, tft.color565(200, 140, 255), fg, NULL);
    drawGauge(margin + cw + gap, 44 + ch + gap, cw, ch, "磁盘", disk, tft.color565(255, 200, 70), fg, NULL);
}

// ================= 按键 =================
void handleButtons() {
    if (digitalRead(BTN_K1) == LOW) {
        delay(50);
        if (digitalRead(BTN_K1) == LOW) {
            if (pending > 0) { approve(); delay(200); }
            else screen = 1 - screen;
            while (digitalRead(BTN_K1) == LOW) delay(10);
        }
    }
    if (digitalRead(BTN_K2) == LOW) {
        delay(50);
        if (digitalRead(BTN_K2) == LOW) { screen = 1 - screen; while (digitalRead(BTN_K2) == LOW) delay(10); }
    }
    if (digitalRead(BTN_K3) == LOW) {
        delay(50);
        if (digitalRead(BTN_K3) == LOW) { fetchStatus(); while (digitalRead(BTN_K3) == LOW) delay(10); }
    }
    if (digitalRead(BTN_K4) == LOW) {
        delay(50);
        if (digitalRead(BTN_K4) == LOW) {
            backlight = !backlight;
            digitalWrite(TFT_BLK, backlight ? HIGH : LOW);
            while (digitalRead(BTN_K4) == LOW) delay(10);
        }
    }
}

// ================= 时间 =================
void updateClock() {
    struct tm ti;
    if (getLocalTime(&ti, 200)) {
        strftime(clockStr, sizeof(clockStr), "%H:%M", &ti);
    } else if (doc["ts"]) {           // 桥时间兜底
        time_t t = doc["ts"] | 0;
        t += 8 * 3600;                // UTC+8
        struct tm* p = gmtime(&t);
        snprintf(clockStr, sizeof(clockStr), "%02d:%02d", p->tm_hour, p->tm_min);
    }
}

// ================= 主流程 =================
void setup() {
    Serial.begin(115200);
    pinMode(TFT_BLK, OUTPUT);
    digitalWrite(TFT_BLK, HIGH);
    SPI.begin(TFT_SCK, -1, TFT_MOSI, -1);      // 自定义引脚硬件 SPI
    tft.init(240, 240);
    tft.setRotation(0);
    tft.fillScreen(C_OFF);

    pinMode(BTN_K1, INPUT_PULLUP);
    pinMode(BTN_K2, INPUT_PULLUP);
    pinMode(BTN_K3, INPUT_PULLUP);
    pinMode(BTN_K4, INPUT_PULLUP);

    drawStr(10, 100, "连接 WiFi...", 0xFFFF);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(200);
    if (WiFi.status() == WL_CONNECTED) {
        configTime(8 * 3600, 0, "pool.ntp.org", "ntp.aliyun.com");
        drawStr(10, 120, "已连接", 0xFFFF);
    } else {
        drawStr(10, 120, "WiFi 失败", tft.color565(255, 80, 80));
    }
    delay(800);
}

void loop() {
    if (millis() - lastPoll >= POLL_MS) {
        lastPoll = millis();
        fetchStatus();
        updateClock();
    }
    handleButtons();
    // 动画节拍重绘
    if (millis() - lastAnim >= ANIM_MS) {
        lastAnim = millis();
        if (screen == 0) drawPetScreen();
        else drawDeviceScreen();
    }
    // WiFi 断线重连
    if (WiFi.status() != WL_CONNECTED && millis() - lastPoll > 15000) {
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASS);
    }
}
