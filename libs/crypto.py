"""加解密工具：基于 Fernet 对称加密，用于保护配置中的 OSS AK/SK。

可单独测试：encrypto/decrypto 均为纯函数，不依赖全局上下文。
"""

from cryptography.fernet import Fernet


def encrypto(string, key):
    """加密字符串并打印结果（key 为空时自动生成）。

    :param string: 待加密明文
    :param key:    Fernet key（bytes 或 str）；为空时随机生成
    :return:       密文（str）
    """
    key = key.encode() if isinstance(key, str) else (key or Fernet.generate_key())
    cipher_suite = Fernet(key)
    encrypted_text = cipher_suite.encrypt(string.strip().encode())
    print(
        f"text: {string}, key: {key.decode()}, encrypted_text: {encrypted_text.decode()}"
    )
    return encrypted_text.decode()


def decrypto(string, key):
    """解密密文，返回明文（str）。key 错误时由底层抛出异常，由调用方包装为 ConfigError。"""
    cipher_suite = Fernet(key.encode() if isinstance(key, str) else key)
    return cipher_suite.decrypt(string.encode()).decode()
