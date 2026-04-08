import { format } from 'date-fns';
import type { LeaderboardEntry } from '../api/types';

interface LeaderboardTableProps {
  entries: LeaderboardEntry[];
  currentUsername?: string | null;
}

export function LeaderboardTable({ entries, currentUsername }: LeaderboardTableProps) {
  const getRankStyle = (rank: number) => {
    if (rank === 1) return 'bg-yellow-500/20 text-yellow-400';
    if (rank === 2) return 'bg-gray-400/20 text-gray-300';
    if (rank === 3) return 'bg-amber-600/20 text-amber-500';
    return 'bg-border/30 text-text-secondary';
  };

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-text-secondary">
        <svg className="w-16 h-16 mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <span className="text-sm">No leaderboard entries yet</span>
        <span className="text-xs text-text-secondary/60">Be the first to submit an episode!</span>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border">
            <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Rank
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase tracking-wider">
              User
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Best
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Avg
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Episodes
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Updated
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr
              key={`${entry.username}-${entry.task_id}`}
              className={`border-b border-border/50 hover:bg-surface/50 transition-colors ${
                entry.username === currentUsername ? 'bg-accent/10 border-l-4 border-l-accent' : ''
              }`}
            >
              <td className="px-4 py-3">
                <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${getRankStyle(entry.rank)}`}>
                  {entry.rank}
                </span>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text-primary">{entry.username}</span>
                  {entry.username === currentUsername && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-accent/20 text-accent">
                      You
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-right">
                <span className="text-sm font-mono font-bold text-success">
                  {entry.best_score.toFixed(3)}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <span className="text-sm font-mono text-text-secondary">
                  {entry.avg_score.toFixed(3)}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <span className="text-sm text-text-secondary">{entry.episode_count}</span>
              </td>
              <td className="px-4 py-3 text-right">
                <span className="text-xs text-text-secondary/60">
                  {format(new Date(entry.updated_at), 'MMM d, HH:mm')}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
