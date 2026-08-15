import { ContentType, ModelType, type Action, type HandlerCallback, type HandlerOptions, type IAgentRuntime, type Memory, type Plugin, type Provider, type UUID } from "@elizaos/core";
import { decide, type SessionState } from "./policy.js";

export const IMAGE_ARCHIVE_TABLE = "conversation_improvement_images";
const POLICY_TABLE = "conversation_improvement_policy";
const DEFAULT_STATE: SessionState = { turn: 0, automaticCount: 0, casualStreak: 0 };

type ArchivedImage = { url: string; description?: string; tags?: string[] };
type Parameters = Record<string, unknown>;

function parameters(options?: HandlerOptions | Record<string, unknown>): Parameters {
  const value = options && "parameters" in options ? options.parameters : undefined;
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value));
}
function sessionKey(message: Memory): string { return message.sessionKey ?? String(message.roomId); }
function parseState(memory?: Memory): SessionState {
  try { return memory?.content.text ? JSON.parse(memory.content.text) as SessionState : { ...DEFAULT_STATE }; }
  catch { return { ...DEFAULT_STATE }; }
}
async function policyMemory(runtime: IAgentRuntime, message: Memory): Promise<Memory | undefined> {
  const entries = await runtime.getMemories({ tableName: POLICY_TABLE, roomId: message.roomId, limit: 20 });
  return entries.find((item) => item.sessionKey === sessionKey(message));
}
async function saveState(runtime: IAgentRuntime, message: Memory, existing: Memory | undefined, state: SessionState): Promise<void> {
  const content = { text: JSON.stringify(state), type: "conversation_improvement_policy_state" };
  if (existing?.id) {
    await runtime.updateMemory({ id: existing.id, content });
    return;
  }
  await runtime.createMemory({ entityId: message.entityId, roomId: message.roomId, worldId: message.worldId, agentId: runtime.agentId, sessionKey: sessionKey(message), content }, POLICY_TABLE, true);
}
async function archive(runtime: IAgentRuntime, message: Memory, image: ArchivedImage): Promise<void> {
  await runtime.createMemory({
    entityId: message.entityId, roomId: message.roomId, worldId: message.worldId, agentId: runtime.agentId,
    sessionKey: sessionKey(message), content: { text: JSON.stringify(image), type: "conversation_improvement_image", url: image.url },
  }, IMAGE_ARCHIVE_TABLE, true);
}
function parseImage(memory: Memory): ArchivedImage | undefined {
  try { return memory.content.text ? JSON.parse(memory.content.text) as ArchivedImage : undefined; } catch { return undefined; }
}
async function findImages(runtime: IAgentRuntime, message: Memory, query: string): Promise<ArchivedImage[]> {
  const memories = await runtime.getMemories({ tableName: IMAGE_ARCHIVE_TABLE, roomId: message.roomId, limit: 100 });
  const needle = query.toLocaleLowerCase();
  return memories.filter((item) => item.sessionKey === sessionKey(message)).map(parseImage).filter((item): item is ArchivedImage => Boolean(item)).filter((item) => !needle || JSON.stringify(item).toLocaleLowerCase().includes(needle));
}
async function deliver(callback: HandlerCallback | undefined, url: string, text: string, actionName: string): Promise<void> {
  if (!callback) throw new Error("This connector did not provide a delivery callback");
  await callback({ text, attachments: [{ id: `conversation-image-${Date.now()}`, url, title: text || "Conversation image", contentType: ContentType.IMAGE }] }, actionName);
}

export const policyProvider: Provider = {
  name: "conversationImprovementPolicy",
  description: "Per-message, per-conversation guidance for restrained visual reactions.",
  dynamic: true,
  position: 10,
  get: async (runtime, message) => {
    const existing = await policyMemory(runtime, message);
    const current = parseState(existing);
    const decision = decide(message.content.text ?? "", current, sessionKey(message));
    const next: SessionState = {
      ...current,
      turn: current.turn + 1,
      casualStreak: decision.allowed ? 0 : current.casualStreak + 1,
      automaticCount: current.automaticCount + (decision.kind === "automatic" ? 1 : 0),
      lastAutomaticTurn: decision.kind === "automatic" ? current.turn : current.lastAutomaticTurn,
    };
    await saveState(runtime, message, existing, next);
    const guidance = decision.allowed
      ? `${decision.kind === "explicit" ? "The user requested" : "Policy allows"} one image on this turn (${decision.reason}). Prefer a relevant archived image; generate only when needed, and do not send more than one.`
      : `Do not send or generate media on this turn (${decision.reason}). Continue with a concise text response.`;
    return { text: guidance, values: { mediaAllowed: decision.allowed, mediaKind: decision.kind, reason: decision.reason, turn: current.turn }, data: { decision, session: sessionKey(message) } };
  },
};

