# 🚀 Multi-Cloud Server Backup

<img src="https://img.shields.io/badge/python-3.8+-blue.svg" width="86">
<img src="https://img.shields.io/badge/license-MIT-green.svg" width="78">
<img src="https://img.shields.io/badge/platform-linux-lightgrey.svg" width="94">

面向 Linux 服务器的自动化全量备份方案：**系统状态快照 → tar 打包 → ZIP 加密 → 多云 OSS(MinIO/S3 兼容) 同步上传 → 保留策略清理 → 飞书通知**。

- **深度系统快照**：备份前自动执行 `df/free/ip/docker/systemctl` 等命令，把系统即时状态与文件一起打包。
- **灵活归档**：多路径备份，支持 `tar --exclude` 排除规则与符号链接解析（`-h`）。
- **安全**：ZIP 二级密码加密；OSS 的 AK/SK 支持 Fernet 密文存储，配置文件泄露不等于权限丢失。
- **多云同步**：一次备份推送到多个 S3 兼容节点。
- **智能清理**：基于「保留天数 + 最少份数」双阈值清理，云端不溢出。
- **可恢复**：`--list` 交互式列出远端备份、`--download` 直接下载。
- **可观测**：飞书卡片报告（主机/内外网 IP/耗时/远程总数/最早备份）。
- **分层模块化**：入口、工具、业务模块解耦，可单独测试。

---

## 📂 项目结构（分层模块化）

```
backup_to_oss3/
├── main.py                # 唯一入口：参数解析、配置加载、日志初始化、业务调度
├── backup.py              # 兼容旧入口（等价 main.py，供既有 crontab 使用）
├── config.py              # 配置层（用户维护，已被 .gitignore 忽略）
├── config.example.py      # 配置模板
├── libs/                  # 公共工具层（与业务无关，可单独测试）
│   ├── crypto.py          #   Fernet 加解密
│   ├── net.py             #   主机名/公私有 IP/文件大小格式化/force_ipv4
│   ├── logger.py          #   双端日志（控制台 + 滚动文件）与脱敏
│   └── exceptions.py      #   统一异常定义
└── modules/               # 业务模块层（依赖注入，可单独测试）
    ├── config_loader.py   #   配置加载、校验、解密、脱敏摘要
    ├── config_tools.py    #   --crypto / --decrypto 工具
    ├── archive.py         #   打包归档（tar + zip 加密）
    ├── status.py          #   系统状态采集
    ├── oss.py             #   OSS 客户端：上传/列举/下载/清理/统计
    ├── notify.py          #   飞书通知
    └── backup_service.py  #   服务层：编排完整备份流程
```

> `bak/` 目录存放已废弃/被取代的旧文件（如旧的 `tool.py`/`notice.py` 兼容层、陈旧测试脚本），已被 `.gitignore` 忽略，不参与提交。

---

## 🛠️ 环境要求与依赖

- Linux（脚本依赖 `tar`、`zip` 命令）
- Python 3.8+

```bash
apt install -y tar zip
pip install requests minio cryptography
```

---

## ⚡ 快速开始

```bash
cp config.example.py config.py
vim config.py          # 至少配置 SOURCE_PATH、OSS_CONFIGS、SKEY
python3 main.py --dry-run    # 演练：只打包，不上传
python3 main.py              # 正式备份并上传
```

---

## 🔧 配置详解（config.py）

### 1. 打包设置
| 配置项 | 说明 |
| :--- | :--- |
| `TAR_DEREFERENCE` | 是否解析符号链接（`tar -h`），备份目录含软链时设为 `True` |
| `USE_ZIP` | 是否在 tar 基础上再做 ZIP 加密 |
| `ZIP_PASSWORD` | ZIP 解压密码 |
| `BACKUP_FILE_STEM` | 备份文件名前缀，最终形如 `autobackup_20261007_012108.zip` |
| `DAYS_TO_RETAIN` | 远端备份保留天数（超过则进入清理候选） |
| `MIN_COUNT_TO_KEEP` | 无论是否过期，至少保留的份数（兜底，防止清空） |

### 2. 客户端标识（决定 bucket 中的目录名）
| 配置项 | 说明 |
| :--- | :--- |
| `CLIENT_NAME` | 目录名前缀；为空则取主机名。**建议显式设置**，如 `my-server` |
| `CLIENT_NAME_WITH_PUBLIC_IP` | 是否追加 `_<公网IP>`（家宽公网 IP 会变，慎用） |
| `CLIENT_NAME_WITH_PRIVATE_IP` | 是否追加 `_<内网IP>` |

最终远程目录：`<CLIENT_NAME 或 hostname>[_<公网IP>][_<内网IP>]`。

