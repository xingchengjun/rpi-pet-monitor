# -*- coding: utf-8 -*-
"""
deploy_pi.py — 通过 SSH 远程配置树莓派（paramiko）。
用法：python deploy_pi.py [host] [user] [password]
凭据也可用环境变量 PI_HOST / PI_USER / PI_PASS。
步骤：系统信息 -> SPI 检查/启用 -> 装依赖 -> 拷贝程序 -> 导入/网络自检
     -> 屏幕闪测 -> 注册 systemd 自启。
"""

import os
import sys

import paramiko

HOST = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PI_HOST", "192.168.3.16")
USER = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PI_USER", "wxc")
PASS = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("PI_PASS", "")
SRC = os.path.dirname(os.path.abspath(__file__))

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())


def run(cmd, sudo=False, timeout=600):
    if sudo:
        esc = cmd.replace("'", "'\\''")
        cmd = "echo '%s' | sudo -S -p '' bash -c '%s'" % (PASS, esc)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def copy_pi_client(remote_root):
    """SFTP 递归拷贝 pi_client/ -> remote_root。返回拷贝文件数。"""
    sftp = client.open_sftp()
    count = [0]

    def put_dir(local, remote):
        try:
            sftp.mkdir(remote)
        except IOError:
            pass
        for name in sorted(os.listdir(local)):
            lp = os.path.join(local, name)
            rp = remote + "/" + name
            if os.path.isdir(lp):
                put_dir(lp, rp)
            else:
                sftp.put(lp, rp)
                count[0] += 1
                print("  put ~/%s" % rp.replace(remote_root, ""))

    put_dir(os.path.join(SRC, "pi_client"), remote_root)
    sftp.close()
    return count[0]


def main():
    print("==> 连接 %s as %s" % (HOST, USER))
    client.connect(HOST, username=USER, password=PASS, timeout=10)

    rc, out, err = run("whoami; uname -m; . /etc/os-release && echo $PRETTY_NAME; python3 --version")
    print(out.strip())

    sftp = client.open_sftp()
    pi_home = sftp.normalize(".")
    sftp.close()
    print("Pi home:", pi_home)

    # ---- SPI 检查/启用 ----
    rc, out, _ = run("ls /dev/spidev0.0 2>/dev/null && echo SPI_OK || echo SPI_MISSING")
    spi_ok = "SPI_OK" in out
    print("SPI:", "已启用" if spi_ok else "未启用")
    needs_reboot = False
    if not spi_ok:
        rc, cfg, _ = run("test -f /boot/firmware/config.txt && echo FIRMWARE || echo BOOT")
        cfg_path = "/boot/firmware/config.txt" if "FIRMWARE" in cfg else "/boot/config.txt"
        rc, out, err = run("grep -q '^dtparam=spi=on' %s && echo HAS || echo ADD" % cfg_path)
        if "HAS" not in out:
            run("printf '\\ndtparam=spi=on\\n' | sudo tee -a %s" % cfg_path, sudo=True)
            print("已写入 %s（需重启生效）" % cfg_path)
            needs_reboot = True

    # ---- 装依赖 ----
    print("==> apt 安装依赖（可能几分钟）")
    rc, out, err = run(
        "DEBIAN_FRONTEND=noninteractive apt-get update -y && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y "
        "python3-pil python3-spidev python3-gpiozero python3-luma.lcd",
        sudo=True, timeout=1200)
    print("apt rc=%d" % rc)
    if rc != 0:
        print("apt 输出尾部:\n", (out + err)[-2000:])

    # ---- 拷贝程序 ----
    print("==> 拷贝 pi_client -> %s/pet" % pi_home)
    remote_root = pi_home + "/pet"
    run("mkdir -p %s" % remote_root)
    n = copy_pi_client(remote_root)
    print("已拷贝 %d 个文件" % n)

    # pet.service 用户/路径改成当前用户
    run("sed -i 's|/home/pi/pet|%s|g; s|User=pi|User=%s|g' %s/pet.service"
        % (remote_root, USER, remote_root))

    # ---- 导入自检 ----
    rc, out, err = run("python3 -c \"import luma.lcd, gpiozero, PIL; print('IMPORTS_OK')\"")
    print("imports:", out.strip() or err.strip())

    # ---- 网络自检（桥） ----
    rc, out, err = run(
        "python3 -c \"import urllib.request;print(urllib.request.urlopen("
        "'http://192.168.3.8:8123/health', timeout=4).read().decode())\"")
    print("bridge health:", out.strip() or err.strip())

    # ---- 屏幕闪测（2 秒白屏，仅 SPI 无需重启时） ----
    if not needs_reboot:
        sftp = client.open_sftp()
        sftp.put(os.path.join(SRC, "_deploy_screen_test.py"), pi_home + "/_deploy_screen_test.py")
        sftp.close()
        rc, out, err = run("python3 %s/_deploy_screen_test.py" % pi_home, timeout=60)
        print("screen test:", out.strip(), err.strip())

    # ---- 注册自启（只 enable，不 start，先人工 test_lcd 确认） ----
    rc, out, err = run(
        "sudo cp %s/pet.service /etc/systemd/system/pet.service && "
        "sudo systemctl daemon-reload && sudo systemctl enable pet" % remote_root,
        sudo=True, timeout=60)
    print("systemd:", "OK" if rc == 0 else out + err)

    print("==> 部署完成")
    if needs_reboot:
        print(">>> SPI 刚启用，现在重启树莓派（10 秒后断连，约 1 分钟后恢复）")
        run("sudo shutdown -r now", sudo=True)
        print(">>> 重启后：ssh %s@%s 然后 cd ~/pet && python3 test_lcd.py" % (USER, HOST))
    else:
        print(">>> 屏幕已闪测通过。下一步在树莓派上：cd ~/pet && python3 test_lcd.py，然后 python3 pet.py")
    client.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            client.close()
        except Exception:
            pass
