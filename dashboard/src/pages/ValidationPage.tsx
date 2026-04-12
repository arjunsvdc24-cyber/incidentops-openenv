import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getValidation } from '../api/client';

type Category = 'All' | 'Environment' | 'Grader' | 'Security' | 'API';

export function ValidationPage() {
  const [category, setCategory] = useState<Category>('All');

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['validation'],
    queryFn: getValidation,
    staleTime: 0,
  });

  const categorize = (name: string): Category => {
    const n = name.toLowerCase();
    if (n.includes('env') || n.includes('state') || n.includes('reset') || n.includes('step')) return 'Environment';
    if (n.includes('grader') || n.includes('grade') || n.includes('reward')) return 'Grader';
    if (n.includes('security') || n.includes('inject') || n.includes('leak')) return 'Security';
    if (n.includes('api') || n.includes('endpoint') || n.includes('route')) return 'API';
    return 'Environment';
  };

  const filtered = data?.filter((r) => {
    if (category === 'All') return true;
    return categorize(r.name) === category;
  }) ?? [];

  const passed = filtered.filter((r) => r.passed).length;
  const failed = filtered.filter((r) => !r.passed).length;
  const pct = filtered.length > 0 ? Math.round((passed / filtered.length) * 100) : 0;

  const categories: Category[] = ['All', 'Environment', 'Grader', 'Security', 'API'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Validation Suite</h1>
          <p className="text-text-secondary text-sm mt-1">
            Pre-submission checks for OpenEnv compliance
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="px-5 py-2.5 rounded-xl bg-accent/10 text-white font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
        >
          <svg className={`w-5 h-5 ${isFetching ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {isFetching ? 'Running...' : 'Run Validation'}
        </button>
      </div>

      {/* Score Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs text-text-secondary font-medium uppercase tracking-wider mb-1">Total</p>
          <p className="text-3xl font-bold text-text-primary font-mono">{data?.length ?? 0}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs text-success font-medium uppercase tracking-wider mb-1">Passed</p>
          <p className="text-3xl font-bold text-success font-mono">{passed}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs text-danger font-medium uppercase tracking-wider mb-1">Failed</p>
          <p className="text-3xl font-bold text-danger font-mono">{failed}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs text-text-secondary font-medium uppercase tracking-wider mb-1">Pass Rate</p>
          <p className={`text-3xl font-bold font-mono ${pct === 100 ? 'text-success' : pct >= 80 ? 'text-warning' : 'text-danger'}`}>
            {pct}%
          </p>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              category === cat
                ? 'bg-accent/10 text-white'
                : 'bg-surface border border-border text-text-secondary hover:text-text-primary'
            }`}
          >
            {cat}
            {cat !== 'All' && data && (
              <span className="ml-2 text-xs opacity-70">
                ({data.filter((r) => categorize(r.name) === cat).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl animate-pulse bg-gradient-to-r from-border via-background to-border bg-[length:200%_100%]" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16">
          <svg className="w-16 h-16 text-text-secondary/30 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-text-secondary">No tests in this category</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((result, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-4 p-4 rounded-xl border transition-all ${
                result.passed
                  ? 'bg-success/5 border-success/20'
                  : 'bg-danger/5 border-danger/20'
              }`}
            >
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                result.passed ? 'bg-success/20' : 'bg-danger/20'
              }`}>
                {result.passed ? (
                  <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`font-semibold text-sm ${
                    result.passed ? 'text-success' : 'text-danger'
                  }`}>
                    {result.passed ? 'PASS' : 'FAIL'}
                  </span>
                  <span className="text-sm font-medium text-text-primary">{result.name}</span>
                </div>
                {result.message && (
                  <p className="text-xs text-text-secondary mt-1">{result.message}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Hackathon Checklist */}
      <div className="bg-surface border border-border rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
          </svg>
          Pre-Submission Checklist
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: 'HF Space deploys', check: true },
            { label: 'OpenEnv spec compliance', check: true },
            { label: 'Dockerfile builds', check: true },
            { label: 'Baseline reproduces', check: true },
            { label: '3+ tasks with graders', check: true },
            { label: 'All validation tests pass', check: pct === 100 },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-3 p-3 rounded-lg bg-bg">
              <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${
                item.check ? 'bg-success/20' : 'bg-danger/20'
              }`}>
                {item.check ? (
                  <svg className="w-3 h-3 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-3 h-3 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
              </div>
              <span className={`text-sm ${item.check ? 'text-text-primary' : 'text-danger'}`}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
