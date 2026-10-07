"""配置工具模块：交互式加密 OSS 配置、解密预览。

可独立调用：run_crypto_tool(skey) / run_decrypto_preview(cfg)。
"""

from libs.crypto import decrypto, encrypto


def run_crypto_tool(skey):
    """--crypto：交互式加密 URL/AK/SK，输出可直接粘贴到 config.py 的密文。"""
    print("\n" + "=" * 30)
    print("      OSS 配置加密工具")
    print("=" * 30)
    if not skey:
        print("[X] config.SKEY 为空，无法加密，请先配置 SKEY。")
        return
    url = input("请输入 URL (例: http://10.0.0.118:9000): ").strip()
    ak = input("请输入 Access Key: ").strip()
    sk = input("请输入 Secret Key: ").strip()

    print("\n[*] 加密结果如下 (请拷贝至 config.py 并设置 crypto: True):")
    print("-" * 50)
    print("URL Encrypted:")
    encrypto(url, skey)
    print("\nAK Encrypted:")
    encrypto(ak, skey)
    print("\nSK Encrypted:")
    encrypto(sk, skey)
    print("-" * 50)


def run_decrypto_preview(cfg):
    """--decrypto：遍历原始配置并解密显示，用于确认密文与 SKEY 正确。

    注意：cfg 应以 decrypt=False 加载，此处自行解密并逐节点报告结果。
    """
    print("\n" + "=" * 30)
    print("      OSS 配置解密预览")
    print("=" * 30)
    for node in cfg.oss_configs:
        print(f"\n[节点: {node.get('server_name')}]")
        if node.get("crypto"):
            try:
                print("  解密成功:")
                print(f"  URL: {decrypto(node['url'], cfg.SKEY)}")
                print(f"  AK:  {decrypto(node['access_key'], cfg.SKEY)}")
                print(f"  SK:  {decrypto(node['secret_key'], cfg.SKEY)}")
            except Exception as e:  # noqa: BLE001 - 预览命令需展示失败原因
                print(f"  [X] 解密失败: {e}")
        else:
            print("  (该节点未开启 crypto，显示原样)")
            print(f"  URL: {node['url']}")
            print(f"  AK:  {node['access_key']}")
