import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from analysis_video.config import load_config
from analysis_video.accounts.user_service import UserService
from analysis_video.analysis.analyzer import Conclusion
from analysis_video.notifications.email_service import send_email_to_recipient

def main():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'storage'))
    svc = UserService(base)
    recipient = ''
    for u in svc.list_users():
        if u.phone == '19526630286' or u.email == '1473157516@qq.com' or u.id == '2':
            recipient = u.email
            break
    if not recipient:
        recipient = '1473157516@qq.com'
    cs = [Conclusion(summary='测试发送：抖音监控', details={'note': 'test'})]
    class _C:
        notify_email_enabled = True
    send_email_to_recipient(cs, recipient, _C())
    print('send_invoked_to', recipient)

if __name__ == '__main__':
    main()