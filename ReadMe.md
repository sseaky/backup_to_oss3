# 🚀 Multi-Cloud Server Backup
<img src="https://img.shields.io/badge/python-3.6+-blue.svg" width="86" title="" crop="0,0,1,1" id="mo17c" class="ne-image">  
<img src="https://img.shields.io/badge/license-MIT-green.svg" width="78" title="" crop="0,0,1,1" id="Kipma" class="ne-image">  
<img src="https://img.shields.io/badge/platform-linux-lightgrey.svg" width="94" title="" crop="0,0,1,1" id="zIEWA" class="ne-image">

这是一个专为 Linux 服务器设计的自动化全量备份解决方案。支持系统状态深度快照、多路径打包、ZIP 密码加密、多云存储同步（MinIO/S3/OSS）以及交互式飞书卡片报告。

## 🌟 核心特性
+ **深度系统快照**：备份前自动执行 `df`, `free`, `docker ps`, `ip a`, `crontab` 等命令，将系统环境即时状态与文件一同打包。
+ **灵活归档策略**：支持多目录备份，支持基于 `tar` 的排除规则（Exclude）及符号链接解析。
+ **安全保障**：
    - **传输安全**：支持 ZIP 压缩包二级密码加密。
    - **凭据安全**：内置 Fernet 对称加密工具，配置文件中的 OSS AK/SK 可通过密文存储，防止配置文件泄露导致权限丢失。
+ **多云同步上传**：支持同时推送到多个兼容 S3 协议的存储节点（如 MinIO, 阿里云 OSS, AWS S3）。
+ **智能生命周期管理**：支持基于“保留天数”和“最小留存份数”的双重清理逻辑，确保云端存储不溢出。
+ **可视化飞书报告**：通过飞书 Webhook 发送精美的消息卡片，包含主机信息、公/私网 IP、执行耗时、远程存储统计（总数及最早备份时间）。

## 📂 文件结构
| 文件 | 说明 |
| :--- | :--- |
| `backup.py` | **主程序**：控制备份流、上传逻辑与远程管理 |
| `config.py` | **配置文件**：定义备份路径、存储节点及通知 Webhook |
| `tool.py` | **工具集**：处理 IP 获取、Fernet 加解密、系统标识获取 |
| `notice.py` | **通知模块**：负责构造并发送飞书交互式消息卡片 |


## 🛠️ 快速开始
### 1. 安装依赖
确保系统安装了 `tar`, `zip` 工具以及 `python3`：

```bash
pip install requests minio cryptography
```

### 2. 配置项目
参考 `config.example.py` 创建你的 `config.py`：

Bash

```plain
cp config.example.py config.py
vim config.py
```

_主要配置项：_`_SOURCE_PATH_`_ (备份源), _`_OSS_CONFIGS_`_ (存储节点), _`_FEISU_WEBHOOK_`_ (通知地址)。_

### 3. 高级用法：加密存储 AK/SK
为了安全，建议不直接在配置文件写明文密钥：

1. 运行加密工具：`python3 backup.py --crypto`
2. 按照提示输入 URL、AK、SK。
3. 将生成的 `encrypted_text` 复制到 `config.py`，并将该节点的 `"crypto": True` 开启。
4. 使用 `python3 backup.py --decrypto` 预览解密结果确认配置无误。

### 4. 运行与自动化
**手动运行：**

Bash

```plain
python3 backup.py
```

**配置 Cron 定时任务：** 建议每天凌晨执行一次（例如 02:00）：

Bash

```plain
# 执行 crontab -e 加入下行
0 2 * * * cd /root/backup3 && /usr/bin/python3 backup.py >> /var/log/backup.log 2>&1
```

## 📊 飞书通知示例
当备份完成后，你的飞书群机器人会发送如下通知：

## **🔔**** 服务器全量备份报告**
**服务器**: Armbian-rk3528 **公网IP**: `123.x.x.x`**内网IP**: `10.0.0.118`**任务耗时**: 15s **备份归档**: `autobackup_20240510_230001.zip`**存储详情**: 🟢 **Backup-Node-01** └ 上传成功 (清理:1) └ 远程总数: 30 份 └ 最早备份: 30 天前 (2024-04-10)

## ⚖️ 许可证
本项目基于 [MIT License](https://www.google.com/search?q=LICENSE) 协议开源。

---

### 💡 提示：
+ **关于 .gitignore**：在上传到 GitHub 前，请确保 `.gitignore` 包含 `config.py`，不要将生产环境的密钥上传。
+ **关于解压**：由于使用了 `zip -P` 加密，在 Linux 下恢复时请使用 `unzip -P <你的密码> 文件名.zip`。
