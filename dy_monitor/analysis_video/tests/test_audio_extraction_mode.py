import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import analysis_video.utils.video_base64 as vb


def main():
    video_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'v0200fg10000d48qfdfog65p20hth670.MP4'))
    if not os.path.exists(video_path):
        print('error: video not found')
        return

    try:
        MB = 1024 * 1024
        class _FakeLimits:
            def __init__(self):
                self.hard_limit_bytes = 1000 * MB
                self.encode_limit_bytes = 1 * MB
        vb.Base64Limits = _FakeLimits
        vb._extract_audio_from_file = lambda p: (b'FAKEAUDIOBYTES', 'audio/mpeg')
        data_url = vb.video_to_base64(video_path, include_data_uri=True)
        print('mode', 'audio_extraction')
        print('data_url_prefix', data_url[:30])
        print('base64_len', len(data_url))
    except Exception as e:
        print('error', str(e))


if __name__ == '__main__':
    main()