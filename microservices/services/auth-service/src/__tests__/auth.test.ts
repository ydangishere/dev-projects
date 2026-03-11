import { hashPassword, comparePassword, generateToken, verifyToken } from '@microservices/shared';

describe('Auth Service - Unit Tests', () => {
  describe('Password hashing', () => {
    it('should hash password correctly', async () => {
      const password = 'test123456';
      const hashed = await hashPassword(password);

      expect(hashed).toBeDefined();
      expect(hashed).not.toBe(password);
      expect(hashed.length).toBeGreaterThan(20);
    });

    it('should compare password correctly', async () => {
      const password = 'test123456';
      const hashed = await hashPassword(password);

      const isValid = await comparePassword(password, hashed);
      expect(isValid).toBe(true);

      const isInvalid = await comparePassword('wrongpassword', hashed);
      expect(isInvalid).toBe(false);
    });
  });

  describe('JWT token', () => {
    it('should generate and verify token', () => {
      const payload = {
        userId: 1,
        email: 'test@example.com',
        role: 'user',
      };

      const token = generateToken(payload);
      expect(token).toBeDefined();
      expect(typeof token).toBe('string');

      const decoded = verifyToken(token);
      expect(decoded).toBeDefined();
      expect(decoded?.userId).toBe(payload.userId);
      expect(decoded?.email).toBe(payload.email);
      expect(decoded?.role).toBe(payload.role);
    });

    it('should return null for invalid token', () => {
      const decoded = verifyToken('invalid-token');
      expect(decoded).toBeNull();
    });
  });
});
