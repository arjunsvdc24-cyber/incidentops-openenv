import { useNavigate } from 'react-router-dom';
import type { Task } from '../api/types';

interface TaskCardProps {
  task: Task;
  onStartEpisode?: () => void;
}

export function TaskCard({ task, onStartEpisode }: TaskCardProps) {
  const navigate = useNavigate();

  const getDifficultyColor = (difficulty: number) => {
    if (difficulty <= 2) return { bg: 'bg-success/20', text: 'text-success', border: 'border-success/30' };
    if (difficulty <= 3) return { bg: 'bg-warning/20', text: 'text-warning', border: 'border-warning/30' };
    return { bg: 'bg-danger/20', text: 'text-danger', border: 'border-danger/30' };
  };

  const getDifficultyLabel = (difficulty: number) => {
    if (difficulty <= 2) return 'Easy';
    if (difficulty <= 3) return 'Medium';
    return 'Hard';
  };

  const colors = getDifficultyColor(task.difficulty);

  const handleStartEpisode = () => {
    if (onStartEpisode) {
      onStartEpisode();
    } else {
      navigate(`/episode?task=${task.id}`);
    }
  };

  return (
    <div
      className="flex flex-col bg-surface border border-border rounded-xl overflow-hidden hover:border-accent/50 transition-all group cursor-pointer"
      tabIndex={0}
      role="button"
      onClick={handleStartEpisode}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleStartEpisode();
        }
      }}
      aria-label={`Start episode for task: ${task.name}`}
    >
      <div className="p-4 flex-1">
        <div className="flex items-start justify-between gap-2 mb-3">
          <h3 className="text-lg font-semibold text-text-primary group-hover:text-accent transition-colors">
            {task.name}
          </h3>
          <span className={`px-2 py-1 rounded-lg text-xs font-bold uppercase ${colors.bg} ${colors.text} border ${colors.border}`}>
            {getDifficultyLabel(task.difficulty)}
          </span>
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          <span className="px-2 py-1 rounded bg-border/30 text-xs text-text-secondary">
            {task.fault_type}
          </span>
        </div>

        <p className="text-sm text-text-secondary leading-relaxed">{task.description}</p>

        {task.services_affected.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {task.services_affected.map((service) => (
              <span key={service} className="px-2 py-0.5 rounded bg-danger/10 text-danger/80 text-xs">
                {service}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 border-t border-border">
        <button
          onClick={handleStartEpisode}
          className="w-full py-2 px-4 rounded-lg bg-accent/10 text-white font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Start Episode
        </button>
      </div>
    </div>
  );
}
