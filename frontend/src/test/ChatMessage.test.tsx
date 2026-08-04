import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ChatMessage, normalizeMathDelimiters } from "../components/ChatMessage";
import type { Message } from "../types";

const message: Message = {
  id: "math-1",
  role: "assistant",
  content: String.raw`行内公式 \(x^2 + y^2\)。

\[Y = W^T X\]

| 步骤 | 操作 |
| --- | --- |
| 1 | 中心化 |`,
  status: "completed",
  request_id: "request-1",
  sources: [],
  metadata: {},
  created_at: "2026-07-19T12:00:00Z",
};

describe("ChatMessage rich Markdown", () => {
  afterEach(cleanup);

  it("normalizes common LaTeX delimiters without changing inline code", () => {
    expect(normalizeMathDelimiters("\\(x\\) and `\\(code\\)`"))
      .toBe("$x$ and `\\(code\\)`");
  });

  it("renders inline/block math with KaTeX and GFM tables", () => {
    const { container } = render(<ChatMessage message={message} onSources={() => undefined} />);

    expect(container.querySelectorAll(".katex").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "步骤" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "中心化" })).toBeInTheDocument();
  });
});
