import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from analysis_video.accounts.user_service import UserService


def main():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'storage'))
    svc = UserService(base)

    phone = '18800000000'
    email = 'new_user@example.com'
    user_id = 'u_new'

    svc.add_user(user_id, phone, email)
    svc.users.set_balance(phone, 12345)

    u = svc.get_user_by_phone(phone)
    print('added_user', u.phone, u.email)
    print('balance_cents', u.balance_cents)


if __name__ == '__main__':
    main()