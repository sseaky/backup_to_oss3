"""配置加载模块。

职责：
    1. 根据 --env 选择配置文件（config_{env}.py，回退 config.py）；
    2. 校验关键配置合法性，非法直接抛 ConfigError；
    3. 对标记 crypto 的 OSS 节点解密 url/AK/SK；
    4. 提供脱敏后的配置摘要用于启动打印。
"""

import importlib
import os

from libs.crypto import decrypto
from libs.exceptions import ConfigError
from libs.logger import mask

# 各配置项缺省值（config.py 未定义时生效，保证向后兼容）
_DEFAULTS = {
    "TAR_DEREFERENCE": True,
    "USE_ZIP": True,
    "ZIP_PASSWORD": None,
    "BACKUP_FILE_STEM": "autobackup",
    "DAYS_TO_RETAIN": 60,
    "MIN_COUNT_TO_KEEP": 2,
    "CLIENT_NAME": "",
    "CLIENT_NAME_WITH_PUBLIC_IP": False,
    "CLIENT_NAME_WITH_PRIVATE_IP": False,
    "BACKUP_STAUS": True,
    "STATUS_FILE_PATH": "/tmp/myState.txt",
    "STATUS_COMMANDS": [],
    "SOURCE_PATH": [],
    "SOURCE_EXCLUDE": [],
    "OSS_CONFIGS": [],
    "SKEY": "",
    "FEISHU_WEBHOOK": "",
    "FEISHU_SEC": "",
    "OSS_CONNECT_TIMEOUT": 5,
    "OSS_READ_TIMEOUT": 15,
    "OSS_FORCE_IPV4": True,
    "OUTPUT_DIR": "output",
}


class Config:
    """配置容器：把 config 模块的字段展开为属性，并持有解密后的 OSS 节点列表。"""

    def __init__(self, raw, env="prod", decrypt=True):
        self.env = env
        for key, default in _DEFAULTS.items():
            setattr(self, key, getattr(raw, key, default))
        self.oss_configs = _load_oss_configs(self, decrypt=decrypt)

    def summary(self):
        """返回脱敏后的配置摘要（用于启动打印，禁止泄露密钥明文）。"""
        nodes = []
        for cfg in self.oss_configs:
            nodes.append(
                {
                    "server_name": cfg.get("server_name"),
                    "url": cfg.get("url"),
                    "bucket": cfg.get("bucket_name"),
                    "access_key": mask(cfg.get("access_key")),
                }
            )
        return {
            "env": self.env,
            "client_name": self.CLIENT_NAME or "<hostname>",
            "days_to_retain": self.DAYS_TO_RETAIN,
            "min_count_to_keep": self.MIN_COUNT_TO_KEEP,
            "oss_nodes": nodes,
        }


def _load_oss_configs(cfg, decrypt=True):
    """解密并校验 OSS 节点配置。decrypt=False 时仅做浅拷贝（供 --decrypto 预览用）。"""
    if not cfg.OSS_CONFIGS:
        raise ConfigError("OSS_CONFIGS 为空，请至少配置一个存储节点")

    resolved = []
    for node in cfg.OSS_CONFIGS:
        item = dict(node)
        if decrypt and item.get("crypto"):
            if not cfg.SKEY:
                raise ConfigError(f"节点 {item.get('server_name')} 开启了 crypto 但未配置 SKEY")
            try:
                for key in ("url", "access_key", "secret_key"):
                    item[key] = decrypto(item[key], cfg.SKEY)
            except Exception as e:
                raise ConfigError(
                    f"节点 {item.get('server_name')} 解密失败，请检查 SKEY: {e}"
                ) from e
        if decrypt:
            for required in ("url", "access_key", "secret_key", "bucket_name"):
                if not item.get(required):
                    raise ConfigError(
                        f"节点 {item.get('server_name')} 缺少必填项: {required}"
                    )
        resolved.append(item)
    return resolved


def load(env=None, decrypt=True):
    """加载配置。

    :param env:     环境名（dev/test/prod）；非 prod 时优先加载 config_{env}.py，
                    不存在则回退 config.py。为 None 时读取 BACKUP_ENV 或默认 prod。
    :param decrypt: 是否自动解密 OSS 节点（--decrypto 预览时传 False）。
    """
    env = env or os.getenv("BACKUP_ENV", "prod")
    module_name = f"config_{env}" if env != "prod" else "config"
    try:
        raw = importlib.import_module(module_name)
    except ModuleNotFoundError:
        if module_name != "config":
            raw = importlib.import_module("config")
        else:
            raise ConfigError("未找到 config.py，请先复制 config.example.py 并填写")
    return Config(raw, env=env, decrypt=decrypt)
