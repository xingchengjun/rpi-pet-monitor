#!/usr/bin/env bash
# install.sh — 树莓派一键安装（在 pi_client/ 目录下运行：bash install.sh）
# 作用：启用 SPI、装依赖、拷贝程序到 ~/pet、注册 systemd 自启
set -e

echo "==> 启用 SPI 接口"
if ! grep -q "dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "dtparam=spi=on" /boot/config.txt 2>/dev/null; then
  if [ -f /boot/firmware/config.txt ]; then
    echo "dtparam=spi=on" | sudo tee -a /boot/firmware/config.txt >/dev/null
  else
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt >/dev/null
  fi
  echo "    已写入 config.txt（需要重启一次生效）"
fi

echo "==> 安装系统依赖"
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-pil python3-spidev python3-gpiozero python3-luma.lcd

echo "==> 拷贝程序到 ~/pet"
mkdir -p "$HOME/pet"
cp -r "$(dirname "$0")"/. "$HOME/pet/"

echo "==> 注册 systemd 自启"
sudo cp "$HOME/pet/pet.service" /etc/systemd/system/pet.service
sudo systemctl daemon-reload
sudo systemctl enable pet

echo ""
echo "======================================================"
echo " 安装完成！接下来："
echo " 1) 编辑 ~/pet/pet_config.json 确认 bridge_url / token"
echo " 2) sudo reboot   （首次启用 SPI 必须重启）"
echo " 3) 先自检： cd ~/pet && python3 test_lcd.py"
echo " 4) 正式跑： sudo systemctl start pet （或 python3 pet.py）"
echo "======================================================"
