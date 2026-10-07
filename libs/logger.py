"""日志工具：控制台实时输出 + 本地文件滚动持久化，四级分级。

每条日志携带时间戳、级别、模块名与业务上下文。
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LEVELS = {"DEBUG", "INFO", "WARNING", "WARN", "ERROR"}


def setup_logger(name="backup", log_dir=None, level="INFO", debug=False, log_file="backup.log"):
    """构建并返回一个双端输出的 logger。

    :param name:      logger 名称（同时作为日志中的模块标识）
    :param log_dir:   日志文件目录；为 None 时仅输出到控制台
    :param level:     控制台日志级别（DEBUG/INFO/WARNING/ERROR）
    :param debug:     True 时强制控制台为 DEBUG
    :param log_file:  日志文件名
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    # 重复调用时先清理旧 handler，避免日志重复输出
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    console_level = logging.DEBUG if debug else getattr(logging, str(level).upper(), logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        # 文件始终记录最详细内容
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


def mask(secret, keep=4):
    """敏感信息脱敏：仅保留首尾各 keep 位，中间以 * 代替。"""
    if not secret:
        return ""
    secret = str(secret)
    if len(secret) <= keep * 2:
        return "*" * len(secret)
    return f"{secret[:keep]}{'*' * (len(secret) - keep * 2)}{secret[-keep:]}"
