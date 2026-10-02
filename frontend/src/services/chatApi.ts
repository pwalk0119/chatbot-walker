// Typed client for the chatbot backend (T024). Types mirror contracts/chat-api.yaml.

export type Campus = "Hammond" | "Westville";
export type AcademicLevel = "Undergraduate" | "Graduate";

export interface Conversation {
  id: string;
  campus?: Campus | null;
  academicLevel?: AcademicLevel | null;
  status: "active" | "ended";
}

export interface StudentMessageHints {
  statedCampus?: Campus | null;
  statedAcademicLevel?: AcademicLevel | null;
}

export interface Citation {
  sourceDocumentId?: string;
  title: string;
  url: string;
}

export interface DepartmentContact {
  name: string;
  contactMethod: string;
}

/** Direct cited answer (FR-001/FR-003). `citations` is never empty. */
export interface AnswerReply {
  type: "answer";
  responseText: string;
  citations: Citation[];
}

/** Asking for campus or academic level before answering (FR-004/FR-013). */
export interface ClarifyingQuestionReply {
  type: "clarifying_question";
  promptText: string;
  slot: "campus" | "academicLevel";
}

/** No confident answer; names a department instead (FR-008). */
export interface EscalationReply {
  type: "escalation";
  explanationText: string;
  department: DepartmentContact;
}

export type ChatbotReply = AnswerReply | ClarifyingQuestionReply | EscalationReply;

/** A non-2xx response from the backend. `status` is the HTTP status code. */
export class ChatApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ChatApiError";
  }
}

export interface ChatApi {
  startConversation(): Promise<Conversation>;
  sendMessage(
    conversationId: string,
    text: string,
    hints?: StudentMessageHints,
  ): Promise<ChatbotReply>;
}

/** Create a client for the backend at `baseUrl` (e.g. "https://chat.pnw.edu"). */
export function createChatApi(baseUrl: string, fetchImpl: typeof fetch = fetch): ChatApi {
  const root = baseUrl.replace(/\/+$/, "");

  async function request<T>(path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetchImpl(`${root}${path}`, {
        method: "POST",
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ChatApiError(
        0,
        "Could not reach the chatbot. Check your connection and try again.",
      );
    }
    if (!response.ok) {
      throw new ChatApiError(response.status, messageFor(response.status));
    }
    return (await response.json()) as T;
  }

  return {
    startConversation: () => request<Conversation>("/api/chat/conversations"),
    sendMessage: (conversationId, text, hints = {}) =>
      request<ChatbotReply>(
        `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
        { text, ...hints },
      ),
  };
}

function messageFor(status: number): string {
  switch (status) {
    case 404:
      return "This conversation has expired. Please start a new one.";
    case 422:
      return "Please type a question before sending.";
    default:
      return "Something went wrong. Please try again in a moment.";
  }
}
