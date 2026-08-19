/*
 * st7789_raw_test2.ino — ST7789 裸 SPI 自检 v2（换默认 FSPI 引脚 + 背光闪烁）
 *
 * 与 v1 的区别：
 *   - SCK/MOSI 用 ESP32-C3 默认 FSPI：SCK=GPIO6, MOSI=GPIO7（不走 GPIO 矩阵映射）
 *   - SS 给真实引脚 GPIO8（某些核心版本 SS=-1 会让 SPI 不工作）
 *   - 背光每 1 秒翻转一次（能看到闪烁=程序在跑）
 *
 * 接线（按此改线测试）：
 *   SCK -> GPIO6   MOSI(SDA) -> GPIO7   DC -> GPIO3   RES -> GPIO2
 *   BLK -> GPIO10   VCC -> 3V3   GND -> GND
 */
#include <SPI.h>

#define PIN_SCK 6
#define PIN_MOSI 7
#define PIN_DC 3
#define PIN_RES 2
#define PIN_BLK 10
#define PIN_SS 8

SPIClass* spi = nullptr;
bool blkState = true;

void cmd(uint8_t c) { digitalWrite(PIN_DC, LOW); spi->transfer(c); }
void dat(uint8_t d) { digitalWrite(PIN_DC, HIGH); spi->transfer(d); }

void fill(uint16_t color) {
    cmd(0x2A); dat(0); dat(0); dat(0); dat(239);
    cmd(0x2B); dat(0); dat(0); dat(0); dat(239);
    cmd(0x2C);
    digitalWrite(PIN_DC, HIGH);
    uint8_t hi = color >> 8, lo = color & 0xFF;
    for (uint32_t i = 0; i < 240UL * 240; i++) { spi->transfer(hi); spi->transfer(lo); }
    delay(30);
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_BLK, OUTPUT); digitalWrite(PIN_BLK, HIGH);
    pinMode(PIN_DC, OUTPUT);
    pinMode(PIN_RES, OUTPUT);
    pinMode(PIN_SS, OUTPUT); digitalWrite(PIN_SS, LOW);   // 片选常低

    spi = &SPI;
    spi->begin(PIN_SCK, -1, PIN_MOSI, PIN_SS);
    spi->setFrequency(8000000);
    spi->setDataMode(SPI_MODE0);

    digitalWrite(PIN_RES, LOW); delay(120);
    digitalWrite(PIN_RES, HIGH); delay(120);

    cmd(0x01); delay(120);
    cmd(0x11); delay(120);
    cmd(0x3A); dat(0x55);
    cmd(0x36); dat(0x00);
    cmd(0x21);
    cmd(0x29); delay(20);

    Serial.println("RAW2: init done");
}

void loop() {
    fill(0xF800); Serial.println("RED"); delay(800);
    fill(0x07E0); Serial.println("GREEN"); delay(800);
    fill(0x001F); Serial.println("BLUE"); delay(800);
    fill(0xFFFF); Serial.println("WHITE"); delay(800);
    // 背光翻转，肉眼确认程序在跑
    blkState = !blkState;
    digitalWrite(PIN_BLK, blkState ? HIGH : LOW);
}
