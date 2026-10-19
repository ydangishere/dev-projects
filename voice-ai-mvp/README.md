# Voice AI MVP

React + TypeScript frontend, NestJS backend, OpenAI Realtime API over WebRTC.

## Conversation flow

```mermaid
sequenceDiagram
    actor User
    participant Browser as React app (browser)
    participant Backend as NestJS backend
    participant OpenAI as OpenAI Realtime API

    User->>Browser: Start conversation
    Browser->>Browser: Request microphone access
    Browser->>Backend: POST /api/session (via Vite proxy)
    Backend->>OpenAI: POST /v1/realtime/client_secrets (server API key)
    OpenAI-->>Backend: Short-lived client secret
    Backend-->>Browser: Client secret
    Browser->>Browser: Create peer connection, audio track, and data channel
    Browser->>OpenAI: POST /v1/realtime/calls (SDP offer, client secret)
    OpenAI-->>Browser: SDP answer

    loop Live conversation
        Browser->>OpenAI: Microphone audio over WebRTC
        OpenAI-->>Browser: Assistant audio over WebRTC
        OpenAI-->>Browser: Data channel events (VAD, transcripts, responses, errors)
        Browser-->>User: Play audio and show status/transcripts when available
    end

    User->>Browser: Mute/unmute or stop
    Browser->>Browser: Toggle mic track or close connection and stop microphone
```

The backend uses `OPENAI_API_KEY` only to create the session secret. After the SDP handshake, audio and Realtime events travel directly between the browser and OpenAI; the backend does not relay the conversation.

## Requirements
- Node.js 20+
- OpenAI API key with Realtime API access

## Run locally
1. `cd voice-ai-mvp/backend`
2. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
3. `npm install && npm run dev`
4. In another terminal: `cd voice-ai-mvp/frontend`
5. `npm install && npm run dev`
6. Open http://localhost:5173

## Features
- Start/stop voice conversation, mute/unmute
- WebRTC browser-to-OpenAI streaming
- Server-side session credentials; API key stays in backend
- Server VAD turn detection and interruption
- Live text transcripts (subject to Realtime event availability)

## Status
Prototype code, not yet end-to-end tested with a real API key or browser microphone.
Do not commit `.env` or API keys.