const archiveAction: Action = {
  name: "ARCHIVE_CONVERSATION_IMAGE", description: "Save an image URL and description in this conversation's image archive.", similes: ["SAVE_IMAGE", "REMEMBER_IMAGE"],
  parameters: [
    { name: "url", description: "Public or connector-readable image URL", required: true, schema: { type: "string" } },
    { name: "description", description: "What the image depicts", required: false, schema: { type: "string" } },
    { name: "tags", description: "Search tags", required: false, schema: { type: "array", items: { type: "string" } } },
  ],
  validate: async () => true,
  handler: async (runtime, message, _state, options) => {
    const p = parameters(options); const url = String(p.url ?? "");
    if (!url) return { success: false, error: "url is required" };
    await archive(runtime, message, { url, description: typeof p.description === "string" ? p.description : undefined, tags: Array.isArray(p.tags) ? p.tags.map(String) : undefined });
    return { success: true, text: "Image archived for this conversation.", data: { url } };
  },
};

const searchAction: Action = {
  name: "SEARCH_CONVERSATION_IMAGES", description: "Search images archived in the current conversation.", similes: ["FIND_IMAGE", "SEARCH_IMAGES"],
  parameters: [{ name: "query", description: "Words from the image description or tags", required: false, schema: { type: "string" } }],
  validate: async () => true,
  handler: async (runtime, message, _state, options) => {
    const matches = await findImages(runtime, message, String(parameters(options).query ?? ""));
    return { success: true, text: matches.length ? `Found ${matches.length} archived image(s).` : "No matching archived images.", data: { matches } };
  },
};

const sendAction: Action = {
  name: "SEND_CONVERSATION_IMAGE", description: "Deliver an image through the active ElizaOS connector callback. Use only when policy context permits it.", similes: ["SEND_IMAGE", "SHOW_IMAGE"],
  parameters: [
    { name: "url", description: "Image URL to deliver", required: true, schema: { type: "string" } },
    { name: "text", description: "Optional caption", required: false, schema: { type: "string" } },
  ],
  validate: async () => true,
  handler: async (_runtime, _message, _state, options, callback) => {
    const p = parameters(options); const url = String(p.url ?? "");
    if (!url) return { success: false, error: "url is required" };
    try { await deliver(callback, url, String(p.text ?? ""), "SEND_CONVERSATION_IMAGE"); return { success: true, text: "Image delivered.", data: { url } }; }
    catch (error) { return { success: false, error: error as Error }; }
  },
};

function generatedUrl(result: unknown): string | undefined {
  if (!Array.isArray(result)) return undefined;
  const first: unknown = result[0];
  return first && typeof first === "object" && "url" in first && typeof first.url === "string" ? first.url : undefined;
}

const generateAction: Action = {
  name: "GENERATE_CONVERSATION_IMAGE", description: "Generate one image with the configured ElizaOS IMAGE model, archive it, and deliver it through the active connector callback. Use only when policy context permits it.", similes: ["GENERATE_IMAGE", "CREATE_IMAGE"],
  parameters: [
    { name: "prompt", description: "Image generation prompt", required: true, schema: { type: "string" } },
    { name: "text", description: "Optional delivery caption", required: false, schema: { type: "string" } },
  ],
  validate: async () => true,
  handler: async (runtime, message, _state, options, callback) => {
    const p = parameters(options); const prompt = String(p.prompt ?? "");
    if (!prompt) return { success: false, error: "prompt is required" };
    try {
      const result = await runtime.useModel(ModelType.IMAGE, { prompt, count: 1 });
      const url = generatedUrl(result);
      if (!url) return { success: false, error: "The configured IMAGE model returned no deliverable URL" };
      await archive(runtime, message, { url, description: prompt, tags: ["generated"] });
      await deliver(callback, url, String(p.text ?? ""), "GENERATE_CONVERSATION_IMAGE");
      return { success: true, text: "Image generated, archived, and delivered.", data: { url } };
    } catch (error) { return { success: false, error: error as Error }; }
  },
};

const plugin: Plugin = {
  name: "conversation-improvement",
  description: "Restrained per-message visual expression with conversation-scoped policy state and image archive.",
  providers: [policyProvider],
  actions: [archiveAction, searchAction, sendAction, generateAction],
};

export default plugin;
