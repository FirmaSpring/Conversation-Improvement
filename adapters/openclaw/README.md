# OpenClaw adapter

Native OpenClaw adapter for Conversation-Improvement.

## Implemented

- `message_received` and `before_prompt_build` hooks for per-conversation policy decisions
- `conversation_image_search`
- `conversation_image_archive`
- `conversation_image_send` using OpenClaw's validated `sendSessionAttachment` route
- isolated per-session cooldown and usage state
- the same JSON image index shape used by the project core

The adapter deliberately does not copy an image provider. The policy tells OpenClaw to use its configured `image_generate` capability when a new image is genuinely required, then archive and send the result through plugin tools.

## Build and test

```bash
npm install
npm test
npm run build
```

Validated against the public `openclaw@2026.8.1-beta.1` SDK. A real Gateway and messaging-channel acceptance test is still required before marking the adapter production-verified.

## Install during development

Install or link this package using OpenClaw's native plugin installer, then restart the Gateway. The package declares `src/index.ts` for source/workspace development and `dist/index.js` for built runtime loading.
