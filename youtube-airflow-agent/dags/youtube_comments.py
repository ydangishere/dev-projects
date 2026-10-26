"""Check YouTube public comments regularly and notify via AI + Telegram."""
from datetime import timedelta

import pendulum
from airflow.sdk import dag, task


@dag(
    dag_id="youtube_comment_ai_telegram",
    description="Monitor channel public comments and send Telegram notifications",
    schedule="0 */12 * * *",
    start_date=pendulum.datetime(2026, 10, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    tags=["youtube", "ai", "telegram"],
)
def youtube_comment_ai_telegram():
    @task(retries=2, retry_delay=timedelta(minutes=1))
    def poll_analyze_notify():
        from agent.monitor import monitor
        return monitor()

    poll_analyze_notify()


youtube_comment_ai_telegram()