### 3. 系统状态收集
| 配置项 | 说明 |
| :--- | :--- |
| `BACKUP_STAUS` | 是否在备份前采集系统状态 |
| `STATUS_FILE_PATH` | 状态文件路径（采集后随备份一起打包） |
| `STATUS_COMMANDS` | 采集命令列表（完全由配置驱动，不再硬编码） |

推荐命令集（已内置在模板）覆盖：基础信息、资源/文件系统、**磁盘分区（`lsblk`/`blkid`/`fdisk -l`，灾难恢复时重建 fstab 的关键）**、网络、服务/容器、定时任务。可按需增删。

### 4. 备份源
| 配置项 | 说明 |
| :--- | :--- |
| `SOURCE_PATH` | 要备份的文件/目录列表；不存在的路径会自动跳过 |
| `SOURCE_EXCLUDE` | `tar --exclude` 规则；匹配目录时 **末尾不要加 `/`** |

### 5. OSS 连接参数
| 配置项 | 默认 | 说明 |
| :--- | :--- | :--- |
| `OSS_CONNECT_TIMEOUT` | 5 | 建连超时（秒），避免死节点长时间阻塞 |
| `OSS_READ_TIMEOUT` | 15 | 读超时（秒） |
| `OSS_FORCE_IPV4` | True | **强制 IPv4 连接**（见下方说明） |
| `OUTPUT_DIR` | `output` | 日志输出根目录（日志写入 `OUTPUT_DIR/logs/backup.log`） |

#### 关于 `OSS_FORCE_IPV4` 的实现原理
- **实现位置**：`libs/net.py` 的 `force_ipv4()`：
  ```python
  import urllib3.util.connection as urllib3_connection
  urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
  ```
  这是 urllib3 的官方钩子，覆盖后**当前进程内所有 urllib3 连接**（minio、requests 均基于它）都只解析 IPv4。
- **生效时机**：`OssClient.__init__` 中当 `force_ipv4=True` 时调用；开关来自 `config.OSS_FORCE_IPV4`。
- **为什么需要**：部分 S3 网关为 IPv4/IPv6 双栈，其 **IPv6 前端鉴权异常**，会对任何请求（含 `GetBucketLocation`/`list_buckets`/`fput_object`）返回 `AccessDenied`，而 IPv4 前端正常。表现为"凭据明明没错却传不上去"，且时好时坏（取决于当时 DNS 选到哪个地址）。可用 `getent ahosts <域名>` 确认是否解析出 IPv6。

### 6. OSS 节点（`OSS_CONFIGS`）
每个节点一个 dict：
| 字段 | 说明 |
| :--- | :--- |
| `server_name` | 节点别名，仅用于日志/通知 |
| `url` | 节点地址，如 `https://oss-cn-hangzhou.aliyuncs.com` |
| `access_key` / `secret_key` | 密钥（明文，或开启 `crypto` 后的密文） |
| `bucket_name` | 目标 bucket |
| `crypto` | `True` 表示 AK/SK/URL 是密文，运行时会用 `SKEY` 解密 |

> 列表中的节点即实际生效的节点，**不要用 `[1:]`/`[:1]` 之类切片做调试过滤**（已踩坑）。
> `backup` 会上传至所有节点；`list`/`download` 使用第一个可连通节点。

### 7. 通知
| 配置项 | 说明 |
| :--- | :--- |
| `FEISHU_WEBHOOK` | 飞书机器人 Webhook；留空则跳过通知 |
| `FEISHU_SEC` | 预留（当前为无签名模式） |

---

## 🔐 凭据密文管理

`SKEY` 是 Fernet 对称密钥，用于加密/解密 `OSS_CONFIGS` 里的 URL/AK/SK。

### 生成一个 SKEY（若还没有）
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 如何「查看」现有密文对应的明文
```bash
python3 main.py --decrypto
```
会遍历 `OSS_CONFIGS`，对开启 `crypto` 的节点解密并打印明文（URL/AK/SK），用于核对密文与 `SKEY` 是否正确。
> ⚠️ 该命令会输出明文密钥，请在可信终端执行，勿留存输出。

### 如何「生成」密文（添加新服务器）
1. 确保 `config.py` 中 `SKEY` 已配置。
2. 运行交互式加密工具：
   ```bash
   python3 main.py --crypto
   # 按提示依次输入 URL、Access Key、Secret Key
   ```
3. 工具会分别打印 `URL/AK/SK` 三段密文，形如 `gAAAAAB...`。
4. 把三段密文填入 `OSS_CONFIGS` 新增节点，并设置 `"crypto": True`：
   ```python
   OSS_CONFIGS = [
       {
           "server_name": "new-node",
           "crypto": True,
           "url":        "gAAAAAB...",   # --crypto 输出的 URL 密文
           "access_key": "gAAAAAB...",   # --crypto 输出的 AK 密文
           "secret_key": "gAAAAAB...",   # --crypto 输出的 SK 密文
           "bucket_name": "your-bucket",
       },
   ]
   ```
