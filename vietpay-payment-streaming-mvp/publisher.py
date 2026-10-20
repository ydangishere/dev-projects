import json
import os
import sqlite3
import time
from kafka import KafkaProducer

DB = os.getenv("DB_PATH", "/tmp/vietpay-demo.db")
while True:
    try:
        producer = KafkaProducer(bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092").split(","), value_serializer=lambda x: json.dumps(x).encode(), acks="all")
        break
    except Exception as e:
        print("Kafka unavailable", e, flush=True)
        time.sleep(3)
while True:
    try:
        with sqlite3.connect(DB, timeout=30) as c:
            rows = c.execute("SELECT event_id,payload FROM outbox WHERE published=0 ORDER BY rowid LIMIT 100").fetchall()
            for event_id, payload in rows:
                producer.send("payment.events", key=event_id.encode(), value=json.loads(payload)).get(timeout=15)
                c.execute("UPDATE outbox SET published=1 WHERE event_id=?", (event_id,))
            c.commit()
    except (sqlite3.OperationalError, Exception) as e:
        print("Publisher retry:", e, flush=True)
    time.sleep(1)
