"""网络与主机信息工具：主机名、公/私网 IP、文件大小格式化。

均为无副作用纯函数，可单独测试（IP 相关函数依赖 Linux 命令，需在目标环境运行）。
"""

import os
import re
import socket
import subprocess

import requests

Pattern_IPv4 = (
    "(?P<ip>((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?))"
)


def get_hostname():
    """返回当前主机名。"""
    return socket.gethostname()


def get_default_private_ip():
    """返回默认路由所在网卡的私网 IPv4 地址，获取失败返回空串。"""
    default_interface = subprocess.getoutput(
        "ip route | grep default | awk '{print $5}' | head -1"
    )
    output = subprocess.getoutput(
        f"ip addr show {default_interface} | grep 'inet ' | awk '{{print $2}}' | cut -d/ -f1"
    )
    m = re.search(Pattern_IPv4, output)
    return m[1] if m else ""


def get_public_ip(timeout=3):
    """依次尝试多个公共 IP 查询服务，返回第一个解析到的公网 IPv4，失败返回 None。"""
    headers = {"User-Agent": "curl"}
    urls = [
        "http://icanhazip.com",
        "https://ifconfig.me",
        "http://myip.ipip.net",
        "http://ip.sb",
        "http://cip.cc",
        "http://ipinfo.io/?token=0bbdf73fa27d4a",
    ]
    ip_pattern = re.compile(Pattern_IPv4)
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                if match := ip_pattern.search(response.text):
                    return match[1]
        except requests.RequestException:
            # 单个服务不可用时静默跳过，尝试下一个
            pass
    return None


def human_size(size_bytes):
    """将字节数转换为人类易读的大小格式（如 12.34 MB）。"""
    try:
        size_bytes = float(size_bytes)
    except (TypeError, ValueError):
        return "未知大小"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_file_size(file_path):
    """获取本地文件的人类易读大小，读取失败返回“未知大小”。"""
    try:
        return human_size(os.path.getsize(file_path))
    except OSError:
        return "未知大小"


def force_ipv4():
    """强制 urllib3 使用 IPv4 解析并连接。

    部分 S3 网关为 IPv4/IPv6 双栈，其 IPv6 前端鉴权异常，会对请求返回
    AccessDenied，而 IPv4 前端正常。调用后对当前进程内所有 urllib3 连接生效。
    """
    import urllib3.util.connection as urllib3_connection

    urllib3_connection.allowed_gai_family = lambda: socket.AF_INET

