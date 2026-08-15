# Botpress adapter

Native Botpress plugin module for Conversation-Improvement.

## Verified contract

- Uses `PluginDefinition`, conversation-scoped `session` and `archive` states, actions, and incoming/outgoing message hooks.
- The build invokes the official Botpress CLI code generator to produce `.botpress` implementation types from `src/definition.ts`, then compiles the strongly typed implementation.
- Actions provide policy lookup, archive, search, media-card payload preparation, and configured-generation orchestration.
- Image payloads use `{ imageUrl, title? }`; file payloads use `{ fileUrl, title? }`.

## Important media boundary

A standalone Botpress Plugin does not itself declare a channel Integration. Therefore it cannot statically type a concrete `client.createMessage` result for every host bot. `sendMedia` deliberately **prepares** the native image/file payload instead of sending it. The host Bot must use its configured channel Integration to create the actual message/card. This is a deliberate limitation, not a missing type cast.

## Use from a Botpress project

Copy or install this module into the Botpress project that owns the channel integration. Register its plugin definition and implementation with that host project, then connect the returned `sendMedia` payload to the host bot's integration-specific message action.

## Verify locally

```bash
npm install
npm test
npm run build
```

`npm run build` regenerates `.botpress` types with the official `@botpress/cli` generator before compiling. The test suite covers policy persistence, archive/search, image/file payload preparation, and generation orchestration. A real Botpress Cloud bot plus a configured channel Integration remains the acceptance test for delivery.
