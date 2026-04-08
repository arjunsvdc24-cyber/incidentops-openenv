import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getEpisodes } from '../api/client';
import { EpisodeRow } from '../components/EpisodeRow';
import { useAuthStore, useUIStore } from '../stores/episodeStore';

export function EpisodesPage() {
  const { isAuthenticated } = useAuthStore();
  const { openAuthModal } = useUIStore();
  const [page, setPage] = useState(1);
  const [faultTypeFilter, setFaultTypeFilter] = useState<string>('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['episodes', page, faultTypeFilter],
    queryFn: () => getEpisodes(page, 20, faultTypeFilter || undefined),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <svg className="w-16 h-16 text-text-secondary mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <h2 className="text-xl font-semibold text-text-primary mb-2">Sign In Required</h2>
        <p className="text-text-secondary text-center mb-4">Please sign in to view your episodes</p>
        <button
          onClick={() => openAuthModal(() => {})}
          className="px-6 py-2 rounded-lg bg-accent/10 text-white font-medium hover:opacity-90 transition-opacity"
        >
          Sign In
        </button>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <svg className="w-16 h-16 text-danger mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h2 className="text-xl font-semibold text-text-primary mb-2">Failed to Load Episodes</h2>
        <p className="text-text-secondary">{String(error)}</p>
      </div>
    );
  }

  const faultTypes = [...new Set(data?.episodes?.map((e) => e.fault_type) || [])];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">My Episodes</h1>
          <p className="text-text-secondary text-sm mt-1">
            View and replay your saved episodes
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Filter by Fault Type
            </label>
            <select
              value={faultTypeFilter}
              onChange={(e) => {
                setFaultTypeFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-4 py-2 bg-bg border border-border rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent"
            >
              <option value="">All Fault Types</option>
              {faultTypes.map((ft) => (
                <option key={ft} value={ft}>
                  {ft}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Episodes List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="bg-surface border border-border rounded-xl p-6 animate-pulse">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-border rounded-full" />
                  <div className="flex-1">
                    <div className="h-4 bg-border rounded w-1/3 mb-2" />
                    <div className="h-3 bg-border rounded w-1/2" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : data?.episodes && data.episodes.length > 0 ? (
          <>
            <div className="flex items-center justify-between text-sm text-text-secondary">
              <span>Showing {data.episodes.length} of {data.total} episodes</span>
            </div>
            {data.episodes.map((episode) => (
              <EpisodeRow key={episode.id} episode={episode} />
            ))}

            {/* Pagination */}
            {data.pages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-4">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, data.pages) }, (_, i) => {
                    let pageNum: number;
                    if (data.pages <= 5) {
                      pageNum = i + 1;
                    } else if (page <= 3) {
                      pageNum = i + 1;
                    } else if (page >= data.pages - 2) {
                      pageNum = data.pages - 4 + i;
                    } else {
                      pageNum = page - 2 + i;
                    }
                    return (
                      <button
                        key={pageNum}
                        onClick={() => setPage(pageNum)}
                        className={`w-10 h-10 rounded-lg font-medium transition-colors ${
                          page === pageNum
                            ? 'bg-accent text-white'
                            : 'border border-border text-text-secondary hover:text-text-primary hover:border-accent'
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>
                <button
                  onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                  disabled={page === data.pages}
                  className="px-4 py-2 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-text-secondary">
            <svg className="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <h2 className="text-xl font-semibold text-text-primary mb-2">No Episodes Yet</h2>
            <p className="text-sm text-center">Complete and save episodes to see them here</p>
          </div>
        )}
      </div>
    </div>
  );
}
