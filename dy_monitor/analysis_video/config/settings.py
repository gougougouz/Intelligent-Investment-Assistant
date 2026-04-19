import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from dotenv import load_dotenv

# 优先加载 analysis_video 目录下的 .env，确保类默认值能读取到
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

"""
配置参数说明（.env内的参数,可通过环境变量覆盖）：

- DOUYIN_AUTH_TOKEN（默认 None）
  抖音 API 的鉴权 token。

"""

MB = 1024 * 1024


@dataclass
class Base64Limits:
    """Base64 转码阈值配置。

    - hard_limit_bytes (默认 200MB)
      视频下载/处理的硬上限（字节）。对于 URL：超过该大小不下载；对于本地文件：超过该大小拒绝处理。

    - encode_limit_bytes (默认 50MB)
      视频整段 base64 的编码上限（字节）。小于等于该值时直接整段视频转 base64；介于该值与硬上限之间时进行音轨分离，仅编码音频。
    """
    hard_limit_bytes: int = 200 * MB  # 硬上限：>200MB 不下载/不处理
    encode_limit_bytes: int = 50 * MB  # 编码上限：<=50MB 直接整段视频转 base64；介于两者音轨分离

@dataclass
class TikHubDouyinApiConfig:
    """
    TikHub 提供商下的抖音 API 配置
    """
    base_url: str = "https://api.tikhub.io"
    auth_token: str = os.getenv("DOUYIN_AUTH_TOKEN", "")

@dataclass
class EmailConfig:
    email_cost_yuan: float = 0.11
    gmail: Tuple[str, str] = ("", "")
    qq: Tuple[str, str] = ("2543191173@qq.com", "pjkutjpxhhizdhhd")
    outlook: Tuple[str, str] = ("", "")
    netease163: Tuple[str, str] = ("WealthReportPluse@163.com", "HAn9Pbjpp6n4jcDp")

@dataclass
class ArkConfig:
    base_url: str = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    api_key: str = os.getenv("ARK_API_KEY", "")
  
@dataclass
class AppConfig:
    """
    应用配置
    """
    douyin_api: TikHubDouyinApiConfig = field(default_factory=TikHubDouyinApiConfig)
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_filename: str = "app.log"
    max_bytes: int = 5 * MB
    backup_count: int = 5
    fetch_interval_minutes: int = 60
    notify_email_enabled: bool = True
    notify_sms_enabled: bool = False
    email_recipients: List[str] = field(default_factory=list)
    sms_recipients: List[str] = field(default_factory=list)
    base64_limits: Base64Limits = field(default_factory=Base64Limits)
    llm_cost_multiplier: int = 2
    special_push_times: List[str] = field(default_factory=lambda: ["22:00", "09:00"])
    closed_scan_interval_hours: int = 12
    dispatch_email_in_job: bool = False


# --- 加载配置 ---

def load_config() -> AppConfig:
    """
    从环境变量加载应用配置，并返回统一 AppConfig 对象。
    """
    load_dotenv()

    # 使用类的默认实例，密钥在 __post_init__ 中完成加载
    douyin_api_config = TikHubDouyinApiConfig()
    email_cfg = EmailConfig()

    mod = os.getenv
    special = [x.strip() for x in (mod("SPECIAL_PUSH_TIMES", "22:00,09:00") or "").split(",") if x.strip()]
    closed_hours = int(mod("CLOSED_SCAN_INTERVAL_HOURS", "12") or 12)
    return AppConfig(
        douyin_api=douyin_api_config,
        notify_email_enabled=os.getenv("NOTIFY_EMAIL_ENABLED", "true").lower() == "true",
        notify_sms_enabled=os.getenv("NOTIFY_SMS_ENABLED", "false").lower() == "true",
        email_recipients=[item.strip() for item in os.getenv("EMAIL_RECIPIENTS", "").split(",") if item.strip()],
        sms_recipients=[item.strip() for item in os.getenv("SMS_RECIPIENTS", "").split(",") if item.strip()],
        llm_cost_multiplier=int(os.getenv("LLM_COST_MULTIPLIER", "2") or 2),
        special_push_times=special or ["22:00", "09:00"],
        closed_scan_interval_hours=closed_hours,
        dispatch_email_in_job=os.getenv("DISPATCH_EMAIL_IN_JOB", "false").lower() == "true",
    )
