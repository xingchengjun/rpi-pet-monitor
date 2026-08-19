/*
 * st7789_espi_test.ino — TFT_eSPI 标准驱动测试（ST7789 240x240）
 *
 * 依赖：TFT_eSPI 库（Arduino 库管理器安装，作者 Bodmer）
 * 必须改库里的 User_Setup.h（见下方说明）——这是 TFT_eSPI 的配置方式。
 *
 * 若此测试出颜色 = 屏幕接线 OK，问题在我之前写的驱动代码；
 * 仍黑屏 = 屏幕硬件/CS 问题。
 */
#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();

void setup() {
    Serial.begin(115200);
    tft.init();
    tft.setRotation(0);
    Serial.println("TFT_eSPI init done");
}

void loop() {
    tft.fillScreen(TFT_RED);    Serial.println("RED");    delay(1000);
    tft.fillScreen(TFT_GREEN);  Serial.println("GREEN");  delay(1000);
    tft.fillScreen(TFT_BLUE);   Serial.println("BLUE");   delay(1000);
    tft.fillScreen(TFT_WHITE);  Serial.println("WHITE");  delay(1000);
}
