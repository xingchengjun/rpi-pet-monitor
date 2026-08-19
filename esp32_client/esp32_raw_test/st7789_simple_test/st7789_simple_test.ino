/*
 * st7789_simple_test.ino — 最简 ST7789 测试（纯 SPI，无第三方库）
 *
 * 引脚：
 *   SCK=GPIO4   SDA(MOSI)=GPIO3   RES=GPIO2   DC=GPIO1   BLK=GPIO0
 *   VCC=3V3  GND=GND  CS=无
 * 串口 115200 打印进度；屏幕循环刷 红/绿/蓝/白。
 */
#include <SPI.h>

#define PIN_SCK 4
#define PIN_MOSI 3
#define PIN_RES 2
#define PIN_DC 1
#define PIN_BLK 0

SPIClass* spi = nullptr;

void cmd(uint8_t c) { digitalWrite(PIN_DC, LOW); spi->transfer(c); }
void dat(uint8_t d) { digitalWrite(PIN_DC, HIGH); spi->transfer(d); }

void fill(uint16_t color) {
    cmd(0x2A); dat(0); dat(0); dat(0); dat(239);
    cmd(0x2B); dat(0); dat(0); dat(0); dat(239);
    cmd(0x2C);
    digitalWrite(PIN_DC, HIGH);
    uint8_t hi = color >> 8, lo = color & 0xFF;
    uint8_t buf[1024];
    for (int i = 0; i < 512; i++) { buf[i * 2] = hi; buf[i * 2 + 1] = lo; }
    for (int n = 0; n < 240 * 240 * 2; n += sizeof(buf)) {
        spi->transfer(buf, sizeof(buf));
    }
    delay(30);
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_BLK, OUTPUT); digitalWrite(PIN_BLK, HIGH);
    pinMode(PIN_DC, OUTPUT);
    pinMode(PIN_RES, OUTPUT);

    spi = &SPI;
    spi->begin(PIN_SCK, -1, PIN_MOSI, -1);
    spi->setFrequency(8000000);
    spi->setDataMode(SPI_MODE0);

    digitalWrite(PIN_RES, LOW); delay(100);
    digitalWrite(PIN_RES, HIGH); delay(100);

    cmd(0x01); delay(120);      // SWRESET
    cmd(0x11); delay(120);      // SLPOUT
    cmd(0x3A); dat(0x55);       // COLMOD 16bit
    cmd(0x36); dat(0x00);       // MADCTL
    cmd(0x21);                  // INVON
    cmd(0x29); delay(20);       // DISPON

    Serial.println("SIMPLE init done");
}

void loop() {
    fill(0xF800); Serial.println("RED");
    delay(800);
    fill(0x07E0); Serial.println("GREEN");
    delay(800);
    fill(0x001F); Serial.println("BLUE");
    delay(800);
    fill(0xFFFF); Serial.println("WHITE");
    delay(800);
}
