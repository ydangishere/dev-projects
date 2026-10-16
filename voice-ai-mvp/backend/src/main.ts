import 'reflect-metadata';
import 'dotenv/config';
import { Controller, Get, Module, Post, Injectable, HttpException, HttpStatus } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';

@Injectable()
class RealtimeService {
  async createClientSecret() {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey || apiKey === 'sk-your-key-here') {
      throw new HttpException('Chưa cấu hình OPENAI_API_KEY trong backend/.env', HttpStatus.SERVICE_UNAVAILABLE);
    }
    let response: Response;
    try {
      response = await fetch('https://api.openai.com/v1/realtime/client_secrets', {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session: {
            type: 'realtime',
            model: process.env.REALTIME_MODEL || 'gpt-realtime',
            instructions: 'Bạn là trợ lý giọng nói thân thiện. Ưu tiên trả lời ngắn gọn bằng tiếng Việt, trừ khi người dùng yêu cầu ngôn ngữ khác.',
            output_modalities: ['audio'],
            audio: {
              input: {
                transcription: { model: 'gpt-4o-mini-transcribe' },
                turn_detection: { type: 'server_vad', threshold: 0.5, prefix_padding_ms: 300, silence_duration_ms: 500, create_response: true, interrupt_response: true }
              },
              output: { voice: 'marin' }
            }
          }
        })
      });
    } catch {
      throw new HttpException('Không kết nối được đến OpenAI', HttpStatus.BAD_GATEWAY);
    }
    const data: any = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new HttpException(data?.error?.message || 'Không tạo được phiên Realtime', response.status >= 500 ? 502 : 400);
    }
    const value = data?.value || data?.client_secret?.value;
    if (!value) throw new HttpException('OpenAI không trả về client secret', 502);
    return { value, expires_at: data?.expires_at ?? data?.client_secret?.expires_at ?? null, model: process.env.REALTIME_MODEL || 'gpt-realtime' };
  }
}
@Controller('api')
class AppController {
  constructor(private readonly realtime: RealtimeService) {}
  @Get('health') health() { return { ok: true }; }
  @Post('session') session() { return this.realtime.createClientSecret(); }
}
@Module({ controllers: [AppController], providers: [RealtimeService] })
class AppModule {}
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors({ origin: ['http://localhost:5173', 'http://127.0.0.1:5173'], methods: ['GET', 'POST'] });
  await app.listen(Number(process.env.PORT || 3001));
  console.log(`Backend: http://localhost:${process.env.PORT || 3001}`);
}
bootstrap();
