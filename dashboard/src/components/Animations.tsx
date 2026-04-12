import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

// Page transition wrapper
export function PageTransition({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const location = useLocation();

  useEffect(() => {
    if (ref.current) {
      ref.current.classList.remove('opacity-0', 'translate-y-1');
    }
    return () => {
      if (ref.current) {
        ref.current.classList.add('opacity-0', 'translate-y-1');
      }
    };
  }, [location.pathname]);

  return (
    <div
      ref={ref}
      className="opacity-0 translate-y-1 transition-all duration-200 ease-out"
    >
      {children}
    </div>
  );
}

// Score badge — flat, monospaced
export function ScoreBadge({ score, size = 'md' }: { score: number; size?: 'sm' | 'md' | 'lg' }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'text-success' : pct >= 60 ? 'text-warning' : 'text-danger';

  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : size === 'lg' ? 'text-xl px-4 py-2' : 'text-sm px-3 py-1';

  return (
    <span className={`font-mono font-bold border ${color} border-current/30 rounded ${sizeClasses}`}>
      {pct}%
    </span>
  );
}

// Animated counter (for use in Dashboard)
export function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const start = parseFloat(el.textContent || '0');
    const end = value;
    const duration = 600;
    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (end - start) * eased;
      el.textContent = current.toFixed(decimals);
      if (progress < 1) requestAnimationFrame(animate);
    };

    requestAnimationFrame(animate);
  }, [value, decimals]);

  return <span ref={ref}>{value.toFixed(decimals)}</span>;
}
