import * as bcrypt from 'bcrypt';

const SALT_ROUNDS = 10;

/**
 * Hash password sử dụng bcrypt
 * @param plainPassword - Password gốc
 * @returns Hashed password
 */
export async function hashPassword(plainPassword: string): Promise<string> {
  return bcrypt.hash(plainPassword, SALT_ROUNDS);
}

/**
 * So sánh password với hash
 * @param plainPassword - Password người dùng nhập
 * @param hashedPassword - Password đã hash trong DB
 * @returns true nếu match
 */
export async function comparePassword(
  plainPassword: string,
  hashedPassword: string
): Promise<boolean> {
  return bcrypt.compare(plainPassword, hashedPassword);
}
