interface SkeletonProps {
  className?: string;
  lines?: number;
  type?: 'text' | 'card' | 'chart' | 'table' | 'avatar';
}

// Flat dark skeleton using bg/surface/border palette
const skeletonPulse = 'animate-pulse bg-bg';

export function Skeleton({ className = '', lines = 3, type = 'text' }: SkeletonProps) {
  if (type === 'card') {
    return (
      <div className={`panel p-4 space-y-3 ${className}`}>
        <div className={`h-3 ${skeletonPulse} rounded w-1/3`} />
        <div className={`h-2.5 ${skeletonPulse} rounded w-full`} />
        <div className={`h-2.5 ${skeletonPulse} rounded w-5/6`} />
        <div className={`h-2.5 ${skeletonPulse} rounded w-4/6`} />
      </div>
    );
  }

  if (type === 'table') {
    return (
      <div className={`panel overflow-hidden ${className}`}>
        <div className="p-3 border-b border-border flex gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className={`h-2.5 ${skeletonPulse} rounded flex-1`} />
          ))}
        </div>
        {[1, 2, 3, 4, 5].map(row => (
          <div key={row} className="p-3 border-b border-border last:border-0 flex gap-4">
            {[1, 2, 3, 4].map(col => (
              <div key={col} className={`h-2.5 ${skeletonPulse} rounded flex-1`} />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (type === 'chart') {
    return (
      <div className={`panel p-4 ${className}`}>
        <div className="flex items-center justify-between mb-4">
          <div className={`h-4 ${skeletonPulse} rounded w-24`} />
          <div className={`h-2.5 ${skeletonPulse} rounded w-16`} />
        </div>
        <div className="flex items-end gap-1.5 h-28">
          {[40, 65, 45, 80, 55, 70, 50, 85, 60, 75, 45, 90].map((h, i) => (
            <div key={i} className={`flex-1 ${skeletonPulse} rounded-sm`} style={{ height: `${h}%` }} />
          ))}
        </div>
        <div className="flex justify-between mt-2">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className={`h-2 ${skeletonPulse} rounded w-6`} />
          ))}
        </div>
      </div>
    );
  }

  if (type === 'avatar') {
    return (
      <div className={`flex items-center gap-3 p-3 panel ${className}`}>
        <div className={`w-9 h-9 rounded border border-border ${skeletonPulse}`} />
        <div className="flex-1 space-y-2">
          <div className={`h-3 ${skeletonPulse} rounded w-1/2`} />
          <div className={`h-2.5 ${skeletonPulse} rounded w-3/4`} />
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`h-2.5 ${skeletonPulse} rounded ${i === lines - 1 ? 'w-3/4' : 'w-full'}`}
        />
      ))}
    </div>
  );
}

// Stats card skeleton — flat dark
export function StatsCardSkeleton() {
  return (
    <div className="panel p-3">
      <div className="flex items-center gap-2.5">
        <div className={`w-8 h-8 rounded border border-border ${skeletonPulse}`} />
        <div className="space-y-1.5 flex-1">
          <div className={`h-4 ${skeletonPulse} rounded w-14`} />
          <div className={`h-2 ${skeletonPulse} rounded w-16`} />
        </div>
      </div>
    </div>
  );
}
