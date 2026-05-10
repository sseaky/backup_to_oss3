#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
Author: Seaky
Date: 2024-12-22 15:12:28
LastEditTime: 2024-12-22 15:14:40
Description: 

"""

import re
import socket
import subprocess
from cryptography.fernet import Fernet
import requests

Pattern_IPv4 = (
    "(?P<ip>((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?))"
)


def encrypto(string, key):
    key = key.encode() if key else Fernet.generate_key()
    cipher_suite = Fernet(key)
    encrypted_text = cipher_suite.encrypt(string.strip().encode())
    print(
        f"text: {string}, key: {key.decode()}, encrypted_text: {encrypted_text.decode()}"
    )


def decrypto(string, key):
    cipher_suite = Fernet(key.encode())
    decrypted_text = cipher_suite.decrypt(string.encode()).decode()
    return decrypted_text


def strip_last_slash(string):
    return re.sub("/+$", "", string)


Pattern_IPv4 = (
    "(?P<ip>((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?))"
)


def get_hostname():
    hostname = socket.gethostname()
    return hostname


def get_default_private_ip():
    default_interface = subprocess.getoutput(
        "ip route | grep default | awk '{print $5}' | head -1"
    )
    output = subprocess.getoutput(
        f"ip addr show {default_interface} | grep 'inet ' | awk '{{print $2}}' | cut -d/ -f1"
    )
    m = re.search(Pattern_IPv4, output)
    ip_address = m[1] if m else ""
    return ip_address


def get_public_ip(timeout=3):
    user_agent = "curl"
    headers = {"User-Agent": user_agent}

    urls = [
        "http://icanhazip.com",
        "https://ifconfig.me",
        "http://myip.ipip.net",
        "http://ip.sb",
        "http://cip.cc",
        "http://ipinfo.io/?token=0bbdf73fa27d4a",
    ]

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                ip_pattern = re.compile(Pattern_IPv4)
                if match := ip_pattern.search(response.text):
                    return match[1]
            # else:
            #     print(f"访问 {url} 失败，状态码: {response.status_code}")
        except requests.RequestException as e:
            # print(f"访问 {url} 时出现异常: {e}")
            pass
