import time
import threading
import os
import json
import csv
from datetime import datetime, time as dtime, timedelta

from .utils.logger import get_logger
from .config import load_config, AppConfig
from .config.settings import EmailConfig
import requests
from .providers.douyin import fetch_recent_videos_for_creators
from .accounts.user_service import UserService
from .accounts.billing_service import BillingService
from .analysis.csv_analyzer import analyze_pending_videos_in_csv
from .notifications.email_service import send_email_to_recipient

logger = get_logger("scheduler")


def is_in_trading_session() -> bool:
    """
    判断当前时间是否为A股交易时段（周一至周五，法定节假日除外）。
    - 上午时段: 09:15 - 11:30
    - 下午时段: 13:00 - 15:00
    """
    now = datetime.now()
    # 1. 判断是否为周一至周五
    if now.weekday() > 4:  # 0-4 is Mon-Fri
        return False

    # 2. 判断是否在交易时间段内
    t = now.time()
    morning_session = dtime(9, 15) <= t <= dtime(11, 30)
    afternoon_session = dtime(13, 0) <= t <= dtime(15, 0)

    return morning_session or afternoon_session

def _next_day_is_trading() -> bool:
    """判断明天是否为交易日（仅判断周一至周五）。"""
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.weekday() <= 4


def job(config: AppConfig) -> None:
    """执行一次完整任务：抓取视频、分析视频、向用户发送邮件并记账扣费。"""
    logger.info("Job started.") 
    run_start = datetime.now()
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "config", "storage"))
    os.makedirs(base, exist_ok=True)
    store_path = os.path.join(base, "users.json")
    billing_path = os.path.join(base, "billing.json")
    user_service = UserService(store_path)
    billing = BillingService(billing_path)
    try:
        fetch_recent_videos_for_creators(config)
        analyze_pending_videos_in_csv(config)
    except requests.exceptions.HTTPError as e:
        resp = getattr(e, "response", None)
        status = getattr(resp, "status_code", None)
        url = getattr(resp, "url", "")
        try:
            body = resp.text
        except Exception:
            body = ""
        logger.error(f"HTTPError status={status} url={url} body={body[:500]}")
    except Exception as e:
        logger.error(f"Error: {e}")

    creators_path = os.path.join(base, "creators.json")
    sec_to_safe: dict[str, str] = {}
    try:
        with open(creators_path, "r", encoding="utf-8") as f:
            cdata = json.load(f)
        for name, info in (cdata.get("creators") or {}).items():
            sec = (info or {}).get("id")
            disp = (info or {}).get("display_name") or name
            safe = disp.replace("/", "_").replace("\\", "_")
            if sec:
                sec_to_safe[sec] = safe
    except Exception:
        pass

    videos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage", "videos"))
    for u in user_service.list_users():
        if not u.active:
            continue
        follows = user_service.list_follows(u.phone)
        creator_ids = {f.creator_id for f in follows}
        conclusions = []
        total_llm_cents = 0
        for cid in creator_ids:
            safe = sec_to_safe.get(cid, cid)
            fpath = os.path.join(videos_dir, f"{safe}.csv")
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", newline="") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
            except Exception:
                continue
            for i, row in enumerate(rows):
                if i == 0:
                    continue
                if len(row) < 9:
                    continue
                try:
                    ts_str = (row[8] or "").strip()
                    ts_obj = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
                if ts_obj <= run_start:
                    continue
                aweme_id = (row[0] or "").strip()
                text = row[6]
                try:
                    llm_cents = int((row[7] or "0").strip())
                except Exception:
                    llm_cents = 0
                multiplier = int(getattr(config, "llm_cost_multiplier", 2) or 2)
                per_fee = (llm_cents or 0) * multiplier
                conclusions.append({"summary": f"{aweme_id}", "details": {"analysis": text, "fee_cents": per_fee}})
                total_llm_cents += llm_cents
                billing.record(u.id, "llm.analyze", llm_cents or 1, {"aweme_id": aweme_id})
        if conclusions:
            send_email_to_recipient(conclusions, u.email, config)
            cfg_email = EmailConfig()
            email_cents = int(round(float(getattr(cfg_email, "email_cost_yuan", 0) or 0) * 100))
            total_cost_cents = total_llm_cents * int(getattr(config, "llm_cost_multiplier", 2) or 2) + email_cents
            if total_cost_cents:
                user_service.adjust_balance(u.id, -total_cost_cents)
                billing.record(u.id, "charge.balance", total_cost_cents, {"llm_total_cents": str(total_llm_cents)})
    logger.info("Job finished.")


def start_scheduler() -> None:
    """启动定时调度。

    行为说明：
    - 加载应用配置并立即执行一次 `job`。
    - 循环心跳每 60 秒，根据交易日与开盘时段规则：
      · 开盘时段：每 30 分钟触发一次 `job`；
      · 闭市时段：按 `closed_scan_interval_hours` 的间隔触发，且在 `special_push_times` 指定的时间点额外触发；
    - 支持 Ctrl-C 终止，终止时记录日志。
    """
    config = load_config()
    stop_event = threading.Event()
    job(config)
    try:
        last_closed_run = None
        while not stop_event.is_set():
            now = datetime.now()
            run_now = False
            if is_in_trading_session():
                if now.minute % 30 == 0:
                    run_now = True
            else:
                closed_hours = int(getattr(config, "closed_scan_interval_hours", 12) or 12)
                if last_closed_run is None or (datetime.now() - last_closed_run) >= timedelta(hours=closed_hours):
                    run_now = True
                special = [x.strip() for x in getattr(config, "special_push_times", ["22:00", "09:00"]) or []]
                if now.strftime("%H:%M") in special:
                    run_now = True
                if now.strftime("%H:%M") in special and _next_day_is_trading():
                    run_now = True
            if run_now:
                job(config)
                if not is_in_trading_session():
                    last_closed_run = datetime.now()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")