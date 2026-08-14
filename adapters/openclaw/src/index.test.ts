import { describe, expect, it, vi } from "vitest";
import { createAdapter } from "./index.js";

function fakeApi() {
  const hooks = new Map<string, Function>();
  const tools = new Map<string, any>();
  const sendSessionAttachment = vi.fn(async () => ({ ok: true, channel: "telegram", deliveredTo: "chat", count: 1 }));
  const api: any = {
    pluginConfig: { dataDirectory: ".tmp-openclaw-test" },
    on(name: string, handler: Function) { hooks.set(name, handler); },
    registerTool(factory: Function, options: { name: string }) {
      tools.set(options.name, factory({ sessionKey: "session-1" }));
    },
    session: { workflow: { sendSessionAttachment } },
  };
  return { api, hooks, tools, sendSessionAttachment };
}

describe("OpenClaw adapter", () => {
  it("registers conversation hooks and image tools", () => {
    const fixture = fakeApi();
    createAdapter(fixture.api);
    expect([...fixture.hooks.keys()].sort()).toEqual(["before_prompt_build", "message_received"]);
    expect([...fixture.tools.keys()].sort()).toEqual([
      "conversation_image_archive",
      "conversation_image_search",
      "conversation_image_send",
    ]);
  });

  it("blocks automatic media for professional coding turns", async () => {
    const fixture = fakeApi();
    createAdapter(fixture.api);
    await fixture.hooks.get("message_received")?.({ content: "帮我调试代码并运行测试" }, { sessionKey: "session-1" });
    const result = await fixture.hooks.get("before_prompt_build")?.(
      { prompt: "帮我调试代码并运行测试", messages: [] },
      { sessionKey: "session-1" },
    );
    expect(result.appendContext).toContain("Automatic media is blocked");
    expect(result.appendContext).toContain("sensitive_context");
  });

  it("uses the active session route to send an archived image", async () => {
    const fixture = fakeApi();
    createAdapter(fixture.api);
    const tool = fixture.tools.get("conversation_image_send");
    const result = await tool.execute("call-1", { path: "C:/tmp/reaction.png", text: "hello" });
    expect(fixture.sendSessionAttachment).toHaveBeenCalledWith({
      sessionKey: "session-1",
      files: [{ path: "C:\\tmp\\reaction.png" }],
      text: "hello",
    });
    expect(result.details.success).toBe(true);
  });
});
