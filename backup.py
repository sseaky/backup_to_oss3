#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""兼容旧入口：等价于 `python main.py`。

保留此文件以避免既有的 crontab / 部署脚本（引用 backup.py）失效。
新项目请直接使用 main.py。
"""

import sys

from main import main

if __name__ == "__main__":
    sys.exit(main())
