from typing import List

from ..utils.logger import get_logger
from ..config import AppConfig

logger = get_logger("notifications.sms")


def send_sms(conclusions: List[dict], config: AppConfig) -> None:
    """
    短信发送占位：当前仅打印内容，未真实发送。
    后续可接入短信服务商（如 Twilio、阿里云短信等）。
    """
    if not config.notify_sms_enabled:
        logger.info("SMS notifications disabled.")
        return

    if not config.sms_recipients:
        logger.warning("No SMS recipients configured; skipping SMS.")
        return

    content_lines = [str(c.get("summary", "")) for c in conclusions]
    content = " | ".join(content_lines)

    logger.info(
        f"Pretend sending SMS to {', '.join(config.sms_recipients)}: {content}"
    )