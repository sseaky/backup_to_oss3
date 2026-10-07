"""系统状态采集模块：备份前执行诊断命令并写入状态文件，随备份一起上传。"""

import os
import subprocess


class StatusCollector:
    """采集系统运行状态。可独立初始化与测试（collector = StatusCollector()）。"""

    def __init__(self, logger=None):
        self.logger = logger

    def _run(self, cmd):
        """执行 shell 命令并返回标准输出（失败时返回错误信息，不中断备份）。"""
        try:
            return subprocess.getoutput(cmd)
        except Exception as e:  # noqa: BLE001 - 状态采集失败不应影响主流程
            if self.logger:
                self.logger.warning("状态命令执行失败: %s (%s)", cmd, e)
            return f"<command failed: {e}>"

    def collect(self, commands, status_file_path):
        """把诊断命令输出写入 status_file_path。

        命令完全由 config.STATUS_COMMANDS 驱动，不再硬编码额外命令。

        :param commands:          config.STATUS_COMMANDS
        :param status_file_path:  状态文件输出路径
        :return:                  状态文件路径
        """
        import datetime

        with open(status_file_path, "w") as f:
            f.write(f"Backup Task Start: {datetime.datetime.now()}\n")
            for cmd in commands:
                f.write(f"\n{'=' * 20} {cmd} {'=' * 20}\n")
                f.write(self._run(cmd) + "\n")
        if self.logger:
            self.logger.debug("系统状态已写入 %s", status_file_path)
        return status_file_path
