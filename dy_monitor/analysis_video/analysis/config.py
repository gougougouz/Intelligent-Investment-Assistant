"""
全局配置文件：统一管理模型参数、评分阈值、权重和历史极值。
"""

# =========================
# 火山引擎 Ark 访问配置
# =========================
# 说明：请根据实际账户信息填写。优先使用 ARK_API_KEY。
ARK_API_KEY = "adb778da-1cfc-4997-be77-a24422b4da47"
ARK_ACCESS_KEY = ""
ARK_SECRET_KEY = ""
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# =========================
# 模型 ID 配置（按要求固定）
# =========================
VISION_MODEL_ID = "doubao-seed-2-0-mini-260215"
TEXT_MODEL_ID = "doubao-seed-1-6-lite-251015"
EMBEDDING_MODEL_ID = "doubao-embedding-vision-251215"

# =========================
# 输入数据与业务约束
# =========================
TARGET_STOCK_OR_SECTOR = "机器人行业股票"
ALLOWED_AUTH_TYPES = {
    "普通用户",
    "垂类财经博主",
    "券商认证",
    "基金从业认证",
}

# =========================
# 强制归一化最大值（必须严格使用）
# =========================
FAN_COUNT_MAX = 2_000_000
VIDEO_LIKE_MAX = 3_000
COMMENT_LIKE_MAX = 1_000

# =========================
# 评分阈值与权重
# =========================
LOGIC_QUALITY_THRESHOLD = 0.4

RAW_SENTIMENT_WEIGHT_TEXT = 0.6
RAW_SENTIMENT_WEIGHT_AUDIO = 0.25
RAW_SENTIMENT_WEIGHT_VISUAL = 0.15

LOGIC_SCORE_WEIGHT_A = 0.4
LOGIC_SCORE_WEIGHT_B = 0.35
LOGIC_SCORE_WEIGHT_C = 0.25

# =========================
# 百分制映射历史极值
# =========================
HIST_MIN = -3.0
HIST_MAX = 4.0

# =========================
# 重试策略
# =========================
API_RETRY_TIMES = 3
API_RETRY_INTERVAL_SEC = 1

# =========================
# 固定 Prompt（必须保持一致）
# =========================
MULTIMODAL_PROMPT = """你是专业A股财经多模态分析助手，严格按要求分析针对机器人行业股票的抖音财经视频，仅返回纯JSON，无其他任何文字、Markdown或转义字符：
1. full_text：合并视频标题、字幕、语音转写、画面所有文字的完整文本
2. text_sentiment：对机器人行业股票的情绪强度，-1.0极端看空~+1.0极端看多，保留2位小数
3. text_certainty：观点论据充分度，0.0纯情绪~1.0论据完整，保留2位小数
4. audio_sentiment_correction：博主语音情绪修正值，-0.5极端消极~+0.5极端积极，无语音返回0.0，保留2位小数
5. visual_sentiment_correction：博主面部表情情绪修正值，-0.3极端消极~+0.3极端积极，无清晰面部返回0.0，保留2位小数
6. finance_credibility_bonus：画面有专业财经数据/K线/研报截图返回0.1，无则返回0.0"""

LOGIC_PROMPT = """你是专业A股财经观点逻辑评分助手，仅返回纯JSON，无其他任何文字：
1. 按3个维度评分，0.0完全不符合~1.0完全符合，保留2位小数：
   a. 论据充分性（权重40%）：是否有机器人行业相关的数据/研报/政策等明确论据
   b. 逻辑一致性（权重35%）：推理是否通顺，无选择性偏差
   c. 风险提示完整性（权重25%）：是否客观提示机器人行业股票的潜在投资风险
2. logic_quality_L = 0.4*a + 0.35*b + 0.25*c，保留2位小数"""

COMMENT_PROMPT = """你是专业A股财经评论分析助手，仅返回纯JSON，无其他任何文字：
1. comment_sentiment_dir：对机器人行业股票的情绪方向，仅返回support/oppose/neutral三选一
2. comment_argument_quality_D：评论论据充分度，0.0纯情绪~1.0论据完整，保留2位小数"""

# =========================
# 情绪等级映射
# =========================
SENTIMENT_LEVEL_MAPPING = [
    {"min": 0, "max": 20, "level": "极端看空", "advice": "卖出/规避"},
    {"min": 21, "max": 40, "level": "看空", "advice": "减仓/观望"},
    {"min": 41, "max": 60, "level": "中性", "advice": "持有/观望"},
    {"min": 61, "max": 80, "level": "看多", "advice": "加仓/持有"},
    {"min": 81, "max": 100, "level": "极端看多", "advice": "重点关注/择机买入"},
]
