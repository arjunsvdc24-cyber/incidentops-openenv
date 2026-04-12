import { format } from 'date-fns';

interface TimelineEntry {
  step: number;
  action_type: string;
  target_service: string;
  reward: number;
  cumulative_reward?: number;
  timestamp?: string;
}

interface TimelineProps {
  entries: TimelineEntry[];
  currentStep?: number;
}

export function Timeline({ entries, currentStep }: TimelineProps) {
  const getRewardColor = (reward: number) => {
    if (reward > 0) return 'text-success';
    if (reward < 0) return 'text-danger';
    return 'text-text-secondary';
  };

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-text-secondary">
        <svg className="w-12 h-12 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="text-sm">No actions yet</span>
        <span className="text-xs text-text-secondary/60">Execute an action to see it here</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 max-h-[400px] overflow-y-auto overscroll-contain pr-2">
      {entries.map((entry, index) => (
        <div
          key={index}
          className={`flex items-center gap-3 p-2 rounded transition-all ${
            currentStep === entry.step ? 'bg-accent/10 border border-accent' : 'bg-bg/50 hover:bg-bg'
          }`}
        >
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-border/30 text-xs font-bold text-text-secondary">
            {entry.step}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-text-primary truncate">
                {entry.action_type?.replace('_', ' ') ?? entry.action_type}
              </span>
              {entry.target_service && (
                <span className="text-xs px-2 py-0.5 rounded bg-border/30 text-text-secondary truncate">
                  {entry.target_service}
                </span>
              )}
            </div>
            {entry.timestamp && (
              <span className="text-[10px] text-text-secondary/60">
                {format(new Date(entry.timestamp), 'HH:mm:ss')}
              </span>
            )}
          </div>
          <div className={`text-sm font-mono font-bold ${getRewardColor(entry.reward)}`}>
            {entry.reward > 0 ? '+' : ''}
            {entry.reward.toFixed(2)}
          </div>
        </div>
      ))}
    </div>
  );
}
