import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";


const user = { id: "u1", username: "tester", email: "tester@example.test", display_name: "测试用户",
  role: "user", is_active: true, created_at: "2026-07-18T12:00:00", last_login_at: null };
const json = (data: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(data), {
  status, headers: { "Content-Type": "application/json" },
}));

describe("web application", () => {
  beforeEach(() => { vi.restoreAllMocks(); window.history.pushState({}, "", "/"); });
  afterEach(cleanup);

  it("redirects an unauthenticated visitor to login", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ detail: "unauthorized" }, 401)));
    window.history.pushState({}, "", "/chat"); render(<App />);
    expect(await screen.findByRole("heading", { name: "欢迎回来" })).toBeInTheDocument();
  });

  it("validates registration password confirmation", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ detail: "unauthorized" }, 401)));
    window.history.pushState({}, "", "/register"); render(<App />); const actor = userEvent.setup();
    await screen.findByRole("heading", { name: "创建账号" });
    await actor.type(screen.getByLabelText("用户名"), "tester");
    await actor.type(screen.getByLabelText("显示名称"), "测试用户");
    await actor.type(screen.getByLabelText("邮箱"), "tester@example.test");
    await actor.type(screen.getByLabelText("密码"), "Example123");
    await actor.type(screen.getByLabelText("确认密码"), "Example124");
    await actor.click(screen.getByRole("button", { name: /创建账号/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("两次输入的密码不一致");
  });

  it("logs in with cookie credentials and opens chat", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _options?: RequestInit) => {
      const path = String(input);
      if (path.endsWith("/api/auth/me")) return json({ detail: "unauthorized" }, 401);
      if (path.endsWith("/api/auth/login")) return json(user);
      if (path.endsWith("/api/chat/sessions")) return json([]);
      return json({});
    });
    vi.stubGlobal("fetch", fetchMock); window.history.pushState({}, "", "/login"); render(<App />); const actor = userEvent.setup();
    await actor.type(await screen.findByLabelText("用户名或邮箱"), "tester");
    await actor.type(screen.getByLabelText("密码"), "Example123");
    await actor.click(screen.getByRole("button", { name: /进入工作台/ }));
    expect(await screen.findByRole("heading", { name: "知识，从一个好问题开始" }, { timeout: 15_000 })).toBeInTheDocument();
    const loginCall = fetchMock.mock.calls.find(call => String(call[0]).endsWith("/api/auth/login"));
    expect(loginCall?.[1]).toMatchObject({ credentials: "include" });
  });

  it("sends a question and displays the answer source", async () => {
    const session = { id: "c1", title: "新对话", created_at: "2026-07-18T12:00:00", updated_at: "2026-07-18T12:00:00", last_message_at: null };
    let sent = false;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
      const path = String(input); const method = options?.method || "GET";
      if (path.endsWith("/api/auth/me")) return json(user);
      if (path.endsWith("/api/chat/sessions") && method === "GET") return json([session]);
      if (path.endsWith("/api/chat/sessions") && method === "POST") return json(session, 201);
      if (path.endsWith("/api/chat/sessions/c1/messages")) { sent = true; return json({ answer: "登录需要 username 和 password。", sources: [], runtime_mode: { llm: "mock" } }); }
      if (path.endsWith("/api/chat/sessions/c1")) return json({ ...session, messages: sent ? [
        { id: "m1", role: "user", content: "用户登录接口需要哪些参数？", status: "completed", request_id: null, sources: [], metadata: {}, created_at: "2026-07-18T12:00:00" },
        { id: "m2", role: "assistant", content: "登录需要 `username` 和 `password`。", status: "completed", request_id: "r1", sources: [{ title: "用户服务接口", source: "knowledge_base/api/user-service.md", snippet: "登录参数说明", score: .88 }], metadata: {}, created_at: "2026-07-18T12:00:01" },
      ] : [] });
      return json({});
    }));
    window.history.pushState({}, "", "/chat?session=c1"); render(<App />); const actor = userEvent.setup();
    await screen.findByRole("heading", { name: "知识，从一个好问题开始" }, { timeout: 15_000 });
    await actor.click(screen.getByRole("button", { name: /用户登录接口需要哪些参数/ }));
    expect(await screen.findByText(/登录需要/)).toBeInTheDocument();
    await actor.click(screen.getByRole("button", { name: /查看 1 个知识来源/ }));
    expect(await screen.findByRole("heading", { name: "用户服务接口" })).toBeInTheDocument();
  });
});
