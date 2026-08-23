import { useCallback, useEffect, useRef, useState } from "react";
import { sendChatMessage } from "./api/chat";
import { AssistantBubble, TypingIndicator, UserBubble } from "./components/ChatMessages";
import { ChatInput } from "./components/ChatInput";
import { Header } from "./components/Header";
import { WelcomeSection } from "./components/WelcomeSection";
import type { ChatMessage } from "./types";

function createId(): string {
  return crypto.randomUUID();
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const hasConversation = messages.length > 0;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, error]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) {
      return;
    }

    setError(null);
    setMessages((current) => [...current, { id: createId(), role: "user", text: trimmed }]);
    setIsLoading(true);

    try {
      const response = await sendChatMessage(trimmed);
      setMessages((current) => [
        ...current,
        { id: createId(), role: "assistant", response },
      ]);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unable to reach the server. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading]);

  return (
    <div className="flex h-screen flex-col items-center overflow-hidden bg-background text-text-primary antialiased">
      <Header />

      <main className="scrollbar-hide flex w-full max-w-chat flex-1 flex-col gap-6 overflow-y-auto px-4 py-10 pb-40 md:px-6">
        {!hasConversation && !isLoading && (
          <WelcomeSection onSelectQuestion={sendMessage} disabled={isLoading} />
        )}

        {messages.map((message, index) => {
          const previous = messages[index - 1];
          const showTurnGap = previous?.role === "assistant" && message.role === "user";

          if (message.role === "user") {
            return (
              <div key={message.id} className={showTurnGap ? "mt-4 flex flex-col gap-3" : "flex flex-col gap-3"}>
                <UserBubble text={message.text} />
              </div>
            );
          }

          return (
            <div key={message.id} className="flex flex-col gap-3">
              <AssistantBubble response={message.response} />
            </div>
          );
        })}

        {isLoading && <TypingIndicator />}

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-error"
          >
            {error}
          </div>
        )}

        <div ref={chatEndRef} />
      </main>

      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
