from typing import List
import os

from ..utils.logger import get_logger
from ..utils.clean_llm_analysis import clean_llm_analysis_text
from ..config import AppConfig
from ..config.settings import EmailConfig
from .smtp_sender import send_text_email_with_sender

logger = get_logger("notifications.email")

def send_email_to_recipient(conclusions: List[dict], recipient: str, config: AppConfig) -> None:
    """将视频分析结果拼装为邮件正文并发送给指定收件人。"""
    if not config.notify_email_enabled:
        logger.info("Email notifications disabled.")
        return
    if not recipient:
        logger.warning("Empty recipient; skipping email.")
        return
    content_lines = []
    content_lines.append("股东您好：")
    content_lines.append("我们是受您的委托替您阅读视频并进行简单总结，并通过邮件发送给您。本邮件不构成任何投资建议。")
    content_lines.append("")  
    content_lines.append("")
    total_fee = 0
    for c in conclusions:
        try:
            summary = c.get("summary")
            details = c.get("details") or {}
            analysis = details.get("analysis")
            fee_cents = int(details.get("fee_cents") or 0)
            if summary:
                content_lines.append(f"【{summary}】")
                content_lines.append("")
            else:
                content_lines.append(f"- {str(c)}")
            if analysis:
                cleaned_analysis = clean_llm_analysis_text(analysis) 
                content_lines.append(f"- 视频内容总览：{cleaned_analysis}")
                content_lines.append("")
                content_lines.append("")
            if fee_cents:
                fee_yuan = round(fee_cents / 100.0, 2)
                content_lines.append(f"费用：{fee_yuan}元")
            total_fee += fee_cents
        except Exception:
            content_lines.append(f"- {str(c)}")
    content = "\n".join(content_lines)
    email_cfg = EmailConfig()
    sender = None
    candidates = []
    for name in ("netease163", "qq", "gmail", "outlook"):
        if hasattr(email_cfg, name):
            cand = getattr(email_cfg, name)
            if isinstance(cand, tuple) and len(cand) == 2 and cand[0] and cand[1]:
                candidates.append(cand)
    if candidates:
        sender = candidates[0]
    if not sender:
        logger.error("No sender configured in EmailConfig.")
        return
    subject = "抖音博主视频监控分析"
    cfg = EmailConfig()
    extra_fee_yuan = float(getattr(cfg, "email_cost_yuan", 0) or 0)
    if total_fee or extra_fee_yuan:
        total_fee_yuan = round(total_fee / 100.0, 2)
        total_yuan = round(total_fee_yuan + extra_fee_yuan, 2)
        tail = f"\n本次分析费用合计：{total_yuan}元"
        content = content + tail
    logger.info(f"Email content preview (first 200 chars): {content[:200]}")
    ok = send_text_email_with_sender(sender, receiver_email=recipient, subject=subject, body=content, smtp_debug=False)
    if ok:
        logger.info(f"Email sent to {recipient}")
    else:
        logger.error(f"Email send failed for {recipient}")