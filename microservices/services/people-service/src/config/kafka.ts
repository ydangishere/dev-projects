import { Kafka, Producer } from 'kafkajs';
import { createLogger, KafkaEvent } from '@microservices/shared';

const logger = createLogger('kafka');

/**
 * Kafka client setup
 */
const kafka = new Kafka({
  clientId: process.env.KAFKA_CLIENT_ID || 'people-service',
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
});

export const kafkaProducer: Producer = kafka.producer();

export async function connectKafka(): Promise<void> {
  await kafkaProducer.connect();
}

/**
 * Kafka topics
 */
export const Topics = {
  PEOPLE_CREATED: 'people.created',
  PEOPLE_UPDATED: 'people.updated',
  PEOPLE_DELETED: 'people.deleted',
};

/**
 * Publish event to Kafka
 * @param topic - Kafka topic
 * @param event - Event data
 */
export async function publishEvent<T>(topic: string, event: KafkaEvent<T>): Promise<void> {
  try {
    await kafkaProducer.send({
      topic,
      messages: [
        {
          key: event.metadata?.userId?.toString(),
          value: JSON.stringify(event),
        },
      ],
    });
    logger.info('Event published', { topic, eventType: event.eventType });
  } catch (error) {
    logger.error('Failed to publish event', { topic, error });
    throw error;
  }
}
