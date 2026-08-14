import { definePluginEntry, type OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";
import { readFile, writeFile, mkdir, copyFile, stat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { basename, extname, join, resolve } from "node:path";
import { decide, type SessionState } from "./policy.js";

const INDEX_FILE = "index.json";

type Config = {
  enabled?: boolean;
  probability?: number;
  playfulProbability?: number;
  forceAfterCasualTurns?: number;
  cooldownTurns?: number;
  maxPerSession?: number;
  dataDirectory?: string;
};

type ImageRow = {
  id: string;
  path: string;
  createdAt: string;
  tags: string[];
  source: string;
};

function textResult(value: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(value) }], details: value };
}

function configOf(api: OpenClawPluginApi): Required<Config> {
  const raw = (api.pluginConfig ?? {}) as Config;
  return {
    enabled: raw.enabled ?? true,
    probability: raw.probability ?? 0.32,
    playfulProbability: raw.playfulProbability ?? 0.65,
    forceAfterCasualTurns: raw.forceAfterCasualTurns ?? 4,
    cooldownTurns: raw.cooldownTurns ?? 5,
    maxPerSession: raw.maxPerSession ?? 20,
    dataDirectory: resolve(raw.dataDirectory ?? join(process.cwd(), ".openclaw", "conversation-improvement")),
  };
}

async function loadRows(root: string): Promise<ImageRow[]> {
  try {
    return JSON.parse(await readFile(join(root, INDEX_FILE), "utf8")) as ImageRow[];
  } catch {
    return [];
  }
}

async function saveRows(root: string, rows: ImageRow[]) {
  await mkdir(root, { recursive: true });
  await writeFile(join(root, INDEX_FILE), JSON.stringify(rows, null, 2), "utf8");
}

async function archive(root: string, inputPath: string, tags: string[], source: string): Promise<ImageRow> {
  const sourcePath = resolve(inputPath);
  await stat(sourcePath);
  const bytes = await readFile(sourcePath);
  const id = createHash("sha256").update(bytes).digest("hex");
  const rows = await loadRows(root);
  const existing = rows.find((row) => row.id === id);
  if (existing) {
    existing.tags = [...new Set([...existing.tags, ...tags])].sort();
    await saveRows(root, rows);
    return existing;
  }
  const media = join(root, "media");
  await mkdir(media, { recursive: true });
  const target = join(media, `${new Date().toISOString().slice(0, 10)}_${id.slice(0, 12)}${extname(sourcePath)}`);
  await copyFile(sourcePath, target);
  const row: ImageRow = { id, path: target, createdAt: new Date().toISOString(), tags: [...new Set(tags)].sort(), source };
  rows.push(row);
  await saveRows(root, rows);
  return row;
}

function searchRows(rows: ImageRow[], query: string, limit: number): ImageRow[] {
  const terms = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return rows
    .filter((row) => terms.every((term) => row.tags.join(" ").toLocaleLowerCase().includes(term)))
    .slice(-Math.max(1, Math.min(limit, 20)))
    .reverse();
}

export function createAdapter(api: OpenClawPluginApi) {
  const config = configOf(api);
  const states = new Map<string, SessionState>();
  const prompts = new Map<string, string>();

  api.on("message_received", (event, ctx) => {
    const sessionKey = ctx.sessionKey ?? "default";
    prompts.set(sessionKey, event.content);
  });

  api.on("before_prompt_build", (event, ctx) => {
    if (!config.enabled) return;
    const sessionKey = ctx.sessionKey ?? "default";
    const previous = states.get(sessionKey) ?? { turn: 0, automaticCount: 0, casualStreak: 0 };
    const current = { ...previous, turn: previous.turn + 1 };
    const message = prompts.get(sessionKey) ?? event.prompt;
    const decision = decide(message, current, { ...config, sessionKey });
    current.casualStreak = decision.kind === "automatic" ? 0 : previous.casualStreak + 1;
    states.set(sessionKey, current);
    const policy = decision.kind === "explicit"
      ? "This is an explicit image request. Search archived media for historical wording; generate only when the user asks for a new/current image."
      : decision.allowed
        ? "A restrained visual reaction is allowed. Search conversation_image_search first; use image_generate only if no matching archived reaction exists, then archive it."
        : `Automatic media is blocked this turn (${decision.reason}). Reply with text unless the user explicitly requests media.`;
    return { appendContext: `Conversation-Improvement policy: ${policy}` };
  });

  api.registerTool((ctx) => ({
    name: "conversation_image_search",
    label: "Conversation image search",
    description: "Search archived conversation images by space-separated semantic tags.",
    parameters: {
      type: "object",
      properties: { query: { type: "string" }, limit: { type: "integer", minimum: 1, maximum: 20, default: 5 } },
      required: ["query"],
      additionalProperties: false,
    },
    async execute(_id, raw) {
      const params = raw as { query: string; limit?: number };
      const rows = searchRows(await loadRows(config.dataDirectory), params.query, params.limit ?? 5);
      return textResult({ success: true, images: rows });
    },
  }), { name: "conversation_image_search" });

  api.registerTool((ctx) => ({
    name: "conversation_image_archive",
    label: "Conversation image archive",
    description: "Permanently archive one local image or GIF with semantic tags.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string" },
        tags: { type: "array", items: { type: "string" } },
        source: { type: "string", default: "generated" },
      },
      required: ["path"],
      additionalProperties: false,
    },
    async execute(_id, raw) {
      const params = raw as { path: string; tags?: string[]; source?: string };
      return textResult({ success: true, image: await archive(config.dataDirectory, params.path, params.tags ?? [], params.source ?? "generated") });
    },
  }), { name: "conversation_image_archive" });

  api.registerTool((ctx) => ({
    name: "conversation_image_send",
    label: "Send archived conversation image",
    description: "Send one local archived image or GIF to the active OpenClaw conversation.",
    parameters: {
      type: "object",
      properties: { path: { type: "string" }, text: { type: "string" } },
      required: ["path"],
      additionalProperties: false,
    },
    async execute(_id, raw) {
      const params = raw as { path: string; text?: string };
      if (!ctx.sessionKey) return textResult({ success: false, error: "No active sessionKey" });
      const result = await api.session.workflow.sendSessionAttachment({
        sessionKey: ctx.sessionKey,
        files: [{ path: resolve(params.path) }],
        text: params.text,
      });
      if (result.ok) {
        const state = states.get(ctx.sessionKey);
        if (state) states.set(ctx.sessionKey, { ...state, lastAutomaticTurn: state.turn, automaticCount: state.automaticCount + 1 });
      }
      return textResult({ success: result.ok, result });
    },
  }), { name: "conversation_image_send" });
}

const plugin: ReturnType<typeof definePluginEntry> = definePluginEntry({
  id: "conversation-improvement",
  name: "Conversation Improvement",
  description: "Restrained visual reactions and persistent image memory for OpenClaw.",
  register(api) {
    createAdapter(api);
  },
});

export default plugin;
