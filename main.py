#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""项目唯一入口。

职责单一：参数解析、配置加载、日志初始化、业务调度。
具体业务逻辑位于 modules/，通用能力位于 libs/。
"""

import argparse
import os
import sys

from libs.exceptions import ConfigError
from libs.logger import setup_logger
from modules import backup_service, config_loader, config_tools


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Server backup to OSS (MinIO/S3 兼容)")
    parser.add_argument("--backup", action="store_true", help="执行打包并上传（默认行为）")
    parser.add_argument("--list", action="store_true", help="列出远端备份并交互式下载")
    parser.add_argument("--download", metavar="OBJECT_NAME", help="直接下载指定远端对象")
    parser.add_argument("--crypto", action="store_true", help="交互式加密 OSS 配置")
    parser.add_argument("--decrypto", action="store_true", help="解密预览当前配置")
    parser.add_argument("--env", default=None, help="环境名 dev/test/prod（默认 prod）")
    parser.add_argument("--debug", action="store_true", help="开启调试日志")
    parser.add_argument("--log-level", default="INFO", help="日志级别 DEBUG/INFO/WARNING/ERROR")
    parser.add_argument("--dry-run", action="store_true", help="只演练，不实际上传/删除")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # --crypto/--decrypto 需要原始密文，故不自动解密；其余场景自动解密并校验
    decrypt = not (args.crypto or args.decrypto)
    try:
        cfg = config_loader.load(env=args.env, decrypt=decrypt)
    except ConfigError as e:
        print(f"[X] 配置错误: {e}")
        return 2

    # 日志双端输出：控制台 + OUTPUT_DIR/logs 滚动文件
    logger = setup_logger(
        level=args.log_level, debug=args.debug, log_dir=os.path.join(cfg.OUTPUT_DIR, "logs")
    )
    logger.debug("生效配置: %s", cfg.summary())

    # 业务调度
    if args.crypto:
        config_tools.run_crypto_tool(cfg.SKEY)
        return 0
    if args.decrypto:
        config_tools.run_decrypto_preview(cfg)
        return 0
    if args.list:
        return backup_service.list_and_download(cfg, logger=logger)
    if args.download:
        return backup_service.download_object(cfg, args.download, logger=logger)

    return backup_service.BackupService(cfg, logger=logger, dry_run=args.dry_run).run()


if __name__ == "__main__":
    sys.exit(main())
