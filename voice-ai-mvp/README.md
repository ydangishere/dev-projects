# Voice AI MVP

React + TypeScript frontend, NestJS backend, OpenAI Realtime API over WebRTC.

## Conversation flow

End-to-end voice flow (conceptual): mic audio → streaming STT → LLM → streaming TTS → voice output; server VAD handles turn detection/barge-in, and WebRTC carries the session.

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

---

## Solution Architecture Review (implementation-backed)

**Business problem:** Provide low-latency spoken interaction while keeping a long-lived OpenAI API key off the browser.

**Implemented design flow (one line):** Browser microphone → NestJS short-lived session credential → WebRTC session with OpenAI Realtime → Audio response + transcript events → React UI.

**Architecture decisions**
- **Separation of trust:** The NestJS backend holds the API key and requests an ephemeral client secret; only the short-lived value reaches the browser for WebRTC negotiation.
- **Interaction:** React manages microphone tracks, peer connection, data channel, server VAD (voice activity detection), interruption, lifecycle cleanup and streaming transcript events.
- **Trade-off:** Realtime WebRTC reduces custom STT/TTS orchestration but makes runtime quality, latency, audio-event compatibility and provider cost dependent on the Realtime API.
- **Evaluation plan:** Measure connection-success rate, turn latency, interruptions, transcript accuracy, dropped calls and cost/minute only after live testing.
- **Production path:** Add authentication, consent and retention rules, abuse/rate limits, credential throttling, reconnect strategy, supported browser matrix, monitoring and automated end-to-end tests.

**RAG status:** No document retrieval, embeddings or vector-based RAG is implemented.

**Status:** Frontend/backend prototype code only; README explicitly states it has **not** been end-to-end tested with a live API key and microphone.
