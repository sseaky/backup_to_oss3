import os
import sys
import argparse
import subprocess
import datetime
from minio import Minio

# 引入自定义模块
import config
from tool import get_hostname, get_public_ip, get_default_private_ip, encrypto, decrypto, get_file_size
from notice import send_feishu_msg

def run_crypto_tool():
    """--crypto 交互式加密工具"""
    print("\n" + "="*30)
    print("      OSS 配置加密工具")
    print("="*30)
    url = input("请输入 URL (例: http://10.0.0.118:9000): ").strip()
    ak = input("请输入 Access Key: ").strip()
    sk = input("请输入 Secret Key: ").strip()
    
    print("\n[*] 加密结果如下 (请拷贝至 config.py 并设置 crypto: True):")
    print("-" * 50)
    # 调用 tool.py 中的加密函数，它会直接打印结果
    print("URL Encrypted:")
    encrypto(url, config.SKEY)
    print("\nAK Encrypted:")
    encrypto(ak, config.SKEY)
    print("\nSK Encrypted:")
    encrypto(sk, config.SKEY)
    print("-" * 50)

def run_decrypto_debug():
    """--decrypto 遍历配置并解密显示"""
    print("\n" + "="*30)
    print("      OSS 配置解密预览")
    print("="*30)
    for cfg in config.OSS_CONFIGS:
        print(f"\n[节点: {cfg['server_name']}]")
        if cfg.get("crypto"):
            try:
                # 调用 tool.py 中的解密函数
                d_url = decrypto(cfg['url'], config.SKEY)
                d_ak = decrypto(cfg['access_key'], config.SKEY)
                d_sk = decrypto(cfg['secret_key'], config.SKEY)
                print(f"  解密成功:")
                print(f"  URL: {d_url}")
                print(f"  AK:  {d_ak}")
                print(f"  SK:  {d_sk}")
            except Exception as e:
                print(f"  [X] 解密失败: {e}")
        else:
            print("  (该节点未开启 crypto，显示原样)")
            print(f"  URL: {cfg['url']}")
            print(f"  AK:  {cfg['access_key']}")

def get_remote_dir():
    """根据配置动态生成远程存储目录名"""
    # 以 CLIENT_NAME 或 hostname 作为基础前缀
    base_name = config.CLIENT_NAME if config.CLIENT_NAME else get_hostname()
    parts = [base_name]

    # 如果开启了公网 IP 开关，追加公网 IP
    if config.CLIENT_NAME_WITH_PUBLIC_IP:
        pub_ip = get_public_ip()
        if pub_ip:
            parts.append(pub_ip)

    # 如果开启了私网 IP 开关，追加私网 IP
    if config.CLIENT_NAME_WITH_PRIVATE_IP:
        priv_ip = get_default_private_ip()
        if priv_ip:
            parts.append(priv_ip)

    # 使用下划线连接所有部分
    return "_".join(parts)

def collect_status():
    """收集系统状态信息到临时文件"""
    if not config.BACKUP_STAUS:
        return
    print(f"[*] 正在收集系统状态到 {config.STATUS_FILE_PATH}...")
    with open(config.STATUS_FILE_PATH, "w") as f:
        f.write(f"Backup Task Start: {datetime.datetime.now()}\n")
        # 增加统计命令
        extra_cmds = ["dpkg -l | head -n 20", "crontab -l"]
        for cmd in config.STATUS_COMMANDS + extra_cmds:
            f.write(f"\n{'='*20} {cmd} {'='*20}\n")
            f.write(subprocess.getoutput(cmd) + "\n")

def get_oss_stats(client, bucket_name, remote_prefix):
    """获取远程 OSS 存储统计信息"""
    try:
        objects = list(client.list_objects(bucket_name, prefix=remote_prefix, recursive=True))
        if not objects:
            return 0, "无数据"
        
        total_count = len(objects)
        # 按最后修改时间排序获取最早的备份
        objects.sort(key=lambda x: x.last_modified)
        oldest_time = objects[0].last_modified
        
        # 计算天数差
        now = datetime.datetime.now(datetime.timezone.utc)
        days_ago = (now - oldest_time).days
        
        time_str = oldest_time.strftime('%Y-%m-%d')
        return total_count, f"{days_ago} 天前 ({time_str})"
    except Exception as e:
        return "未知", f"获取失败: {e}"

def create_archive():
    """执行打包与可选的密码加密，并处理 tar 常见的退出码"""
    now_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{config.BACKUP_FILE_STEM}_{now_tag}"
    tar_name = f"{base_name}.tar.gz"

    print(f"[*] 正在创建本地归档: {tar_name}...")
    
    # 构造命令
    cmd = ["tar", "-czf", tar_name]
    if config.TAR_DEREFERENCE: cmd.append("-h")
    for exclude in config.SOURCE_EXCLUDE:
        cmd.append(f"--exclude={exclude}")
    
    paths = [p for p in config.SOURCE_PATH if os.path.exists(p)]
    if os.path.exists(config.STATUS_FILE_PATH):
        paths.append(config.STATUS_FILE_PATH)
    
    if not paths:
        raise Exception("没有找到任何有效的备份源路径")

    cmd.extend(paths)
    
    # 优化点：手动处理进程，允许退出码 1 (Warning)
    process = subprocess.run(cmd, capture_output=True, text=True)
    
    # tar 返回 0 是成功，返回 1 是警告（如文件消失），这在备份时通常可以接受
    if process.returncode not in [0, 1]:
        error_msg = process.stderr if process.stderr else "未知错误"
        raise Exception(f"tar 命令失败 (退出码 {process.returncode}): {error_msg}")
    elif process.returncode == 1:
        print(f"[!] 警告: 备份过程中某些文件发生了变动 (tar exit code 1)")

    # 之后的 ZIP 处理逻辑保持不变
    if config.USE_ZIP:
        zip_name = f"{base_name}.zip"
        print(f"[*] 正在执行 ZIP 密码加密...")
        subprocess.run(["zip", "-P", config.ZIP_PASSWORD, "-q", zip_name, tar_name], check=True)
        os.remove(tar_name)
        return zip_name
    return tar_name

