// Common types dùng chung cho tất cả services

export interface User {
  id: number;
  email: string;
  full_name?: string;
  role: string;
}

export interface JwtPayload {
  userId: number;
  email: string;
  role: string;
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginationParams {
  page: number;
  limit: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

// Kafka event types
export interface KafkaEvent<T = any> {
  eventType: string;
  timestamp: string;
  data: T;
  metadata?: {
    userId?: number;
    correlationId?: string;
  };
}

export interface PersonCreatedEvent {
  id: number;
  firstName: string;
  lastName: string;
  email?: string;
}

export interface PersonUpdatedEvent {
  id: number;
  changes: Partial<PersonCreatedEvent>;
}

export interface CaseCreatedEvent {
  id: number;
  caseNumber: string;
  title: string;
  personId?: number;
}
