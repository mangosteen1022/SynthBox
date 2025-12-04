import os
import platform
import subprocess
import ctypes
import sys
import logging
from v5.core.utils import get_cert_path

log = logging.getLogger("SynthBox")
# mitmproxy-ca-cert.pem


def is_admin():
    """检查当前脚本是否以管理员/root权限运行。"""
    try:
        # For Unix/Linux/macOS
        return os.getuid() == 0
    except AttributeError:
        # For Windows
        return ctypes.windll.shell32.IsUserAnAdmin() != 0


def is_cert_installed_windows():
    """在Windows上检查证书是否已安装。"""
    # certutil 会用证书的 'Subject' 和其他字段来查找，我们可以直接查找 mitmproxy
    command = 'certutil -store "Root" mitmproxy'
    try:
        # 使用 CREATE_NO_WINDOW 标志来隐藏弹出的命令行窗口
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=False, startupinfo=startupinfo
        )
        # 如果输出中包含 mitmproxy 相关信息并且命令成功，则认为已安装
        return "mitmproxy" in result.stdout and result.returncode == 0
    except Exception:
        return False


def is_cert_installed_macos():
    """在macOS上检查证书是否已安装。"""
    command = 'security find-certificate -a -c "mitmproxy" -Z /Library/Keychains/System.keychain'
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        # 如果命令成功且有输出 (找到了证书的哈希值)，则认为已安装
        return result.returncode == 0 and "SHA-1 hash" in result.stdout
    except Exception:
        return False


def is_cert_installed_linux():
    """在Linux上检查证书是否已安装。"""
    # 间接但可靠的方法：检查目标文件是否存在
    if os.path.exists("/etc/debian_version"):
        cert_dest = "/usr/local/share/ca-certificates/mitmproxy-ca-cert.crt"
    elif os.path.exists("/etc/redhat-release"):
        cert_dest = "/etc/pki/ca-trust/source/anchors/mitmproxy-ca-cert.crt"
    else:
        return False  # 不支持的发行版
    return os.path.exists(cert_dest)


def check_cert_is_installed():
    system = platform.system()

    # 2. 检查证书是否已安装
    is_installed = False
    if system == "Windows":
        is_installed = is_cert_installed_windows()
    elif system == "Darwin":
        is_installed = is_cert_installed_macos()
    elif system == "Linux":
        is_installed = is_cert_installed_linux()
    if is_installed:
        return True
    return False


def cert_installer():
    """主安装逻辑。"""
    # 1. 确定操作系统
    if check_cert_is_installed():
        log.info("证书已安装!重新覆盖安装!")

    # 3. 如果未安装，则执行安装流程
    cert_path = get_cert_path("mitmproxy-ca-cert.pem")
    if not cert_path:
        return False

    if not is_admin():
        print("❌ 权限不足。此操作需要管理员权限来安装根证书。")
        # 如果是被打包的程序，这里可以提示用户右键以管理员身份运行
        return False

    system = platform.system()
    if system == "Windows":
        command = f'certutil -addstore -f "Root" "{cert_path}"'
        subprocess.run(command, shell=True)
    elif system == "Darwin":
        command = f'sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "{cert_path}"'
        subprocess.run(command, shell=True)
    elif system == "Linux":
        if os.path.exists("/etc/debian_version"):
            cert_dest = "/usr/local/share/ca-certificates/mitmproxy-ca-cert.crt"
            update_command = "sudo update-ca-certificates"
        else:  # redhat-based
            cert_dest = "/etc/pki/ca-trust/source/anchors/mitmproxy-ca-cert.crt"
            update_command = "sudo update-ca-trust extract"
        subprocess.run(f'sudo cp "{cert_path}" "{cert_dest}"', shell=True)
        subprocess.run(update_command, shell=True)

    return True


if __name__ == "__main__":
    print("--- Mitmproxy 根证书自动安装工具 ---")
    cert_installer()
    # 在打包成exe后，让窗口保持几秒钟，方便用户看到信息
    if getattr(sys, "frozen", False):
        import time

        print("\n窗口将在10秒后自动关闭...")
        time.sleep(10)
