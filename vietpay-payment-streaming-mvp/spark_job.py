"""Spark microbatch data preparation; Kafka event topic -> feature topic."""
import os
import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_json, struct, lit
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType

bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
spark = (SparkSession.builder.appName("VietPay-Features")
    .master("local[2]")
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5")
    .getOrCreate())
schema = StructType([
    StructField("event_id", StringType()), StructField("transaction_id", StringType()),
    StructField("user_id", StringType()), StructField("merchant_id", StringType()),
    StructField("amount", LongType()), StructField("created_at", DoubleType()),
])
source = spark.readStream.format("kafka").option("kafka.bootstrap.servers", bootstrap).option("subscribe", "payment.events").option("startingOffsets", "earliest").load()
features = (source.select(from_json(col("value").cast("string"), schema).alias("p"))
    .select("p.*").filter(col("event_id").isNotNull())
    .withColumn("large_amount", col("amount") >= lit(5000000)))
out = features.selectExpr("CAST(event_id AS STRING) AS key").join(features.select("event_id",to_json(struct("*")).alias("value")), col("key")==col("event_id")).selectExpr("CAST(key AS STRING) key", "CAST(value AS STRING) value")
query = (out.writeStream.format("kafka").option("kafka.bootstrap.servers", bootstrap)
    .option("topic", "payment.features").option("checkpointLocation", "/tmp/spark-checkpoints/payment-features")
    .outputMode("append").start())
query.awaitTermination()
