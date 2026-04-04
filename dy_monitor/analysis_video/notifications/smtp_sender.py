import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Union, List

def send_text_email_with_sender(
    sender: tuple,
    receiver_email: Union[str, List[str]],
    subject: str,
    body: str,
    smtp_debug: bool = False,
) -> bool:
    """根据发件邮箱域名自动选择 SMTP 配置并发送纯文本邮件。"""
    if isinstance(receiver_email, str):
        to_emails = [receiver_email]
    else:
        to_emails = receiver_email

    user, password = sender[0], sender[1]
    server = None
    port = None
    use_ssl = None

    def _map_by_domain(email: str):
        dom = email.split("@")[-1].lower().strip()
        if dom in ("gmail.com", "googlemail.com"):
            return ("smtp.gmail.com", 587, False)
        if dom in ("outlook.com", "hotmail.com", "live.com", "office365.com"):
            return ("smtp-mail.outlook.com", 587, False)
        if dom == "qq.com":
            return ("smtp.qq.com", 465, True)
        if dom == "163.com":
            return ("smtp.163.com", 465, True)
        return (None, None, None)

    if user and password:
        server, port, use_ssl = _map_by_domain(user)

    if not user or not password or not server or not port:
        return False

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if use_ssl:
            smtp = smtplib.SMTP_SSL(server, port)
        else:
            smtp = smtplib.SMTP(server, port)
            smtp.ehlo()
            smtp.starttls()
        if smtp_debug:
            smtp.set_debuglevel(1)
        smtp.login(user, password)
        smtp.sendmail(user, to_emails, msg.as_string())
        smtp.quit()
        return True
    except Exception:
        try:
            smtp.quit()
        except Exception:
            pass
        return False