import os

# --- 1. 基础打包设置 ---
TAR_DEREFERENCE = True      # 是否解析符号链接（如果备份目录中有软连接，设为True可备份实际文件）
USE_ZIP = True              # 是否在tar包基础上进行ZIP加密压缩
ZIP_PASSWORD = "your_backup_password"  # ZIP压缩包解压密码
BACKUP_FILE_STEM = "autobackup"        # 备份文件名前缀
DAYS_TO_RETAIN = 30         # 远程备份保留天数
MIN_COUNT_TO_KEEP = 5       # 无论是否过期，最少保留的备份份数

# --- 2. 客户端标识配置 ---
# 远程BUCKET中的目录名。
# # BUCKET中的目录名，如果CLIENT_NAME为空，则自动为<hostname>，如果是家宽，用公网ip会导致目录变化 (取决于下方开关)
CLIENT_NAME = ""
CLIENT_NAME_WITH_PUBLIC_IP = False
CLIENT_NAME_WITH_PRIVATE_IP = False

# --- 3. 系统状态收集 ---
BACKUP_STAUS = True         # 是否在备份前收集系统运行状态（如df, uptime等）
STATUS_FILE_PATH = "/tmp/myState.txt"
STATUS_COMMANDS = [
    "hostname",
    "uptime",
    "w",
    "last",
    "lastb",
    "free -h",
    "mount",
    "df -h",
    "ip a",
    "ip route",
    "ip -6 route",
    "iptables-save",
    "netstat -anop",
    "netstat -lntup",
    "docker ps -a",
    "docker images",
    "crontab -l",
]

# --- 4. 备份源路径 ---
# 要备份的文件或目录列表
SOURCE_PATH = [
    os.path.abspath(__file__),
    "/etc/os-release",
    "/etc/motd",
    "/etc/hosts",
    "/etc/passwd",
    "/etc/nginx",
    "/etc/zabbix",
    "/backup",
    "/var/spool/cron/crontabs",
    "/root/.ssh",
]

# 排除规则（tar命令的--exclude参数）
SOURCE_EXCLUDE = ["*.log", "*.tmp", "*/.env", "*/.git"]

# --- 5. 飞书通知配置 (Webhook) ---
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
FEISHU_SEC = ""  # 如果飞书机器人开启了签名校验，请填写Secret；未开启则留空

# --- 6. 远程存储 (S3/MinIO/OSS) 配置 ---
# 支持多个节点同步上传
SKEY = "your_fernet_encrypt_key_here"  # 用于加密下放AK/SK的SKey (由 tool.py 生成)

OSS_CONFIGS = [
    {
        "server_name": "My-Cloud-Storage",
        "url": "http://oss-cn-hangzhou.aliyuncs.com", # 或者是 MinIO 的地址
        "bucket_name": "my-backup-bucket",
        "access_key": "your_access_key",
        "secret_key": "your_secret_key",
        "crypto": False  # 如果上述AK/SK是加密后的字符串，请设为 True
    }
]