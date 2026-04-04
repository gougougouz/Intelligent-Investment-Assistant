import sys
import os

# 将项目根目录添加到 Python 路径中，以便导入 `analysis_video` 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from analysis_video.utils.video_base64 import video_to_base64

def test_local_video_conversion():
    """
    测试将本地视频文件转换为 Base64 字符串的功能。
    """
    # 指定位于项目根目录的视频文件
    video_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'v0200fg10000d48qfdfog65p20hth670.MP4'))
    
    print(f"--- 开始测试本地视频转换 ---")
    print(f"视频文件路径: {video_path}")
    
    # 检查文件是否存在
    if not os.path.exists(video_path):
        print(f"错误: 视频文件未找到，请确认路径是否正确！")
        return

    try:
        # 调用核心函数进行转换
        base64_string = video_to_base64(video_path)
        
        # 验证并打印结果
        if base64_string:
            print(f"成功: 视频已成功转换为 Base64 字符串。")
            print(f"Base64 字符串 (前100个字符): {base64_string[:100]}...")
        else:
            print(f"失败: 函数返回了空的 Base64 字符串。")
            
    except Exception as e:
        print(f"异常: 在转换过程中发生错误: {e}")
    finally:
        print(f"--- 测试结束 ---")

if __name__ == "__main__":
    test_local_video_conversion()