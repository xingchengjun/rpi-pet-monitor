/*
 * st7789_raw_test.ino — ST7789 裸 SPI 自检（不依赖 Adafruit 库）
 *
 * 作用：跳过所有库，直接驱动屏幕刷 红/绿/蓝/白。
 *   - 看到颜色循环 = 屏幕和接线正常，问题在 Adafruit 库的配置
 *   - 还是黑屏 = 接线/屏幕本身问题（查 SCK/SDA 对调、DC/RES、供电）
 *
 * 接线（与主固件一致）：
 *   SCK=GPIO5  MOSI=GPIO1  DC=GPIO3  RES=GPIO2  BLK=GPIO10（CS 无/接地）
 * 串口 115200 会打印进度。
 */
#include <SPI.h>

#define PIN_SCK 5
#define PIN_MOSI 1
#define PIN_DC 3
#define PIN_RES 2
#define PIN_BLK 10

SPIClass* spi = nullptr;

void cmd(uint8_t c) { digitalWrite(PIN_DC, LOW); spi->transfer(c); }
void dat(uint8_t d) { digitalWrite(PIN_DC, HIGH); spi->transfer(d); }

void fill(uint16_t color) {
    cmd(0x2A); dat(0); dat(0); dat(0); dat(239);   // 列 0..239
    cmd(0x2B); dat(0); dat(0); dat(0); dat(239);   // 行 0..239
    cmd(0x2C);                                     // RAMWR
    digitalWrite(PIN_DC, HIGH);
    uint8_t hi = color >> 8, lo = color & 0xFF;
    for (uint32_t i = 0; i < 240UL * 240; i++) { spi->transfer(hi); spi->transfer(lo); }
    delay(50);
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_BLK, OUTPUT); digitalWrite(PIN_BLK, HIGH);
    pinMode(PIN_DC, OUTPUT);
    pinMode(PIN_RES, OUTPUT);

    spi = &SPI;
    spi->begin(PIN_SCK, -1, PIN_MOSI, -1);   // sck, miso, mosi, ss
    spi->setFrequency(8000000);
    spi->setDataMode(SPI_MODE0);

    // 硬件复位
    digitalWrite(PIN_RES, LOW); delay(120);
    digitalWrite(PIN_RES, HIGH); delay(120);

    // ST7789 基础初始化
    cmd(0x01); delay(120);          // SWRESET
    cmd(0x11); delay(120);          // SLPOUT
    cmd(0x3A); dat(0x55);           // COLMOD 16bit
    cmd(0x36); dat(0x00);           // MADCTL
    cmd(0x21);                      // INVON（部分屏需要，颜色不对可去掉）
    cmd(0x29); delay(20);           // DISPON

    Serial.println("RAW TEST: init done, filling colors...");
}

void loop() {
    fill(0xF800); Serial.println("RED");
    delay(1000);
    fill(0x07E0); Serial.println("GREEN");
    delay(1000);
    fill(0x001F); Serial.println("BLUE");
    delay(1000);
    fill(0xFFFF); Serial.println("WHITE");
    delay(1000);
}
