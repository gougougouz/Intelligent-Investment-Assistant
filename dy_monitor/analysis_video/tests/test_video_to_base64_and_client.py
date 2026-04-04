import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from analysis_video.utils.video_base64 import video_to_base64
from analysis_video.analysis.llm_client import analyze_video_with_llm_url


def main():
    video_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'v0200fg10000d48qfdfog65p20hth670.MP4'))
    if not os.path.exists(video_path):
        print('error: video not found')
        return
    data_url = video_to_base64(video_path, include_data_uri=True)
    print('data_url_prefix', data_url[:30])
    prompt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'analysis', 'prompt_single_video'))
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read().strip().strip('"')
    except Exception:
        prompt = '请客观、完整地转述视频内容。'
    content, cost = analyze_video_with_llm_url(data_url, prompt)
    print('llm_content_len', len(content or ''))
    print('llm_cost', cost)


if __name__ == '__main__':
    main()