#!/bin/bash
# 树莓派一键安装脚本（需要 sudo 运行）
#   sudo bash install.sh
set -e

echo "==> 安装系统依赖"
sudo apt update
sudo apt install -y python3-pil python3-spidev python3-gpiozero python3-luma.lcd python3-luma.core

echo "==> 启用 SPI 接口（需要重启生效）"
if ! grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null; then
  echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
  echo "    已在 /boot/config.txt 追加 dtparam=spi=on，重启后 SPI 生效"
else
  echo "    SPI 已启用"
fi

echo "==> 可选：安装中文字体（显示中文台词，否则自动退英文）"
sudo apt install -y fonts-noto-cjk || true

echo
echo "安装完成！"
echo "  1) 先 reboot 一次，让 SPI 生效"
echo "  2) 运行测试:  python3 test_lcd.py"
echo "  3) 正式运行:  python3 main.py        （--mode preview 可先在电脑上预览）"
echo
echo "  如需开机自启，把下面一行加入 crontab："
echo "  @reboot cd $(pwd) && python3 main.py >/dev/null 2>&1 &"
