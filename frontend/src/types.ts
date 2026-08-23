export interface Citation {
  url: string;
  title: string;
}

export interface ChatResponse {
  type: "answer" | "refusal";
  text: string;
  citation: Citation;
  footer: string;
  disclaimer: string;
  intent?: string | null;
}

export interface UserMessage {
  id: string;
  role: "user";
  text: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  response: ChatResponse;
}

export type ChatMessage = UserMessage | AssistantMessage;

export const EXAMPLE_QUESTIONS = [
  "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
  "What is the ELSS lock-in period for HDFC ELSS Tax Saver?",
  "What is the exit load on HDFC Mid Cap Fund Direct Growth?",
] as const;

export const WELCOME_TEXT =
  "Ask factual questions about 5 HDFC mutual fund schemes indexed from official Groww pages. I answer expense ratios, exit loads, lock-in periods, and similar facts — never investment advice.";
