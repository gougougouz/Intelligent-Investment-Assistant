"""
获取视频的评论数据
"""

from typing import List, Optional, Dict
from dataclasses import dataclass
import os
import time
from datetime import datetime, timezone
from collections import deque
import requests
from analysis_video.config.settings import TikHubDouyinApiConfig, AppConfig
from analysis_video.utils.logger import get_logger
from analysis_video.accounts.user_service import UserService
from analysis_video.accounts.billing_service import BillingService





