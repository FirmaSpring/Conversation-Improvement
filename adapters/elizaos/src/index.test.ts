import type { HandlerCallback, IAgentRuntime, Memory } from "@elizaos/core";
import { describe, expect, it, vi } from "vitest";
import plugin, { IMAGE_ARCHIVE_TABLE } from "./index.js";

const id = "00000000-0000-4000-8000-000000000001" as const;
function message(text = "hello"): Memory { return { id, entityId: id, roomId: id, agentId: id, content: { text }, sessionKey: "discord:room-1" }; }
function runtime() {
  const memories: Record<string, Memory[]> = {};
  let nextId = 2;
  return {
    agentId: id,
    getMemories: vi.fn(async ({ tableName }: { tableName: string }) => memories[tableName] ?? []),
    createMemory: vi.fn(async (memory: Memory, tableName: string) => {
      const stored = { ...memory, id: `00000000-0000-4000-8000-${String(nextId++).padStart(12, "0")}` };
      (memories[tableName] ??= []).unshift(stored);
      return stored.id;
    }),
    updateMemory: vi.fn(async (memory: Memory) => {
      for (const entries of Object.values(memories)) {
        const index = entries.findIndex((entry) => entry.id === memory.id);
        if (index >= 0) entries[index] = { ...entries[index], ...memory };
      }
      return true;
    }),
    useModel: vi.fn(async () => [{ url: "https://example.test/generated.png" } as { url: string }]),
    _memories: memories,
  } as unknown as IAgentRuntime & { _memories: Record<string, Memory[]> };
}

const action = (name: string) => plugin.actions!.find((item) => item.name === name)!;

describe("ElizaOS native plugin", () => {
  it("exports current Plugin components", () => {
    expect(plugin.providers?.map((p) => p.name)).toEqual(["conversationImprovementPolicy"]);
    expect(plugin.actions?.map((a) => a.name)).toEqual(["ARCHIVE_CONVERSATION_IMAGE", "SEARCH_CONVERSATION_IMAGES", "SEND_CONVERSATION_IMAGE", "GENERATE_CONVERSATION_IMAGE"]);
  });

  it("participates per message and persists restrained policy state by conversation", async () => {
    const rt = runtime();
    const provider = plugin.providers![0];
    const result = await provider.get(rt, message("帮我调试代码并运行测试"), {} as never);
    expect(result.text).toContain("Do not send or generate media");
    expect(result.values?.reason).toBe("sensitive_context");
    expect(rt.createMemory).toHaveBeenCalled();
    const again = await provider.get(rt, message("帮我调试代码并运行测试"), {} as never);
    expect((rt._memories.conversation_improvement_policy ?? []).length).toBe(1);
    expect(again.values?.turn).toBe(1);
  });

  it("archives and searches images within the current conversation", async () => {
    const rt = runtime();
    await action("ARCHIVE_CONVERSATION_IMAGE").handler(rt, message(), {} as never, { parameters: { url: "https://example.test/cat.png", description: "sleepy cat" } });
    const result = await action("SEARCH_CONVERSATION_IMAGES").handler(rt, message(), {} as never, { parameters: { query: "sleepy" } });
    expect(result?.success).toBe(true);
    expect(result?.data?.matches).toHaveLength(1);
    expect(rt._memories[IMAGE_ARCHIVE_TABLE]).toHaveLength(1);
  });

  it("delivers archived media through the connector callback", async () => {
    const rt = runtime();
    const callback: HandlerCallback = vi.fn(async () => []);
    const result = await action("SEND_CONVERSATION_IMAGE").handler(rt, message(), {} as never, { parameters: { url: "https://example.test/cat.png", text: "for you" } }, callback);
    expect(callback).toHaveBeenCalledWith(expect.objectContaining({ text: "for you", attachments: [expect.objectContaining({ url: "https://example.test/cat.png", contentType: "image" })] }), "SEND_CONVERSATION_IMAGE");
    expect(result?.success).toBe(true);
  });

  it("uses the runtime IMAGE model then delivers and archives the result", async () => {
    const rt = runtime();
    const callback: HandlerCallback = vi.fn(async () => []);
    const result = await action("GENERATE_CONVERSATION_IMAGE").handler(rt, message("make it"), {} as never, { parameters: { prompt: "a tiny moon" } }, callback);
    expect(rt.useModel).toHaveBeenCalledWith("IMAGE", expect.objectContaining({ prompt: "a tiny moon" }));
    expect(callback).toHaveBeenCalled();
    expect(rt._memories[IMAGE_ARCHIVE_TABLE]).toHaveLength(1);
    expect(result?.success).toBe(true);
  });

  it("rejects missing required handler parameters without side effects", async () => {
    const rt = runtime();
    const callback: HandlerCallback = vi.fn(async () => []);
    const send = await action("SEND_CONVERSATION_IMAGE").handler(rt, message(), undefined, { parameters: {} }, callback);
    const generate = await action("GENERATE_CONVERSATION_IMAGE").handler(rt, message(), undefined, { parameters: {} }, callback);
    expect(send).toMatchObject({ success: false, error: "url is required" });
    expect(generate).toMatchObject({ success: false, error: "prompt is required" });
    expect(callback).not.toHaveBeenCalled();
    expect(rt.useModel).not.toHaveBeenCalled();
  });
});
