import { CacheKeys, CacheTTL } from '../config/redis';

describe('People Service - Cache Tests', () => {
  describe('Cache key generation', () => {
    it('should generate correct person cache key', () => {
      const key = CacheKeys.person(123);
      expect(key).toBe('person:123');
    });

    it('should generate correct people list cache key', () => {
      const key = CacheKeys.peopleList(1, 10);
      expect(key).toBe('people:list:1:10');
    });
  });

  describe('Cache TTL configuration', () => {
    it('should have defined TTL values', () => {
      expect(CacheTTL.person).toBe(3600);
      expect(CacheTTL.list).toBe(300);
    });
  });
});
