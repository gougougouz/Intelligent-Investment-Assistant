import re
from typing import Optional


def clean_llm_analysis_text(text: Optional[str]) -> str:
    """
    清洗 LLM 输出的分析文本，移除形如 【时讯分享类】、【观点输出类】等分类标签行。
    
    Args:
        text: 原始 LLM 输出文本（可能为 None 或空字符串）
    
    Returns:
        清洗后的文本，保留非分类行，去除前后空白。
    """
    if not text or not isinstance(text, str):
        return ""
    
    lines = text.splitlines()
    # 过滤掉单独一行且匹配 【...】 格式的行（允许前后空格）
    filtered_lines = [
        line for line in lines
        if not re.fullmatch(r"\s*【[^】]*】\s*", line)
    ]
    return "\n".join(filtered_lines).strip()