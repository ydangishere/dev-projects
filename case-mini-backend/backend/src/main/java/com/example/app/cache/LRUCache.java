package com.example.app.cache;

/**
 * LRU Cache Interface
 * Có thể implement bằng Custom HashMap+LinkedList hoặc Redis
 */
public interface LRUCache {
    
    /**
     * Lấy value theo key
     * @param key - key cần tìm
     * @return value nếu tìm thấy, null nếu không có
     */
    String get(String key);
    
    /**
     * Thêm/update key-value pair
     * @param key - key
     * @param value - value
     */
    void put(String key, String value);
    
    /**
     * Xóa key khỏi cache (for invalidation)
     * @param key - key cần xóa
     */
    void delete(String key);
    
    /**
     * Lấy kích thước cache hiện tại
     */
    int size();
    
    /**
     * Xóa tất cả cache
     */
    void clear();
    
    /**
     * Lấy capacity tối đa
     */
    int getCapacity();
}