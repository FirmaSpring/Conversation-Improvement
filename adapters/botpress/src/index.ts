import { PluginDefinition, z } from "@botpress/sdk";
import { Plugin, type HookHandlerProps } from "../.botpress/implementation/index.js";
import { decide, type SessionState } from "./policy.js";

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

const emptySession = (): SessionState => ({ turn: 0, automaticCount: 0, casualStreak: 0 });
const policyText = (decision: ReturnType<typeof decide>) => decision.kind === "explicit"
  ? "Explicit media request: search archived media first; generate only when a new/current asset was requested."
  : decision.allowed
    ? "A restrained visual reaction is allowed: search first, generate only if no suitable archive match exists, then archive it."
    : `Automatic media is blocked this turn (${decision.reason}); use text unless media was explicitly requested.`;
const normalizeTags = (tags: string[]) => [...new Set(tags.map((tag) => tag.trim().toLocaleLowerCase()).filter(Boolean))].sort();
const makeId = (value: string) => { let hash = 2166136261; for (const c of value) { hash ^= c.charCodeAt(0); hash = Math.imul(hash, 16777619); } return `media_${(hash >>> 0).toString(16).padStart(8, "0")}`; };
const extractText = (data: { type: string; payload: unknown }) => data.type === "text" && typeof (data.payload as { text?: unknown })?.text === "string" ? (data.payload as { text: string }).text : "";
const extractUrl = (raw: Record<string, unknown>, kind: "image" | "file") => {
  const keys = kind === "image" ? ["imageUrl", "url"] : ["fileUrl", "url"];
  for (const key of keys) if (typeof raw[key] === "string") return raw[key] as string;
  const nested = raw.output;
  if (nested && typeof nested === "object") return extractUrl(nested as Record<string, unknown>, kind);
  throw new Error(`Generation action did not return ${keys.join(" or ")}`);
};

async function archive(states: any, input: { conversationId: string; url: string; kind: "image" | "file"; title?: string; tags: string[]; source: string }) {
  const repo = states.conversation.archive;
  const current = await repo.getOrSet(input.conversationId, { items: [] });
  const id = makeId(`${input.kind}:${input.url}`);
  const existing = current.items.find((item: MediaItem) => item.id === id);
  if (existing) {
    existing.tags = normalizeTags([...existing.tags, ...input.tags]);
    if (input.title) existing.title = input.title;
    await repo.set(input.conversationId, current);
    return { item: existing, created: false };
  }
  const item: MediaItem = { id, url: input.url, kind: input.kind, ...(input.title ? { title: input.title } : {}), tags: normalizeTags(input.tags), source: input.source, createdAt: new Date().toISOString() };
  await repo.set(input.conversationId, { items: [...current.items, item] });
  return { item, created: true };
}

export const plugin = new Plugin({
  actions: {
    async getPolicy({ input, states }) {
      const state = await states.conversation.session.getOrSet(input.conversationId, emptySession());
      return { policy: state.policy ?? "No incoming text has been evaluated for this conversation yet.", state: { turn: state.turn, automaticCount: state.automaticCount, casualStreak: state.casualStreak } };
    },
    async archiveMedia({ input, states }) {
      return archive(states, { ...input, kind: input.kind ?? "image", tags: input.tags ?? [], source: input.source ?? "generated" });
    },
    async searchMedia({ input, states }) {
      const { items } = await states.conversation.archive.getOrSet(input.conversationId, { items: [] });
      const terms = input.query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
      return { items: items.filter((item) => (!input.kind || item.kind === input.kind) && terms.every((term) => `${item.title ?? ""} ${item.tags.join(" ")} ${item.source}`.toLocaleLowerCase().includes(term))).slice(-(input.limit ?? 5)).reverse() };
    },
    async sendMedia({ input }) {
      const kind = input.kind ?? "image";
      const payload = kind === "image"
        ? { imageUrl: input.url, ...(input.title ? { title: input.title } : {}) }
        : { fileUrl: input.url, ...(input.title ? { title: input.title } : {}) };
      return { kind, payload };
    },
    async generateMedia({ input, client, states }) {
      const kind = input.kind ?? "image";
      const tags = input.tags ?? [];
      const result = await client.callAction({ type: input.actionType, input: { ...(input.actionInput ?? {}), prompt: input.prompt } });
      const raw = result.output as Record<string, unknown>;
      const url = extractUrl(raw, kind);
      const archived = input.archive !== false ? await archive(states, { conversationId: input.conversationId, url, kind, title: input.title, tags, source: `action:${input.actionType}` }) : undefined;
      return { url, ...(archived ? { item: archived.item } : {}), raw };
    },
  },
});

export const beforeIncomingMessage = async ({ data, conversation, configuration, states }: HookHandlerProps["before_incoming_message"]) => {
  if (!configuration.enabled || !conversation) return { data };
  const text = extractText(data);
  if (!text) return { data };
  const previous = await states.conversation.session.getOrSet(conversation.id, emptySession());
  const current = { ...previous, turn: previous.turn + 1, lastUserText: text };
  const decision = decide(text, current, {
    probability: configuration.probability ?? 0.32,
    playfulProbability: configuration.playfulProbability ?? 0.65,
    forceAfterCasualTurns: configuration.forceAfterCasualTurns ?? 4,
    cooldownTurns: configuration.cooldownTurns ?? 5,
    maxPerSession: configuration.maxPerConversation ?? 20,
    sessionKey: conversation.id,
  });
  current.casualStreak = decision.kind === "automatic" ? 0 : previous.casualStreak + 1;
  current.policy = policyText(decision);
  await states.conversation.session.set(conversation.id, current);
  return { data };
};

export const afterOutgoingMessage = async ({ data, states }: HookHandlerProps["after_outgoing_message"]) => {
  if (data.message.type !== "image" && data.message.type !== "file") return { data };
  const state = await states.conversation.session.getOrSet(data.message.conversationId, emptySession());
  await states.conversation.session.set(data.message.conversationId, { ...state, lastAutomaticTurn: state.turn, automaticCount: state.automaticCount + 1 });
  return { data };
};

plugin.on.beforeIncomingMessage("*", beforeIncomingMessage);
plugin.on.afterOutgoingMessage("*", afterOutgoingMessage);

export default plugin;
