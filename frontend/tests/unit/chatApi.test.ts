import { describe, expect, it, vi } from "vitest";

import { ChatApiError, createChatApi } from "../../src/services/chatApi";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("chatApi", () => {
  it("starts a conversation with a bodyless POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, { id: "c1", status: "active" }));
    const api = createChatApi("http://api.test/", fetchMock);

    const convo = await api.startConversation();

    expect(convo).toEqual({ id: "c1", status: "active" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/chat/conversations");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("sends text plus campus/level hints and returns the typed reply", async () => {
    const reply = { type: "clarifying_question", promptText: "Which campus?", slot: "campus" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, reply));
    const api = createChatApi("http://api.test", fetchMock);

    const result = await api.sendMessage("c/1", "When is drop day?", { statedCampus: "Hammond" });

    expect(result).toEqual(reply);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/chat/conversations/c%2F1/messages");
    expect(JSON.parse(init.body)).toEqual({ text: "When is drop day?", statedCampus: "Hammond" });
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
  });

  it.each([
    [404, "expired"],
    [422, "type a question"],
    [500, "Something went wrong"],
  ])("turns HTTP %i into a ChatApiError with a student-friendly message", async (status, text) => {
    const api = createChatApi(
      "http://api.test",
      vi.fn().mockResolvedValue(jsonResponse(status, {})),
    );
    const error = await api.sendMessage("c1", "hi").catch((e) => e);
    expect(error).toBeInstanceOf(ChatApiError);
    expect(error.status).toBe(status);
    expect(error.message).toContain(text);
  });

  it("reports a network failure as status 0", async () => {
    const api = createChatApi("http://api.test", vi.fn().mockRejectedValue(new TypeError("fail")));
    const error = await api.startConversation().catch((e) => e);
    expect(error).toBeInstanceOf(ChatApiError);
    expect(error.status).toBe(0);
  });
});
