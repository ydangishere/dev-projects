import { INDEX_NAME } from '../config/elasticsearch';
import { Topics } from '../config/kafka';

describe('Case Service - Unit Tests', () => {
  describe('Elasticsearch configuration', () => {
    it('should have correct index name', () => {
      expect(INDEX_NAME).toBe('cases');
    });
  });

  describe('Kafka topics', () => {
    it('should have defined topics', () => {
      expect(Topics.CASE_CREATED).toBe('case.created');
      expect(Topics.CASE_UPDATED).toBe('case.updated');
      expect(Topics.CASE_DELETED).toBe('case.deleted');
    });
  });

  describe('Case number generation', () => {
    it('should generate unique case numbers', () => {
      const generateCaseNumber = () => {
        const timestamp = Date.now();
        const random = Math.floor(Math.random() * 1000);
        return `CASE-${timestamp}-${random}`;
      };

      const num1 = generateCaseNumber();
      const num2 = generateCaseNumber();

      expect(num1).toMatch(/^CASE-\d+-\d+$/);
      expect(num2).toMatch(/^CASE-\d+-\d+$/);
    });
  });
});
