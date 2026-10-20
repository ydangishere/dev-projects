"""TradingView -> match -> research -> risk -> Telegram. Fail-closed scaffold."""
import json
import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from airflow import DAG
from airflow.exceptions import AirflowSkipException
from airflow.operators.python import PythonOperator

DB = os.getenv("SHARED_DB", "/opt/shared/signals.db")
CONFIG = "/opt/config/settings.json"

def settings():
    return json.loads(Path(CONFIG).read_text(encoding="utf-8"))

def match_alerts(**context):
    cfg = settings()["alert_matching"]
    allowed = set(cfg.get("allowed_alert_ids", []))
    if not cfg.get("enabled") or len(allowed) < 2:
        raise AirflowSkipException("Alert matching not configured yet")
    if not Path(DB).exists():
        raise AirflowSkipException("No alerts received yet")
    db = sqlite3.connect(DB, timeout=20)
    db.execute("PRAGMA busy_timeout=20000")
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS processed_pairs (pair_key TEXT PRIMARY KEY, created_at INTEGER NOT NULL)")
        window = int(float(cfg.get("window_hours", 4)) * 3600)
        if window <= 0:
            raise ValueError("window_hours must be positive")
        rows = db.execute("SELECT id,alert_id,symbol,side,received_at FROM alerts WHERE received_at>=? ORDER BY received_at DESC LIMIT 500", (int(time.time())-window,)).fetchall()
        chosen = None
        for a in rows:
            if a[1] not in allowed:
                continue
            for b in rows:
                if a[0] == b[0] or a[1] == b[1] or b[1] not in allowed:
                    continue
                if abs(a[4]-b[4]) > window:
                    continue
                if cfg.get("require_same_symbol", True) and a[2] != b[2]:
                    continue
                if cfg.get("require_same_side", True) and a[3] != b[3]:
                    continue
                key = f"{min(a[0],b[0])}:{max(a[0],b[0])}"
                if not db.execute("SELECT 1 FROM processed_pairs WHERE pair_key=?", (key,)).fetchone():
                    chosen = (key,a,b)
                    break
            if chosen:
                break
        if not chosen:
            db.rollback()
            raise AirflowSkipException("No eligible unmatched pair")
        key,a,b = chosen
        db.execute("INSERT INTO processed_pairs VALUES(?,?)", (key,int(time.time())))
        db.commit()
        return {"pair_key":key,"alerts":[{"id":x[0],"alert_id":x[1],"symbol":x[2],"side":x[3],"received_at":x[4]} for x in (a,b)]}
    finally:
        db.close()

def research(**context):
    cfg = settings()["ai_research"]
    if not cfg.get("enabled") or not cfg.get("provider") or not cfg.get("decision_criteria"):
        raise AirflowSkipException("AI research provider/skill/criteria not configured")
    raise AirflowSkipException("Research adapter not implemented; fail closed")

def risk_check(**context):
    cfg = settings()["risk_check"]
    if not cfg.get("enabled") or not cfg.get("rules"):
        raise AirflowSkipException("Risk rules not configured")
    raise AirflowSkipException("Risk adapter not implemented; fail closed")

def telegram_report(**context):
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        raise AirflowSkipException("Telegram credentials not configured")
    raise AirflowSkipException("Report adapter not implemented")

def execution_disabled():
    raise AirflowSkipException("Live trading intentionally disabled")

with DAG(dag_id="tradingview_research_pipeline", description="Two alerts -> research -> risk -> Telegram; execution disabled", start_date=datetime(2026,1,1), schedule_interval="* * * * *", catchup=False, max_active_runs=1, default_args={"retries":0,"execution_timeout":timedelta(minutes=5)}, tags=["tradingview","research","mvp"]) as dag:
    a=PythonOperator(task_id="match_alerts",python_callable=match_alerts)
    b=PythonOperator(task_id="ai_deep_research",python_callable=research)
    c=PythonOperator(task_id="risk_check",python_callable=risk_check)
    d=PythonOperator(task_id="telegram_report",python_callable=telegram_report)
    e=PythonOperator(task_id="execution_disabled",python_callable=execution_disabled)
    a >> b >> c >> d >> e
