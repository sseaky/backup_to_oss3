"""备份服务层：编排“状态采集 -> 打包 -> 多节点上传 -> 保留清理 -> 通知”主流程。

入口层（main.py）只负责调度，具体业务逻辑集中在此，便于单独测试与复用。
"""

import datetime
import os

from libs.net import get_default_private_ip, get_hostname, get_public_ip, human_size
from modules.archive import Archiver
from modules.notify import FeishuNotifier
from modules.oss import OssClient, pick_available
from modules.status import StatusCollector


class BackupService:
    """备份主流程服务。依赖通过构造函数注入。"""

    def __init__(self, cfg, logger=None, dry_run=False):
        self.cfg = cfg
        self.logger = logger
        self.dry_run = dry_run
        self.archiver = Archiver(logger=logger)
        self.status = StatusCollector(logger=logger)
        self.notifier = FeishuNotifier(
            cfg.FEISHU_WEBHOOK, cfg.FEISHU_SEC, logger=logger
        )

    def remote_dir(self):
        """根据配置生成远程目录名：<client_name>[_<public_ip>][_<private_ip>]。"""
        parts = [self.cfg.CLIENT_NAME or get_hostname()]
        if self.cfg.CLIENT_NAME_WITH_PUBLIC_IP:
            ip = get_public_ip()
            if ip:
                parts.append(ip)
        if self.cfg.CLIENT_NAME_WITH_PRIVATE_IP:
            ip = get_default_private_ip()
            if ip:
                parts.append(ip)
        return "_".join(parts)

    def _build_client(self, node):
        """按节点配置构建带超时的 OssClient。"""
        return OssClient(
            connect_timeout=self.cfg.OSS_CONNECT_TIMEOUT,
            read_timeout=self.cfg.OSS_READ_TIMEOUT,
            force_ipv4=self.cfg.OSS_FORCE_IPV4,
            logger=self.logger,
            **node,
        )

    def run(self):
        """执行完整备份流程，返回进程退出码（0 成功 / 1 存在失败节点）。"""
        cfg = self.cfg
        start_time = datetime.datetime.now()
        hostname = cfg.CLIENT_NAME or get_hostname()
        public_ip = get_public_ip()
        private_ip = get_default_private_ip()

        if self.logger:
            self.logger.info("--- 备份任务开始 --- 主机: %s 内网IP: %s 公网IP: %s",
                             hostname, private_ip, public_ip)

        status_file = None
        local_file = None
        oss_info_msg = []
        is_all_success = True

        try:
            # 1. 可选：采集系统状态
            if cfg.BACKUP_STAUS:
                status_file = self.status.collect(cfg.STATUS_COMMANDS, cfg.STATUS_FILE_PATH)

            # 2. 打包（状态文件随包上传）
            local_file = self.archiver.pack(
                source_path=cfg.SOURCE_PATH,
                source_exclude=cfg.SOURCE_EXCLUDE,
                stem=cfg.BACKUP_FILE_STEM,
                use_zip=cfg.USE_ZIP,
                zip_password=cfg.ZIP_PASSWORD,
                dereference=cfg.TAR_DEREFERENCE,
                extra_paths=[status_file] if status_file else None,
            )
            file_size = human_size(os.path.getsize(local_file))
            remote_dir = self.remote_dir()
            if self.logger:
                self.logger.info("归档生成成功: %s", local_file)

            # 3. 遍历上传至所有节点
            for node in cfg.oss_configs:
                server = node.get("server_name")
                try:
                    if self.dry_run:
                        if self.logger:
                            self.logger.info("[dry-run] 跳过上传至节点 %s/%s", server, remote_dir)
                        continue
                    client = self._build_client(node)
                    # 探活仅作提示，不作为上传前置条件（避免因权限受限而误判节点不可用）
                    if not client.check_connection() and self.logger:
                        self.logger.debug("节点 %s 探活未通过，仍尝试上传", server)
                    client.upload(remote_dir, local_file)
                    del_num = client.delete_old_objects(
                        remote_dir, cfg.DAYS_TO_RETAIN, cfg.MIN_COUNT_TO_KEEP
                    )
                    total, oldest = client.stats(remote_dir)
                    if self.logger:
                        self.logger.info(
                            "[%s] 远程总数: %s | 最早备份: %s | 本次清理: %s",
                            server, total, oldest, del_num,
                        )
                    oss_info_msg.append(
                        f"🟢 **{server}/{remote_dir}**\n"
                        f" └ 上传成功 (清理:{del_num})\n"
                        f" └ 远程总数: {total} 份\n"
                        f" └ 最早备份: {oldest}"
                    )
                except Exception as e:  # noqa: BLE001 - 单节点失败不影响其它节点
                    is_all_success = False
                    oss_info_msg.append(f"🔴 **{server}**: 失败 ({str(e)[:50]})")
                    if self.logger:
                        self.logger.error("节点 %s 处理失败: %s", server, e)

            # 4. 通知（dry-run 不发送，避免演练打扰）
            duration = (datetime.datetime.now() - start_time).seconds
            notice_content = (
                f"**服务器**: {hostname}\n"
                f"**公网IP**: {public_ip}\n"
                f"**内网IP**: {private_ip}\n"
                f"**任务耗时**: {duration}s\n"
                f"**备份归档**: {local_file} ({file_size})\n"
                f"**存储详情**:\n" + "\n".join(oss_info_msg)
            )
            if self.dry_run:
                if self.logger:
                    self.logger.info("[dry-run] 跳过飞书通知")
            else:
                self.notifier.send(
                    f"{hostname} 备份报告", notice_content, is_success=is_all_success
                )

            # 5. 全部成功后删除本地归档
            if is_all_success and not self.dry_run:
                self.archiver.remove(local_file)
                local_file = None

            return 0 if is_all_success else 1
        except Exception as e:
            if self.logger:
                self.logger.exception("备份任务异常中止")
            if not self.dry_run:
                self.notifier.send(
                    "备份任务异常中止", f"主机: {hostname}\n错误原因: {e}", is_success=False
                )
            return 1
        finally:
            if status_file and os.path.exists(status_file):
                os.remove(status_file)
            # 失败时保留本地归档，便于人工排查；成功路径已在上面删除
            if local_file and os.path.exists(local_file) and is_all_success and not self.dry_run:
                os.remove(local_file)


