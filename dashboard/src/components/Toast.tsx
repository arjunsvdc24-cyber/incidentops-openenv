import { useEffect, useRef } from 'react';
import { useUIStore } from '../stores/episodeStore';

const TOAST_ICONS = {
  success: (
    <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  ),
  error: (
    <svg className="w-5 h-5 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
  warning: (
    <svg className="w-5 h-5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  ),
  info: (
    <svg className="w-5 h-5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
};

const MAX_VISIBLE_TOASTS = 3;
const AUTO_DISMISS_DELAY = 4000;

function ToastItem({ id, message, type }: { id: string; message: string; type: 'success' | 'error' | 'info' }) {
  const { removeToast } = useUIStore();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    timerRef.current = setTimeout(() => {
      removeToast(id);
    }, AUTO_DISMISS_DELAY);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [id, removeToast]);

  return (
    <div
      className={`animate-slideIn flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg pointer-events-auto border ${
        type === 'success'
          ? 'bg-success/20 border-success/50'
          : type === 'error'
          ? 'bg-danger/20 border-danger/50'
          : 'bg-surface border-border'
      }`}
      role="alert"
      aria-live="polite"
    >
      {TOAST_ICONS[type]}
      <span className="text-sm text-text-primary flex-1">{message}</span>
      <button
        onClick={() => removeToast(id)}
        className="text-text-secondary hover:text-text-primary transition-colors"
        aria-label="Dismiss notification"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export function Toast() {
  const { toasts } = useUIStore();

  if (toasts.length === 0) return null;

  const visibleToasts = toasts.slice(0, MAX_VISIBLE_TOASTS);

  return (
    <div className="fixed top-4 right-4 z-[90] flex flex-col gap-2 pointer-events-none max-w-sm" aria-label="Notifications">
      {visibleToasts.map((toast) => (
        <ToastItem key={toast.id} id={toast.id} message={toast.message} type={toast.type} />
      ))}
    </div>
  );
}
