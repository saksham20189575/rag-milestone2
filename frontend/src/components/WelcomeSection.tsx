import { EXAMPLE_QUESTIONS, WELCOME_TEXT } from "../types";

interface WelcomeSectionProps {
  onSelectQuestion: (question: string) => void;
  disabled?: boolean;
}

export function WelcomeSection({ onSelectQuestion, disabled = false }: WelcomeSectionProps) {
  return (
    <section className="mx-auto mb-4 mt-8 flex max-w-[540px] flex-col items-center text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full border border-border-subtle bg-surface-white shadow-soft">
        <span className="material-symbols-outlined text-[32px] text-primary">support_agent</span>
      </div>
      <p className="mb-8 text-base leading-relaxed text-text-primary md:text-lg">{WELCOME_TEXT}</p>
      <div className="w-full">
        <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Try an example question
        </p>
        <div className="flex w-full flex-col gap-3">
          {EXAMPLE_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              disabled={disabled}
              onClick={() => onSelectQuestion(question)}
              className="w-full rounded-full border border-border-subtle bg-surface-white px-4 py-3 text-left text-sm text-text-primary shadow-sm transition-all hover:border-text-secondary hover:bg-surface-bright disabled:cursor-not-allowed disabled:opacity-60"
            >
              {question}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
