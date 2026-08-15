# ElizaOS adapter

Native ElizaOS plugin for Conversation-Improvement.

## Verified contract

- Dynamic per-message policy is provided through the ElizaOS provider API.
- Conversation state and media archive are stored with ElizaOS memory APIs.
- Actions cover policy lookup, archive, search, delivery through `HandlerCallback`, and image generation through `runtime.useModel(ModelType.IMAGE)`.
- The package is pinned to `@elizaos/core@2.0.0-alpha.77`; ElizaOS alpha APIs can change.

## Install in an ElizaOS project

```bash
npm install @firmaspring/elizaos-conversation-improvement @elizaos/core@2.0.0-alpha.77
```

Register the default export in the ElizaOS character or runtime plugin list.

## Verify locally

```bash
npm install
npm test
npm run build
```

The included tests use a typed in-memory runtime. They verify policy state, archive/search, callback delivery, and image-model orchestration. A live ElizaOS database, connector, and image provider remain host-level acceptance tests.
