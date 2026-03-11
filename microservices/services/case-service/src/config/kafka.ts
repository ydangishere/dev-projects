import { Kafka, Consumer, Producer } from 'kafkajs';
import { createLogger } from '@microservices/shared';
import { handlePersonEvent } from '../consumers/person.consumer';

const logger = createLogger('kafka');

const kafka = new Kafka({
  clientId: process.env.KAFKA_CLIENT_ID || 'case-service',
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
});

export const kafkaProducer: Producer = kafka.producer();
export const kafkaConsumer: Consumer = kafka.consumer({
  groupId: process.env.KAFKA_GROUP_ID || 'case-service-group',
});

export async function connectKafka(): Promise<void> {
  await kafkaProducer.connect();
  await kafkaConsumer.connect();
}

/**
 * Start Kafka consumer để listen events từ people-service
 */
export async function startConsumer(): Promise<void> {
  try {
    await kafkaConsumer.subscribe({
      topics: ['people.created', 'people.updated', 'people.deleted'],
      fromBeginning: false,
    });

    await kafkaConsumer.run({
      eachMessage: async ({ topic, partition, message }) => {
        try {
          const event = JSON.parse(message.value?.toString() || '{}');
          logger.info('Received event', { topic, eventType: event.eventType });

          // Handle event based on topic
          if (topic.startsWith('people.')) {
            await handlePersonEvent(topic, event);
          }
        } catch (error) {
          logger.error('Error processing message', { error, topic });
        }
      },
    });

    logger.info('Kafka consumer started');
  } catch (error) {
    logger.error('Failed to start consumer', { error });
    throw error;
  }
}

export const Topics = {
  CASE_CREATED: 'case.created',
  CASE_UPDATED: 'case.updated',
  CASE_DELETED: 'case.deleted',
};
