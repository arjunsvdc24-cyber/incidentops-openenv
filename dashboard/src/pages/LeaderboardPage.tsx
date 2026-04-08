import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getLeaderboard, getTasks } from '../api/client';
import { LeaderboardTable } from '../components/LeaderboardTable';
import { useAuthStore } from '../stores/episodeStore';

export function LeaderboardPage() {
  const [selectedTask, setSelectedTask] = useState<string | undefined>(undefined);
  const { username } = useAuthStore();

  const { data: tasksData } = useQuery({
    queryKey: ['tasks'],
    queryFn: getTasks,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['leaderboard', selectedTask],
    queryFn: () => getLeaderboard(selectedTask),
  });

  const getDifficultyColor = (difficulty: number) => {
    if (difficulty <= 2) return 'text-success';
    if (difficulty <= 3) return 'text-warning';
    return 'text-danger';
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <svg className="w-16 h-16 text-danger mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h2 className="text-xl font-semibold text-text-primary mb-2">Failed to Load Leaderboard</h2>
        <p className="text-text-secondary">{String(error)}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Leaderboard</h1>
          <p className="text-text-secondary text-sm mt-1">
            Top performers across all tasks
          </p>
        </div>
      </div>

      {/* Task Filter */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Filter by Task
            </label>
            <select
              value={selectedTask || ''}
              onChange={(e) => setSelectedTask(e.target.value || undefined)}
              className="w-full px-4 py-2 bg-bg border border-border rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="">All Tasks</option>
              {tasksData?.tasks?.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.name} ({task.difficulty <= 2 ? 'Easy' : task.difficulty <= 3 ? 'Medium' : 'Hard'})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Leaderboard Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">
            {selectedTask
              ? `${tasksData?.tasks?.find((t) => t.id === selectedTask)?.name || 'Task'} Rankings`
              : 'All Tasks Rankings'}
          </h2>
          <span className="text-sm text-text-secondary">
            {data?.entries?.length || 0} entries
          </span>
        </div>

        {isLoading ? (
          <div className="p-8">
            <div className="animate-pulse space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center gap-4">
                  <div className="w-8 h-8 bg-border rounded-full" />
                  <div className="flex-1 h-4 bg-border rounded" />
                  <div className="w-20 h-4 bg-border rounded" />
                  <div className="w-20 h-4 bg-border rounded" />
                </div>
              ))}
            </div>
          </div>
        ) : data?.entries && data.entries.length > 0 ? (
          <LeaderboardTable entries={data.entries} currentUsername={username} />
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-text-secondary">
            <svg className="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <h2 className="text-xl font-semibold text-text-primary mb-2">No Entries Yet</h2>
            <p className="text-sm">Be the first to submit an episode and claim the top spot!</p>
          </div>
        )}
      </div>

      {/* Top Performers by Task */}
      {!selectedTask && data?.entries && data.entries.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {tasksData?.tasks?.slice(0, 6).map((task) => {
            const taskEntries = data.entries.filter((e) => e.task_id === task.id);
            const topEntry = [...taskEntries].sort((a, b) => b.best_score - a.best_score)[0];
            if (!topEntry) return null;

            return (
              <div key={task.id} className="bg-surface border border-border rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-text-primary">{task.name}</h3>
                  <span className={`text-xs font-bold ${getDifficultyColor(task.difficulty)}`}>
                    {task.difficulty <= 2 ? 'Easy' : task.difficulty <= 3 ? 'Medium' : 'Hard'}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-yellow-500/20 flex items-center justify-center">
                    <span className="text-xl font-bold text-yellow-400">1</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text-primary truncate">
                      {topEntry.username}
                      {topEntry.username === username && (
                        <span className="ml-2 text-xs text-accent">(You)</span>
                      )}
                    </p>
                    <p className="text-sm text-success font-mono">
                      {topEntry.best_score.toFixed(3)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
