import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from analysis_video.analysis.llm_client import analyze_text_with_llm


def main():
    text = "测试：请复述这一句。"
    prompt = "你是一个中文助手，请尽量简洁地回答用户。"
    content, cost = analyze_text_with_llm(text, prompt)
    print('content_len', len(content or ''))
    print('cost', cost)


if __name__ == '__main__':
    main()