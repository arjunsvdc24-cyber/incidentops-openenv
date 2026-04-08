import { useUIStore } from '../stores/episodeStore';

export function Toast() {
  const { toasts, removeToast } = useUIStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[90] flex flex-col gap-2 pointer-events-none max-w-sm">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`animate-slideIn flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg pointer-events-auto ${
            toast.type === 'success'
              ? 'bg-success/20 border border-success/50'
              : toast.type === 'error'
              ? 'bg-danger/20 border border-danger/50'
              : 'bg-surface border border-border'
          }`}
        >
          <span className="text-sm text-text-primary">{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
