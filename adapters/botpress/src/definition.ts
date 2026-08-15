import { PluginDefinition, z } from "@botpress/sdk";

export type MediaItem = {
  id: string;
  url: string;
  kind: "image" | "file";
  title?: string;
  tags: string[];
  source: string;
  createdAt: string;
};

const mediaSchema = z.object({
  id: z.string(), url: z.string(), kind: z.enum(["image", "file"]), title: z.string().optional(),
  tags: z.array(z.string()), source: z.string(), createdAt: z.string(),
});

export const definition = new PluginDefinition({
  name: "conversation-improvement",
  version: "0.1.0",
  title: "Conversation Improvement",
  description: "Restrained visual reactions and persistent, conversation-scoped media memory.",
  configuration: { schema: z.object({
    enabled: z.boolean().default(true),
    probability: z.number().min(0).max(1).default(0.32),
    playfulProbability: z.number().min(0).max(1).default(0.65),
    forceAfterCasualTurns: z.number().int().min(1).default(4),
    cooldownTurns: z.number().int().min(0).default(5),
    maxPerConversation: z.number().int().min(0).default(20),
  }) },
  states: {
    session: { type: "conversation", schema: z.object({
      turn: z.number(), lastAutomaticTurn: z.number().optional(), automaticCount: z.number(),
      casualStreak: z.number(), lastUserText: z.string().optional(), policy: z.string().optional(),
    }) },
    archive: { type: "conversation", schema: z.object({ items: z.array(mediaSchema) }) },
  },
  actions: {
    getPolicy: {
      title: "Get media policy", description: "Read the current conversation media policy.",
      input: { schema: z.object({ conversationId: z.string() }) },
      output: { schema: z.object({ policy: z.string(), state: z.object({ turn: z.number(), automaticCount: z.number(), casualStreak: z.number() }) }) },
    },
    archiveMedia: {
      title: "Archive media", description: "Archive an image or file URL with semantic tags in conversation-scoped state.",
      input: { schema: z.object({ conversationId: z.string(), url: z.string(), kind: z.enum(["image", "file"]).default("image"), title: z.string().optional(), tags: z.array(z.string()).default([]), source: z.string().default("generated") }) },
      output: { schema: z.object({ item: mediaSchema, created: z.boolean() }) },
    },
    searchMedia: {
      title: "Search media", description: "Search archived conversation media by space-separated tags.",
      input: { schema: z.object({ conversationId: z.string(), query: z.string(), limit: z.number().int().min(1).max(20).default(5), kind: z.enum(["image", "file"]).optional() }) },
      output: { schema: z.object({ items: z.array(mediaSchema) }) },
    },
    sendMedia: {
      title: "Prepare media", description: "Return a Botpress image/file card payload for the host bot to send through its configured integration.",
      input: { schema: z.object({ conversationId: z.string(), userId: z.string(), url: z.string(), kind: z.enum(["image", "file"]).default("image"), title: z.string().optional() }) },
      output: { schema: z.object({ kind: z.enum(["image", "file"]), payload: z.record(z.string(), z.unknown()) }) },
    },
    generateMedia: {
      title: "Generate and deliver media", description: "Call a configured Botpress generation action, extract a URL, optionally archive it, and optionally send it.",
      input: { schema: z.object({ conversationId: z.string(), userId: z.string().optional(), actionType: z.string(), prompt: z.string(), actionInput: z.record(z.string(), z.unknown()).default({}), kind: z.enum(["image", "file"]).default("image"), title: z.string().optional(), tags: z.array(z.string()).default([]), archive: z.boolean().default(true), send: z.boolean().default(true) }) },
      output: { schema: z.object({ url: z.string(), item: mediaSchema.optional(), messageId: z.string().optional(), raw: z.record(z.string(), z.unknown()) }) },
    },
  },
});
