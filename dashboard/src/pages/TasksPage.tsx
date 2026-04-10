import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getTasks } from '../api/client';
import { TaskCard } from '../components/TaskCard';

type DifficultyFilter = 'all' | 'easy' | 'medium' | 'hard';

export function TasksPage() {
  const [filter, setFilter] = useState<DifficultyFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['tasks'],
    queryFn: getTasks,
  });

  const getDifficultyRange = (difficultyFilter: DifficultyFilter): [number, number] => {
    switch (difficultyFilter) {
      case 'easy':
        return [1, 2];
      case 'medium':
        return [3, 3];
      case 'hard':
        return [4, 5];
      default:
        return [1, 5];
    }
  };

  const filteredTasks = data?.tasks?.filter((task) => {
    const [min, max] = getDifficultyRange(filter);
    const matchesDifficulty = task.difficulty >= min && task.difficulty <= max;
    const matchesSearch =
      searchQuery === '' ||
      task.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.fault_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesDifficulty && matchesSearch;
  }) || [];

  const difficultyCounts = {
    all: data?.tasks?.length || 0,
    easy: data?.tasks?.filter((t) => t.difficulty <= 2).length || 0,
    medium: data?.tasks?.filter((t) => t.difficulty === 3).length || 0,
    hard: data?.tasks?.filter((t) => t.difficulty >= 4).length || 0,
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12" role="alert" aria-live="polite">
        <svg className="w-16 h-16 text-danger mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h2 className="text-xl font-semibold text-text-primary mb-2">Failed to Load Tasks</h2>
        <p className="text-text-secondary">{String(error)}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Fault Scenarios</h1>
        <p className="text-text-secondary text-sm mt-1">
          Browse and start incident response episodes
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="flex-1 relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-secondary"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tasks..."
            className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent"
            aria-label="Search tasks"
          />
        </div>

        {/* Difficulty Filter */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-secondary">Difficulty:</span>
          <div className="flex rounded-lg border border-border overflow-x-auto scrollbar-thin" role="group" aria-label="Difficulty filter">
            {(['all', 'easy', 'medium', 'hard'] as DifficultyFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  filter === f
                    ? 'bg-accent text-white'
                    : 'bg-surface text-text-secondary hover:text-text-primary hover:bg-surface-border'
                }`}
                aria-pressed={filter === f}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
                <span className="ml-1 text-xs opacity-75">({difficultyCounts[f]})</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tasks Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-surface border border-border rounded-xl p-6 animate-pulse">
              <div className="h-6 bg-border rounded w-3/4 mb-4" />
              <div className="h-4 bg-border rounded w-1/2 mb-2" />
              <div className="h-4 bg-border rounded w-full mb-2" />
              <div className="h-4 bg-border rounded w-2/3" />
            </div>
          ))}
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-text-secondary" role="status">
          <svg className="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="text-xl font-semibold text-text-primary mb-2">No Tasks Found</h2>
          <p className="text-sm">Try adjusting your filters or search query</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
      )}

      {/* Stats Summary */}
      {data?.tasks && data.tasks.length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-lg bg-bg">
              <p className="text-3xl font-bold text-text-primary">{data.tasks.length}</p>
              <p className="text-sm text-text-secondary">Total Tasks</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-success/10">
              <p className="text-3xl font-bold text-success">{difficultyCounts.easy}</p>
              <p className="text-sm text-text-secondary">Easy</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-warning/10">
              <p className="text-3xl font-bold text-warning">{difficultyCounts.medium}</p>
              <p className="text-sm text-text-secondary">Medium</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-danger/10">
              <p className="text-3xl font-bold text-danger">{difficultyCounts.hard}</p>
              <p className="text-sm text-text-secondary">Hard</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
