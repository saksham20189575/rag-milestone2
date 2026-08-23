import type { ChatResponse } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export class ChatApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ChatApiError";
  }
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    let detail = "Unable to reach the server. Please try again.";
    try {
      const payload = (await response.json()) as { detail?: string | { msg?: string }[] };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      } else if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
        detail = payload.detail[0].msg;
      }
    } catch {
      // Keep generic message when body is not JSON.
    }
    throw new ChatApiError(detail, response.status);
  }

  return (await response.json()) as ChatResponse;
}
