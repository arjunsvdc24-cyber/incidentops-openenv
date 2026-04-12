import { useState } from 'react';
import { format } from 'date-fns';
import { ScoreRing } from './ScoreRing';
import type { Episode } from '../api/types';

interface EpisodeRowProps {
  episode: Episode;
  expanded?: boolean;
}

export function EpisodeRow({ episode, expanded: defaultExpanded = false }: EpisodeRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const getGradeColor = (grade: number) => {
    if (grade >= 0.8) return 'text-success';
    if (grade >= 0.6) return 'text-warning';
    if (grade >= 0.4) return 'text-orange-500';
    return 'text-danger';
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 p-4 hover:bg-surface/50 transition-colors text-left"
      >
        <div className="flex-shrink-0">
          <ScoreRing score={episode.grade * 100} maxScore={100} size={50} strokeWidth={4} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-text-primary">{episode.fault_type}</span>
            <span className="px-2 py-0.5 rounded bg-border/30 text-xs text-text-secondary">
              {episode.steps} steps
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs text-text-secondary">
            <span>{episode.task_name}</span>
            <span>{format(new Date(episode.created_at), 'MMM d, yyyy HH:mm')}</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className={`text-lg font-mono font-bold ${getGradeColor(episode.grade)}`}>
              {(episode.grade * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-text-secondary">Grade</div>
          </div>
          <svg
            className={`w-5 h-5 text-text-secondary transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border p-4 bg-surface/30">
          <h4 className="text-sm font-semibold text-text-secondary mb-3">Action Timeline</h4>
          <div className="flex flex-col gap-2 max-h-[300px] overflow-y-auto overscroll-contain">
            {episode.trajectory.map((entry, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-2 bg-surface rounded-lg"
              >
                <div className="flex items-center justify-center w-6 h-6 rounded-full bg-border/30 text-xs font-bold text-text-secondary">
                  {entry.step}
                </div>
                <div className="flex-1">
                  <span className="text-sm font-medium text-text-primary">
                    {entry.action_type?.replace('_', ' ') ?? entry.action_type}
                  </span>
                  {entry.target_service && (
                    <span className="ml-2 text-xs px-2 py-0.5 rounded bg-border/30 text-text-secondary">
                      {entry.target_service}
                    </span>
                  )}
                </div>
                <div
                  className={`text-sm font-mono ${
                    entry.reward > 0 ? 'text-success' : entry.reward < 0 ? 'text-danger' : 'text-text-secondary'
                  }`}
                >
                  {entry.reward > 0 ? '+' : ''}
                  {entry.reward.toFixed(2)}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-border flex justify-end text-sm">
            <div>
              <span className="text-text-secondary">Total Reward: </span>
              <span className="font-mono font-bold text-text-primary">
                {episode.trajectory.reduce((sum, e) => sum + e.reward, 0).toFixed(3)}
              </span>
            </div>
            <a
              href={`/replay/${episode.id}`}
              className="text-accent hover:underline flex items-center gap-1"
            >
              Replay Episode
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
