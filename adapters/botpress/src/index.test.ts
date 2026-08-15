import { describe, expect, it, vi } from "vitest";
import { beforeIncomingMessage, plugin } from "./index.js";

function repos() {
  const session = new Map<string, any>();
  const archive = new Map<string, any>();
  const repo = (map: Map<string, any>) => ({
    getOrSet: vi.fn(async (id: string, value: any) => { if (!map.has(id)) map.set(id, structuredClone(value)); return structuredClone(map.get(id)); }),
    set: vi.fn(async (id: string, value: any) => { map.set(id, structuredClone(value)); }),
  });
  return { states: { conversation: { session: repo(session), archive: repo(archive) } }, session, archive };
}

const config = { enabled: true, probability: 0.32, playfulProbability: 0.65, forceAfterCasualTurns: 4, cooldownTurns: 5, maxPerConversation: 20 };
const action = (name: string) => (plugin as any).props.actions[name];

describe("Botpress native plugin", () => {
  it("defines conversation states and all orchestration actions", () => {
    expect(Object.keys((plugin as any).props.actions).sort()).toEqual(["archiveMedia", "generateMedia", "getPolicy", "searchMedia", "sendMedia"]);
  });

  it("evaluates incoming text in a conversation hook and persists scoped policy", async () => {
    const fixture = repos();
    await beforeIncomingMessage({ data: { type: "text", payload: { text: "帮我调试代码" } }, conversation: { id: "c1" }, configuration: config, states: fixture.states } as never);
    expect(fixture.session.get("c1")).toMatchObject({ turn: 1, casualStreak: 1, lastUserText: "帮我调试代码" });
    expect(fixture.session.get("c1").policy).toContain("sensitive_context");
  });

  it("archives, deduplicates, and searches conversation media", async () => {
    const fixture = repos();
    const first = await action("archiveMedia")({ input: { conversationId: "c1", url: "https://cdn.test/a.png", kind: "image", tags: ["Cute", "cat"], source: "generated" }, states: fixture.states });
    const second = await action("archiveMedia")({ input: { conversationId: "c1", url: "https://cdn.test/a.png", kind: "image", tags: ["reaction"], source: "generated" }, states: fixture.states });
    const found = await action("searchMedia")({ input: { conversationId: "c1", query: "cute reaction", limit: 5 }, states: fixture.states });
    expect(first.created).toBe(true);
    expect(second.created).toBe(false);
    expect(found.items).toHaveLength(1);
    expect(found.items[0].tags).toEqual(["cat", "cute", "reaction"]);
  });

  it.each([
    ["image", { imageUrl: "https://cdn.test/a.png", title: "A" }],
    ["file", { fileUrl: "https://cdn.test/a.pdf", title: "A" }],
  ])("sends native %s message payloads", async (kind, payload) => {
    const result = await action("sendMedia")({ input: { conversationId: "c1", userId: "u1", url: Object.values(payload)[0], kind, title: "A" } });
    expect(result).toEqual({ kind, payload });
  });

  it("orchestrates a configured generation action, archive, and delivery", async () => {
    const fixture = repos();
    const callAction = vi.fn(async () => ({ output: { imageUrl: "https://cdn.test/generated.png", provider: "test" } }));
    const result = await action("generateMedia")({ input: { conversationId: "c1", userId: "u1", actionType: "image-generator:generate", prompt: "a cheerful reaction", actionInput: { style: "photo" }, kind: "image", tags: ["cheerful"], archive: true, send: false }, client: { callAction }, states: fixture.states });
    expect(callAction).toHaveBeenCalledWith({ type: "image-generator:generate", input: { style: "photo", prompt: "a cheerful reaction" } });
    expect(result).toMatchObject({ url: "https://cdn.test/generated.png" });
    expect(fixture.archive.get("c1").items).toHaveLength(1);
  });
});