def manage_retention(client, bucket_name, remote_prefix):
    """执行保留策略并返回删除数量"""
    objects = list(client.list_objects(bucket_name, prefix=remote_prefix, recursive=True))
    objects.sort(key=lambda x: x.last_modified)
    
    total = len(objects)
    now = datetime.datetime.now(datetime.timezone.utc)
    deleted_count = 0
    
    for obj in objects:
        if (total - deleted_count) <= config.MIN_COUNT_TO_KEEP:
            break
        if (now - obj.last_modified).days > config.DAYS_TO_RETAIN:
            client.remove_object(bucket_name, obj.object_name)
            deleted_count += 1
    return deleted_count

def main():
    parser = argparse.ArgumentParser(description="Detailed Backup Script")
    parser.add_argument("--crypto", action="store_true")
    parser.add_argument("--decrypto", action="store_true")
    args = parser.parse_args()

    if args.crypto:
        run_crypto_tool()
        return
    
    if args.decrypto:
        run_decrypto_debug()
        return

    # --- 1. 获取基础环境信息 ---
    start_time = datetime.datetime.now()
    hostname = config.CLIENT_NAME if config.CLIENT_NAME else get_hostname()
    public_ip = get_public_ip()
    private_ip = get_default_private_ip()
    
    print(f"--- 备份任务开始 ---")
    print(f"主机: {hostname}")
    print(f"内网IP: {private_ip} | 公网IP: {public_ip}")
    
    collect_status()
    
    local_file = None
    oss_info_msg = []
    is_all_success = True

    try:
        # --- 2. 打包本地文件 ---
        local_file = create_archive()
        # 【新增】获取备份文件大小
        file_size = get_file_size(local_file)
        remote_dir = get_remote_dir()
        
        print(f"[*] 备份文件生成成功: {local_file} (大小: {file_size})")

        # --- 3. 遍历上传至 OSS ---
        for cfg in config.OSS_CONFIGS:
            try:
                print(f"[*] 正在上传至节点: {cfg['server_name']}/{remote_dir}...")
                u_val, ak_val, sk_val = cfg['url'], cfg['access_key'], cfg['secret_key']
                if cfg.get("crypto"):
                    u_val = decrypto(u_val, config.SKEY); ak_val = decrypto(ak_val, config.SKEY); sk_val = decrypto(sk_val, config.SKEY)

                endpoint = u_val.replace("http://", "").replace("https://", "").rstrip('/')
                client = Minio(endpoint, access_key=ak_val, secret_key=sk_val, secure=u_val.startswith("https"))
                
                # 上传文件
                remote_path = f"{remote_dir}/{local_file}"
                client.fput_object(cfg['bucket_name'], remote_path, local_file)
                
                # 执行清理并统计远程状态
                del_num = manage_retention(client, cfg['bucket_name'], f"{remote_dir}/")
                total_remote, oldest_info = get_oss_stats(client, cfg['bucket_name'], f"{remote_dir}/")
                
                # 打印详细本地输出 (包含文件大小)
                print(f"    [OK] 节点: {cfg['server_name']} | 远程总数: {total_remote} | 最早: {oldest_info} | 清理: {del_num}")
                
                oss_info_msg.append(
                    f"🟢 **{cfg['server_name']}/{remote_dir}**\n"
                    f" └ 上传成功 (清理:{del_num})\n"
                    f" └ 远程总数: {total_remote} 份\n"
                    f" └ 最早备份: {oldest_info}"
                )
                
            except Exception as e:
                print(f"    [ERR] 节点: {cfg['server_name']} | 错误: {e}")
                oss_info_msg.append(f"🔴 **{cfg['server_name']}**: 失败 ({str(e)[:50]})")
                is_all_success = False

        # --- 4. 发送详细飞书通知 (增加备份大小展示) ---
        duration = (datetime.datetime.now() - start_time).seconds
        notice_content = (
            f"**服务器**: {hostname}\n"
            f"**公网IP**: {public_ip}\n"
            f"**内网IP**: {private_ip}\n"
            f"**任务耗时**: {duration}s\n"
            f"**备份归档**: {local_file} ({file_size})\n"
            f"**存储详情**:\n" + "\n".join(oss_info_msg)
        )
        
        # 注意：此处修复了你代码片段中 config.FEISHU_ENABLED 未定义的逻辑
        # 按照 config.py 内容，这里应该直接调用或判断 FEISU_WEBHOOK 是否存在
        send_feishu_msg(f"{hostname} 备份报告", notice_content, is_success=is_all_success)

        # 成功后删除本地归档
        if is_all_success and local_file and os.path.exists(local_file):
            os.remove(local_file)

    except Exception as e:
        print(f"[CRITICAL] 备份失败: {e}")
        send_feishu_msg("备份任务异常中止", f"主机: {hostname}\n错误原因: {e}", is_success=False)
    finally:
        if os.path.exists(config.STATUS_FILE_PATH):
            os.remove(config.STATUS_FILE_PATH)

if __name__ == "__main__":
    main()