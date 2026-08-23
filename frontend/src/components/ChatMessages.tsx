import type { ChatResponse } from "../types";

interface UserBubbleProps {
  text: string;
}

export function UserBubble({ text }: UserBubbleProps) {
  return (
    <div className="flex w-full justify-end">
      <div className="max-w-[85%] rounded-t-xl rounded-bl-xl rounded-br-sm bg-primary-container px-5 py-4 text-white shadow-soft">
        <p className="whitespace-pre-wrap text-base leading-relaxed">{text}</p>
      </div>
    </div>
  );
}

interface AssistantBubbleProps {
  response: ChatResponse;
}

export function AssistantBubble({ response }: AssistantBubbleProps) {
  const isRefusal = response.type === "refusal";

  return (
    <div className="flex w-full justify-start gap-3">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-border-subtle bg-surface-white shadow-sm">
        <span className="material-symbols-outlined text-[18px] text-primary">smart_toy</span>
      </div>
      <div className="flex w-full max-w-[85%] flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
          Assistant
        </span>
        <div
          className={`flex flex-col gap-4 rounded-t-xl rounded-bl-sm rounded-br-xl border border-border-subtle bg-surface-white p-5 shadow-soft ${
            isRefusal ? "border-l-4 border-l-compliance-amber" : ""
          }`}
        >
          <div className={`flex items-start gap-3 ${isRefusal ? "" : "hidden"}`}>
            <span className="material-symbols-outlined mt-1 text-compliance-amber">policy</span>
            <p className="whitespace-pre-wrap text-base leading-relaxed text-text-primary">
              {response.text}
            </p>
          </div>
          {!isRefusal && (
            <p className="whitespace-pre-wrap text-base leading-relaxed text-text-primary">
              {response.text}
            </p>
          )}

          <div className="mt-2 flex items-center justify-between rounded-md border border-border-subtle bg-surface-bright p-3">
            <span className="flex min-w-0 items-center gap-2 text-sm text-text-secondary">
              <span className="material-symbols-outlined flex-shrink-0 text-[16px]">menu_book</span>
              <span className="truncate">Source: {response.citation.title}</span>
            </span>
            <a
              href={response.citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 flex-shrink-0 text-primary hover:text-primary-container"
              aria-label={`Open source: ${response.citation.title}`}
            >
              <span className="material-symbols-outlined text-[18px]">open_in_new</span>
            </a>
          </div>

          <div className="mt-2 flex flex-col gap-2 border-t border-border-subtle pt-3 text-text-secondary sm:flex-row sm:items-center sm:justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide">{response.footer}</span>
            <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-compliance-amber">
              <span className="material-symbols-outlined text-[14px]">warning</span>
              {response.disclaimer}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex w-full justify-start gap-3">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-border-subtle bg-surface-white shadow-sm">
        <span className="material-symbols-outlined text-[18px] text-primary">smart_toy</span>
      </div>
      <div className="flex max-w-[85%] flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
          Assistant
        </span>
        <div className="rounded-t-xl rounded-bl-sm rounded-br-xl border border-border-subtle bg-surface-white p-5 shadow-soft">
          <div className="flex items-center gap-1.5" aria-label="Assistant is typing">
            <span className="h-2 w-2 animate-bounce rounded-full bg-text-secondary [animation-delay:0ms]" />
            <span className="h-2 w-2 animate-bounce rounded-full bg-text-secondary [animation-delay:150ms]" />
            <span className="h-2 w-2 animate-bounce rounded-full bg-text-secondary [animation-delay:300ms]" />
          </div>
        </div>
      </div>
    </div>
  );
}
