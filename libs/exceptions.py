"""统一异常定义。

所有业务模块抛出的异常均继承自 BackupError，禁止直接抛出底层原生异常，
便于入口层统一捕获、记录完整上下文。
"""


class BackupError(Exception):
    """备份业务异常基类。"""


class ConfigError(BackupError):
    """配置缺失、非法或解密失败。"""


class ArchiveError(BackupError):
    """本地打包/加密失败。"""


class OssError(BackupError):
    """OSS 连接、上传、下载或清理失败。"""


class NotifyError(BackupError):
    """通知发送失败。"""
