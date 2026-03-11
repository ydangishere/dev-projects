/**
 * Simple logger utility - trong production nên dùng Winston hoặc Pino
 */

type LogLevel = 'info' | 'warn' | 'error' | 'debug';

class Logger {
  private serviceName: string;

  constructor(serviceName: string) {
    this.serviceName = serviceName;
  }

  private log(level: LogLevel, message: string, meta?: any) {
    const timestamp = new Date().toISOString();
    const logMessage = {
      timestamp,
      level,
      service: this.serviceName,
      message,
      ...(meta && { meta }),
    };
    console.log(JSON.stringify(logMessage));
  }

  info(message: string, meta?: any) {
    this.log('info', message, meta);
  }

  warn(message: string, meta?: any) {
    this.log('warn', message, meta);
  }

  error(message: string, meta?: any) {
    this.log('error', message, meta);
  }

  debug(message: string, meta?: any) {
    if (process.env.NODE_ENV === 'development') {
      this.log('debug', message, meta);
    }
  }
}

export function createLogger(serviceName: string): Logger {
  return new Logger(serviceName);
}
