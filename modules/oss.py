"""OSS(MinIO/S3 兼容) 操作模块。

封装单节点的连接、探活、上传、列举、下载、保留策略清理与统计。
可独立初始化与测试：OssClient(url, ak, sk, bucket)。
"""

import datetime
import os

import urllib3
from minio import Minio
from urllib3 import PoolManager

from libs.exceptions import OssError
from libs.net import force_ipv4 as force_ipv4_global
from libs.net import get_file_size


class OssClient:
    """一个 OSS 节点的客户端封装（带连接超时控制，不自动重试）。"""

    def __init__(
        self,
        url,
        access_key,
        secret_key,
        bucket_name,
        server_name="",
        connect_timeout=5,
        read_timeout=15,
        force_ipv4=True,
        logger=None,
        **kwargs,
    ):
        """
        :param url:             节点地址，如 http(s)://host:port
        :param access_key:      AK（已解密）
        :param secret_key:      SK（已解密）
        :param bucket_name:     目标 bucket
        :param server_name:     节点别名，仅用于日志
        :param connect_timeout: 建连超时（秒）
        :param read_timeout:    读超时（秒）
        :param force_ipv4:      是否强制使用 IPv4 连接（规避部分网关 IPv6 前端鉴权异常）
        :param kwargs:          吸收多余配置项，保证配置向后兼容
        """
        self.logger = logger
        self.server_name = server_name
        self.bucket_name = bucket_name
        self.url = url

        if force_ipv4:
            force_ipv4_global()

        endpoint = url.replace("http://", "").replace("https://", "").rstrip("/")
        # 自定义连接池：设置建连/读超时且完全不重试，避免死节点长时间阻塞
        http_client = PoolManager(
            timeout=urllib3.Timeout(connect=connect_timeout, read=read_timeout),
            retries=urllib3.Retry(total=0, connect=0, read=0),
        )
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=url.startswith("https"),
            http_client=http_client,
        )
        self.is_connected = False

    def check_connection(self):
        """探活：检查目标 bucket 是否可访问。

        使用 bucket_exists（针对具体 bucket 的轻量探测），而非 list_buckets，
        避免因 AK 缺少“列出所有 bucket”权限而误判为不可用。
        失败不抛异常，返回 bool。
        """
        try:
            self.is_connected = bool(self.client.bucket_exists(self.bucket_name))
        except Exception as e:  # noqa: BLE001 - 探活失败交由调用方处理
            self.is_connected = False
            if self.logger:
                self.logger.warning("节点 %s 探活失败: %s", self.server_name, e)
        return self.is_connected

    def upload(self, remote_dir, local_file_path):
        """上传本地文件到 <bucket>/<remote_dir>/<文件名>。"""
        remote_dir = remote_dir.rstrip("/")
        object_name = f"{remote_dir}/{os.path.basename(local_file_path)}"
        try:
            result = self.client.fput_object(self.bucket_name, object_name, local_file_path)
        except Exception as e:
            raise OssError(f"上传失败 {object_name}: {e}") from e
        if self.logger:
            self.logger.info(
                "上传成功 [%s] %s (ETag: %s)", self.server_name, result.object_name, result.etag
            )
        return result

    def list_objects(self, remote_dir="/"):
        """列出 remote_dir 下所有对象，按最后修改时间升序（最早的在前）。"""
        remote_dir = remote_dir.rstrip("/")
        try:
            objects = list(
                self.client.list_objects(
                    self.bucket_name, prefix=f"{remote_dir}/", recursive=True
                )
            )
        except Exception as e:
            raise OssError(f"列举对象失败: {e}") from e
        objects.sort(key=lambda x: x.last_modified)
        return objects

    def download(self, object_name, out_dir="."):
        """下载远端对象到 out_dir（文件名取对象名最后一段），返回本地路径。"""
        file_name = os.path.basename(object_name)
        target = os.path.join(out_dir, file_name)
        try:
            self.client.fget_object(self.bucket_name, object_name, target)
        except Exception as e:
            raise OssError(f"下载失败 {object_name}: {e}") from e
        if self.logger:
            self.logger.info("下载完成: %s (%s)", target, get_file_size(target))
        return target

    def delete_old_objects(self, remote_dir, days_to_retain, min_count_to_keep):
        """保留策略：删除超过 days_to_retain 天的对象，但至少保留 min_count_to_keep 份。

        对象已按时间升序，从头处理即“先删最旧的”。返回删除数量。
        """
        objects = self.list_objects(remote_dir)
        now = datetime.datetime.now(datetime.timezone.utc)
        deleted = 0
        for obj in objects:
            if len(objects) - deleted <= min_count_to_keep:
                break
            if (now - obj.last_modified).days > days_to_retain:
                try:
                    self.client.remove_object(self.bucket_name, obj.object_name)
                except Exception as e:
                    raise OssError(f"删除失败 {obj.object_name}: {e}") from e
                deleted += 1
                if self.logger:
                    self.logger.info("已删除过期备份 [%s] %s", self.server_name, obj.object_name)
        return deleted

    def stats(self, remote_dir):
        """返回 (对象总数, 最早备份描述)。"""
        objects = self.list_objects(remote_dir)
        if not objects:
            return 0, "无数据"
        oldest_time = objects[0].last_modified
        days_ago = (datetime.datetime.now(datetime.timezone.utc) - oldest_time).days
        return len(objects), f"{days_ago} 天前 ({oldest_time.strftime('%Y-%m-%d')})"


def pick_available(cfg, logger=None):
    """遍历 config.oss_configs，返回第一个可连通的 OssClient；全部失败返回 None。"""
    for node in cfg.oss_configs:
        client = OssClient(
            connect_timeout=cfg.OSS_CONNECT_TIMEOUT,
            read_timeout=cfg.OSS_READ_TIMEOUT,
            force_ipv4=cfg.OSS_FORCE_IPV4,
            logger=logger,
            **node,
        )
        if client.check_connection():
            return client
    return None