5. 核对：
   ```bash
   python3 main.py --decrypto        # 预览明文确认无误
   python3 main.py --dry-run         # 演练打包
   python3 main.py                   # 正式上传（会同时写入所有节点）
   ```

> 若某节点使用明文密钥，把该节点 `crypto` 设为 `False` 即可（可与其他密文节点混用）。

---

## 🖥️ 命令行用法

| 参数 | 作用 |
| :--- | :--- |
| （无） / `--backup` | 打包并上传至所有可用节点，执行保留策略（默认行为） |
| `--list` | 列出远端备份（含大小）并交互式选择下载 |
| `--download <OBJECT>` | 直接下载指定远端对象到当前目录 |
| `--crypto` | 交互式加密 URL/AK/SK，输出可粘贴的密文 |
| `--decrypto` | 解密预览当前配置 |
| `--env <dev/test/prod>` | 选择环境配置（加载 `config_<env>.py`，缺省回退 `config.py`） |
| `--debug` | 开启调试日志 |
| `--log-level <LEVEL>` | 日志级别 `DEBUG/INFO/WARNING/ERROR`（默认 INFO） |
| `--dry-run` | 只演练，不实际上传与删除 |

示例：
```bash
python3 main.py                       # 备份并上传
python3 main.py --dry-run --debug     # 演练 + 详细日志
python3 main.py --list                # 交互式恢复
python3 main.py --download my-server_10.0.0.5/autobackup_20260101_012108.zip
```

---

## 🚀 部署与定时任务

### 部署
```bash
cd ~/git && git clone <repo> backup_to_oss3 && cd backup_to_oss3
pip install requests minio cryptography
cp config.example.py config.py && vim config.py
python3 main.py --dry-run
```

### 定时任务（crontab）
示例（每天 01:21 执行）：
```cron
21 1 * * * cd /backup && bash run.sh > /tmp/backup_to_oss3.log 2>&1
```
其中 `run.sh` 可先做数据库 dump 等前置动作，再调用备份：
```bash
# run.sh 最后一行
cd ~/git/backup_to_oss3 && python3 main.py
```

> 日志双端输出：控制台 + `OUTPUT_DIR/logs/backup.log`（滚动，单文件 5MB × 5）。
> 旧入口 `backup.py` 与 `main.py` 参数完全一致，既有 cron 无需改动。

---

## ♻️ 恢复流程

```bash
python3 main.py --list                 # 交互式选择要恢复的备份并下载
python3 main.py --download <对象名>    # 或直接下载
unzip -P <ZIP_PASSWORD> 文件名.zip     # 解压（ZIP 加密时）
tar -xzf 文件名.tar.gz                 # 若未加密
```

---

## 🧯 故障排查

| 现象 | 原因 / 处理 |
| :--- | :--- |
| `AccessDenied`（凭据看似正确） | 多为走了 **IPv6** 前端。确认 `OSS_FORCE_IPV4 = True`；或 `getent ahosts <域名>` 看是否解析出 IPv6 |
| 节点 `ConnectTimeout` | 该节点从本机不可达（网络/端口），属正常，会跳过并继续其它节点 |
| `配置错误: 节点 X 解密失败` | `SKEY` 与密文不匹配；用 `--decrypto` 核对 |
| `配置错误: 缺少必填项` | 节点缺 `url/access_key/secret_key/bucket_name` |
| `tar 打包失败` | tar 退出码非 0/1；查看日志中 stderr（退出码 1 是"文件变动"警告，可接受） |
| 本地残留 `.zip` | 说明有节点上传失败（脚本仅在全成功时删除本地归档），便于人工排查 |

---

## 🧩 模块说明（可单独测试）

- `libs/crypto.py`：`encrypto(string, key)` / `decrypto(string, key)` 纯函数。
- `libs/net.py`：`get_hostname/get_public_ip/get_default_private_ip/human_size/force_ipv4`。
- `modules/archive.py`：`Archiver().pack(...)` 打包；独立可测。
- `modules/status.py`：`StatusCollector().collect(commands, path)`。
- `modules/oss.py`：`OssClient(url, ak, sk, bucket, ...)`，方法 `check_connection/upload/list_objects/download/delete_old_objects/stats`。
- `modules/notify.py`：`FeishuNotifier(webhook).send(title, content, is_success)`。
- `modules/config_loader.py`：`load(env=None, decrypt=True)` 返回 `Config`。
- `modules/backup_service.py`：`BackupService(cfg).run()` 编排主流程。

所有模块通过构造函数注入依赖（如 `logger`），不依赖全局上下文，支持单独初始化与单元测试。

---

## ⚖️ 许可证

本项目基于 [MIT License](LICENSE) 协议开源。
