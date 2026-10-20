"""Read Kafka lending events with Spark Structured Streaming, print per-batch aggregates."""
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType,StructField,LongType,StringType

spark=(SparkSession.builder.master("local[2]").appName("VietPayLendingAnalytics")
    .config("spark.jars.packages","org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5").getOrCreate())
bootstrap=os.getenv("KAFKA_BOOTSTRAP","kafka:9092")
schema=StructType([StructField("application_id",LongType()),StructField("event",StringType())])
stream=(spark.readStream.format("kafka").option("kafka.bootstrap.servers",bootstrap)
    .option("subscribe","lending.events").option("startingOffsets","earliest").load())
events=stream.select(from_json(col("value").cast("string"),schema).alias("data")).select("data.*")
def summarize(batch,batch_id):
    print("batch",batch_id,flush=True)
    batch.groupBy("event").count().show(truncate=False)
query=(events.writeStream.foreachBatch(summarize)
    .option("checkpointLocation","/tmp/lending-spark-checkpoint").start())
query.awaitTermination()
