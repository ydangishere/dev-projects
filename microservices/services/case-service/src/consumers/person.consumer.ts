import { createLogger, KafkaEvent, PersonCreatedEvent, PersonUpdatedEvent } from '@microservices/shared';
import { pool } from '../config/database';

const logger = createLogger('person-consumer');

/**
 * Handle person events từ people-service
 * Use case: Update người liên quan trong cases khi có thay đổi
 */
export async function handlePersonEvent(topic: string, event: KafkaEvent): Promise<void> {
  try {
    switch (event.eventType) {
      case 'PersonCreated':
        await handlePersonCreated(event.data as PersonCreatedEvent);
        break;
      case 'PersonUpdated':
        await handlePersonUpdated(event.data as PersonUpdatedEvent);
        break;
      case 'PersonDeleted':
        await handlePersonDeleted(event.data);
        break;
      default:
        logger.warn('Unknown event type', { eventType: event.eventType });
    }
  } catch (error) {
    logger.error('Failed to handle person event', { error, event });
  }
}

async function handlePersonCreated(data: PersonCreatedEvent): Promise<void> {
  logger.info('Person created event received', { personId: data.id });
  // Có thể log hoặc sync data nếu cần
}

async function handlePersonUpdated(data: PersonUpdatedEvent): Promise<void> {
  logger.info('Person updated event received', { personId: data.id });
  // Trong thực tế có thể update denormalized data trong cases
}

async function handlePersonDeleted(data: { id: number }): Promise<void> {
  logger.info('Person deleted event received', { personId: data.id });
  // Có thể nullify person_id trong cases hoặc soft delete
  try {
    await pool.query('UPDATE cases SET person_id = NULL WHERE person_id = $1', [data.id]);
    logger.info('Cases updated after person deletion', { personId: data.id });
  } catch (error) {
    logger.error('Failed to update cases', { error });
  }
}
