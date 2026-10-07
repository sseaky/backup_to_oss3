"""通知模块：飞书 Webhook 交互式卡片消息。

可独立初始化与测试：FeishuNotifier(webhook).send(title, content)。
"""

import datetime
import json

import requests


class FeishuNotifier:
    """飞书机器人通知（无签名模式）。webhook 为空时静默跳过。"""

    def __init__(self, webhook="", sec="", timeout=10, logger=None):
        self.webhook = webhook
        self.sec = sec
        self.timeout = timeout
        self.logger = logger

    def send(self, title, content, is_success=True):
        """发送一张交互式卡片，返回是否成功。"""
        if not self.webhook:
            if self.logger:
                self.logger.debug("未配置 FEISHU_WEBHOOK，跳过通知")
            return False

        color = "blue" if is_success else "red"
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "template": color,
                    "title": {
                        "tag": "plain_text",
                        "content": f"{'✅' if is_success else '❌'} {title}",
                    },
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
                            }
                        ],
                    },
                ],
            },
        }
        try:
            response = requests.post(
                self.webhook,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            res_data = response.json()
        except Exception as e:  # noqa: BLE001 - 通知失败不应影响备份主流程
            if self.logger:
                self.logger.error("飞书通知请求异常: %s", e)
            return False

        if res_data.get("code") == 0:
            if self.logger:
                self.logger.info("飞书通知发送成功")
            return True
        if self.logger:
            self.logger.error(
                "飞书返回错误: %s (Code: %s)", res_data.get("msg"), res_data.get("code")
            )
        return False