def list_and_download(cfg, logger=None, out_dir="."):
    """--list：列出第一个可用节点上的备份并交互式选择下载。返回退出码。"""
    remote_dir = BackupService(cfg, logger=logger).remote_dir()
    client = pick_available(cfg, logger=logger)
    if not client:
        print("[X] 没有可用的 OSS 节点")
        return 1

    objects = client.list_objects(remote_dir)
    if not objects:
        print(f"[*] {client.server_name}/{remote_dir} 下暂无备份")
        return 0

    from libs.net import human_size

    print(f"\n[{client.server_name}/{remote_dir}] 共 {len(objects)} 份备份:")
    for i, obj in enumerate(objects, 1):
        print(f"{i:>3}) {obj.object_name}  ({human_size(obj.size)})")

    while True:
        choice = input("\n输入序号下载，或 'q' 退出: ").strip()
        if choice.lower() == "q":
            print("已退出。")
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(objects):
            target = client.download(objects[int(choice) - 1].object_name, out_dir=out_dir)
            print(f"[OK] 已保存至 {target}")
            return 0
        print(f"[!] 请输入 1-{len(objects)} 之间的序号，或 'q' 退出")


def download_object(cfg, object_name, logger=None, out_dir="."):
    """--download：直接从第一个可用节点下载指定对象。返回退出码。"""
    client = pick_available(cfg, logger=logger)
    if not client:
        print("[X] 没有可用的 OSS 节点")
        return 1
    target = client.download(object_name, out_dir=out_dir)
    print(f"[OK] 已保存至 {target}")
    return 0
