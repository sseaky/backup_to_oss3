import json
import requests
import time
import config

def send_feishu_msg(title, content, is_success=True):
    """最简 Webhook 通知模式 (无签名)"""
    if not config.FEISHU_WEBHOOK:
        return

    color = "blue" if is_success else "red"
    
    # 构造最基础的飞书卡片格式
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "template": color,
                "title": {
                    "tag": "plain_text",
                    "content": f"{'✅' if is_success else '❌'} {title}"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                },
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"}]
                }
            ]
        }
    }

    try:
        # 移除所有签名相关字段，直接发送
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            config.FEISHU_WEBHOOK, 
            data=json.dumps(payload), 
            headers=headers, 
            timeout=10
        )
        res_data = response.json()
        
        if res_data.get("code") == 0:
            print("[V] 飞书通知发送成功。")
        else:
            print(f"[X] 飞书返回错误: {res_data.get('msg')} (Code: {res_data.get('code')})")
            print("[!] 请检查飞书后台：安全设置是否已清空（不勾选任何选项）。")
    except Exception as e:
        print(f"[X] 飞书请求异常: {e}")