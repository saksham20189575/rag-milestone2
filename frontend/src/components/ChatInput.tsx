import { FormEvent, KeyboardEvent, useState } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [value, setValue] = useState("");

  const trimmed = value.trim();
  const canSend = trimmed.length > 0 && !disabled;

  const submit = () => {
    if (!canSend) {
      return;
    }
    onSend(trimmed);
    setValue("");
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="fixed bottom-0 z-50 w-full border-t border-border-subtle bg-surface-white/95 px-4 pb-6 pt-4 shadow-sticky backdrop-blur-md md:px-6">
      <form onSubmit={handleSubmit} className="mx-auto flex max-w-chat flex-col gap-2">
        <div className="relative flex w-full items-center">
          <input
            type="text"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            aria-label="Ask a factual question about HDFC schemes"
            placeholder="Ask a factual question about HDFC schemes..."
            className="w-full rounded-lg border border-border-subtle bg-surface-bright py-4 pl-4 pr-16 text-base text-text-primary placeholder:text-text-secondary shadow-inner focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
            className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center justify-center rounded-md bg-primary p-2 text-white shadow-sm transition hover:bg-primary-container disabled:cursor-not-allowed disabled:bg-text-secondary/40"
          >
            <span className="material-symbols-outlined filled text-[20px]">send</span>
          </button>
        </div>
        <p className="mt-1 flex items-center justify-center gap-1 text-center text-xs font-semibold uppercase tracking-wide text-text-secondary">
          <span className="material-symbols-outlined text-[14px]">lock</span>
          Do not enter PAN, Aadhaar, phone, or account numbers.
        </p>
      </form>
    </div>
  );
}
