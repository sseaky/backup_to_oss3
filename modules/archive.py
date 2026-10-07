"""本地打包归档模块：tar 打包 + 可选 zip 密码加密。

可独立初始化与测试（archiver = Archiver()）。
"""

import datetime
import os
import subprocess

from libs.exceptions import ArchiveError


class Archiver:
    """负责把源路径打包为 tar.gz，并按需再加密为 zip。"""

    def __init__(self, logger=None):
        self.logger = logger

    def pack(
        self,
        source_path,
        source_exclude,
        stem="autobackup",
        use_zip=True,
        zip_password=None,
        dereference=False,
        extra_paths=None,
    ):
        """打包备份。

        :param source_path:    要备份的路径列表
        :param source_exclude: tar --exclude 规则列表
        :param stem:           文件名前缀
        :param use_zip:        是否在 tar 基础上再做 zip 加密
        :param zip_password:   zip 密码；为空则不加密码（仍返回 tar.gz）
        :param dereference:    是否跟随符号链接（tar -h）
        :param extra_paths:    额外附加进归档的文件（如状态文件）
        :return:               生成的归档文件名（.tar.gz 或 .zip）
        """
        now_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{stem}_{now_tag}"
        tar_name = f"{base_name}.tar.gz"

        cmd = ["tar", "-czf", tar_name]
        if dereference:
            cmd.append("-h")
        for exclude in source_exclude:
            cmd.append(f"--exclude={exclude}")

        paths = [p for p in list(source_path) + list(extra_paths or []) if os.path.exists(p)]
        if not paths:
            raise ArchiveError("没有找到任何有效的备份源路径")
        cmd.extend(paths)

        if self.logger:
            self.logger.debug("执行打包命令: %s", " ".join(cmd))

        process = subprocess.run(cmd, capture_output=True, text=True)
        # tar 返回 0 为成功，1 为警告（如文件在打包过程中消失），备份场景可接受
        if process.returncode not in (0, 1):
            raise ArchiveError(
                f"tar 打包失败 (退出码 {process.returncode}): {process.stderr or '未知错误'}"
            )
        if process.returncode == 1 and self.logger:
            self.logger.warning("tar 警告: 部分文件在打包过程中发生变动 (exit code 1)")

        if not (use_zip and zip_password):
            return tar_name

        zip_name = f"{base_name}.zip"
        zip_proc = subprocess.run(
            ["zip", "-P", zip_password, "-q", zip_name, tar_name],
            capture_output=True,
            text=True,
        )
        if zip_proc.returncode != 0:
            raise ArchiveError(f"zip 加密失败: {zip_proc.stderr or '未知错误'}")
        os.remove(tar_name)
        return zip_name

    @staticmethod
    def remove(file_path):
        """删除本地临时归档，文件不存在时忽略。"""
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
