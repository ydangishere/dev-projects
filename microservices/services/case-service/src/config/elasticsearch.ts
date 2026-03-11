import { Client } from '@elastic/elasticsearch';
import { createLogger } from '@microservices/shared';

const logger = createLogger('elasticsearch');

/**
 * Elasticsearch client
 * Use case: Full-text search cases, filter phức tạp
 */
export const esClient = new Client({
  node: process.env.ES_NODE || 'http://localhost:9200',
});

export const INDEX_NAME = 'cases';

export async function connectElasticsearch(): Promise<void> {
  try {
    await esClient.ping();
    logger.info('Elasticsearch connected');
  } catch (error) {
    throw new Error(`Elasticsearch connection failed: ${error}`);
  }
}

/**
 * Initialize cases index with mapping
 */
export async function initializeIndex(): Promise<void> {
  try {
    const exists = await esClient.indices.exists({ index: INDEX_NAME });

    if (!exists) {
      await esClient.indices.create({
        index: INDEX_NAME,
        body: {
          mappings: {
            properties: {
              case_number: { type: 'keyword' },
              title: { type: 'text' },
              description: { type: 'text' },
              status: { type: 'keyword' },
              priority: { type: 'keyword' },
              assigned_to: { type: 'integer' },
              person_id: { type: 'integer' },
              created_by: { type: 'integer' },
              created_at: { type: 'date' },
              updated_at: { type: 'date' },
            },
          },
        },
      });
      logger.info('Cases index created');
    }
  } catch (error) {
    logger.error('Failed to initialize index', { error });
  }
}

/**
 * Index case document vào Elasticsearch
 */
export async function indexCase(caseData: any): Promise<void> {
  try {
    await esClient.index({
      index: INDEX_NAME,
      id: caseData.id.toString(),
      document: caseData,
      refresh: true,
    });
    logger.info('Case indexed', { caseId: caseData.id });
  } catch (error) {
    logger.error('Failed to index case', { error, caseId: caseData.id });
  }
}

/**
 * Update case document
 */
export async function updateCaseInIndex(id: number, updates: any): Promise<void> {
  try {
    await esClient.update({
      index: INDEX_NAME,
      id: id.toString(),
      doc: updates,
      refresh: true,
    });
    logger.info('Case updated in index', { caseId: id });
  } catch (error) {
    logger.error('Failed to update case in index', { error, caseId: id });
  }
}

/**
 * Delete case document
 */
export async function deleteCaseFromIndex(id: number): Promise<void> {
  try {
    await esClient.delete({
      index: INDEX_NAME,
      id: id.toString(),
      refresh: true,
    });
    logger.info('Case deleted from index', { caseId: id });
  } catch (error) {
    logger.error('Failed to delete case from index', { error, caseId: id });
  }
}

/**
 * Search cases với full-text và filters
 */
export async function searchCases(query: string, filters?: any): Promise<any[]> {
  try {
    const must: any[] = [];

    // Full-text search
    if (query) {
      must.push({
        multi_match: {
          query,
          fields: ['title^2', 'description', 'case_number'],
          fuzziness: 'AUTO',
        },
      });
    }

    // Filters
    if (filters?.status) {
      must.push({ term: { status: filters.status } });
    }
    if (filters?.priority) {
      must.push({ term: { priority: filters.priority } });
    }
    if (filters?.assigned_to) {
      must.push({ term: { assigned_to: filters.assigned_to } });
    }

    const result = await esClient.search({
      index: INDEX_NAME,
      body: {
        query: must.length > 0 ? { bool: { must } } : { match_all: {} },
        size: 100,
        sort: [{ created_at: 'desc' }],
      },
    });

    return result.hits.hits.map((hit: any) => ({
      id: hit._id,
      ...hit._source,
    }));
  } catch (error) {
    logger.error('Search failed', { error });
    return [];
  }
}
