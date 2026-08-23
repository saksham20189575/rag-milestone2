export function Header() {
  return (
    <header className="sticky top-0 z-50 flex w-full flex-col border-b border-border-subtle bg-surface-white shadow-sm">
      <div className="mx-auto flex w-full max-w-chat flex-col px-4 py-4 md:px-6">
        <div className="flex w-full items-center justify-between">
          <div className="flex flex-col">
            <h1 className="text-xl font-semibold text-text-primary md:text-2xl">
              Mutual Fund FAQ Assistant
            </h1>
            <p className="mt-1 text-sm text-text-secondary">HDFC schemes · Groww sources</p>
          </div>
          <button
            type="button"
            aria-label="About this assistant"
            className="rounded-full p-2 text-text-secondary transition-colors hover:bg-surface-bright hover:text-primary"
            title="Facts-only assistant for HDFC mutual fund scheme information"
          >
            <span className="material-symbols-outlined text-[22px]">info</span>
          </button>
        </div>
      </div>
      <div className="w-full border-b border-amber-200 bg-amber-50">
        <div className="mx-auto flex max-w-chat items-center gap-2 px-4 py-2 md:px-6">
          <span className="material-symbols-outlined text-[16px] text-compliance-amber">info</span>
          <p className="text-sm font-medium text-compliance-amber">
            Facts-only. No investment advice.
          </p>
        </div>
      </div>
    </header>
  );
}
