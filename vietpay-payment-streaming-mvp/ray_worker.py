"""Consume feature events; distribute Python risk-scoring tasks with Ray."""
import json
import os
import time
import ray
from kafka import KafkaConsumer, KafkaProducer

ray.init(num_cpus=2, include_dashboard=False, ignore_reinit_error=True)

@ray.remote
def score(event):
    amount = int(event["amount"])
    return {"event_id": event["event_id"], "transaction_id": event["transaction_id"],
            "risk_score": 75 if amount >= 5000000 else 10,
            "rule": "HIGH_AMOUNT" if amount >= 5000000 else "LOW_AMOUNT",
            "note": "Demo heuristic; not for authorization"}

bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
while True:
    try:
        consumer = KafkaConsumer("payment.features", bootstrap_servers=bootstrap, group_id="ray-risk-v1", auto_offset_reset="earliest", enable_auto_commit=False, value_deserializer=lambda x: json.loads(x))
        producer = KafkaProducer(bootstrap_servers=bootstrap, value_serializer=lambda x: json.dumps(x).encode(), acks="all")
        break
    except Exception as e:
        print("Kafka retry:", e, flush=True)
        time.sleep(3)
for batch in iter(lambda: consumer.poll(timeout_ms=1000, max_records=100), None):
    pending = []
    for records in batch.values():
        for record in records:
            pending.append(score.remote(record.value))
    if pending:
        for result in ray.get(pending):
            producer.send("payment.risk", key=result["event_id"].encode(), value=result).get(timeout=15)
        consumer.commit()
        print("Scored", len(pending), "events", flush=True)
