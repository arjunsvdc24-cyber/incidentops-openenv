import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getProfile, getTasks, checkProvider } from '../api/client';
import { useAuthStore, useUIStore } from '../stores/episodeStore';
import { ScoreRing } from '../components/ScoreRing';

export function ProfilePage() {
  const navigate = useNavigate();
  const { isAuthenticated, username, apiKey, setApiKey, logout, loadFromStorage } = useAuthStore();
  const { openAuthModal, addToast } = useUIStore();
  const [openaiKey, setOpenaiKey] = useState('');
  const [apiKeyCopied, setApiKeyCopied] = useState(false);
  const [openaiValidating, setOpenaiValidating] = useState(false);
  const [openaiValid, setOpenaiValid] = useState<boolean | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<'groq' | 'gemini' | 'asksage' | 'openai' | 'huggingface'>('groq');

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: getProfile,
    enabled: isAuthenticated,
  });

  const { data: tasks } = useQuery({
    queryKey: ['tasks'],
    queryFn: getTasks,
  });

  const handleCopyApiKey = () => {
    if (profile?.api_key) {
      navigator.clipboard.writeText(profile.api_key);
      setApiKeyCopied(true);
      setTimeout(() => setApiKeyCopied(false), 2000);
    }
  };

  const handleSetApiKey = async () => {
    if (!openaiKey.trim()) {
      addToast('Please enter an API key', 'error');
      return;
    }
    setOpenaiValidating(true);
    try {
      const result = await checkProvider(selectedProvider, openaiKey.trim());
      if (result.valid) {
        setApiKey(openaiKey.trim());
        setOpenaiValid(true);
        const provider = result.provider || selectedProvider;
        const model = result.model ? ` (${result.model})` : '';
        addToast(`${provider.toUpperCase()} API key validated${model}!`, 'success');
      } else {
        setOpenaiValid(false);
        addToast('Invalid API key', 'error');
      }
    } catch {
      setOpenaiValid(false);
      addToast('Failed to validate API key', 'error');
    } finally {
      setOpenaiValidating(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto space-y-6">
        <div className="text-center">
          <div className="w-20 h-20 rounded-full bg-accent/10 mx-auto flex items-center justify-center mb-4">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-text-primary">Sign In to IncidentOps</h1>
          <p className="text-text-secondary mt-2">Create an account or sign in to save episodes and track your progress</p>
        </div>

        <div className="bg-surface border border-border rounded-xl p-6">
          <button
            onClick={() => openAuthModal(() => {})}
            className="w-full py-3 px-4 rounded-lg bg-accent/10 text-white font-semibold hover:opacity-90 transition-opacity"
          >
            Sign In / Register
          </button>
        </div>

        {/* LLM API Configuration */}
        <div className="bg-surface border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">LLM API Key</h2>
          <p className="text-sm text-text-secondary mb-4">
            Configure an API key for the LLM baseline agent. Groq is free and default.
          </p>
          <div className="space-y-3">
            {/* Provider selector */}
            <div className="flex gap-2 flex-wrap">
              {(['groq', 'gemini', 'asksage', 'openai', 'huggingface'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => {
                    setSelectedProvider(p);
                    setOpenaiKey('');
                    setOpenaiValid(null);
                  }}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    selectedProvider === p
                      ? 'bg-accent text-white'
                      : 'bg-bg border border-border text-text-secondary hover:border-accent'
                  }`}
                >
                  {p === 'groq' ? 'Groq (free)' : p === 'asksage' ? 'AskSage' : p.charAt(0).toUpperCase() + p.slice(1)}
                </button>
              ))}
            </div>
            <input
              type="password"
              value={openaiKey}
              onChange={(e) => {
                setOpenaiKey(e.target.value);
                setOpenaiValid(null);
              }}
              placeholder={
                selectedProvider === 'groq' ? 'gsk_... (leave empty for default)' :
                selectedProvider === 'gemini' ? 'AIza...' :
                selectedProvider === 'asksage' ? 'Your AskSage key...' :
                selectedProvider === 'openai' ? 'sk-...' :
                'hf_...'
              }
              className="w-full px-4 py-2 bg-bg border border-border rounded-lg text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <button
              onClick={handleSetApiKey}
              disabled={openaiValidating || !openaiKey.trim()}
              className="w-full py-2 px-4 rounded-lg border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {openaiValidating ? 'Validating...' : 'Save API Key'}
            </button>
            {openaiValid !== null && (
              <p className={`text-sm ${openaiValid ? 'text-success' : 'text-danger'}`}>
                {openaiValid ? 'API key is valid!' : 'Invalid API key'}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <div className="flex items-center gap-6">
          <div className="w-20 h-20 rounded-full bg-accent/10 flex items-center justify-center">
            <span className="text-3xl font-bold text-white">
              {username?.charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-text-primary">{username}</h1>
            <p className="text-text-secondary mt-1">Incident Response Agent</p>
            <div className="flex items-center gap-4 mt-3">
              <span className="px-3 py-1 rounded-full bg-success/20 text-success text-sm font-medium">
                Active
              </span>
              <span className="text-sm text-text-secondary">
                {profile?.total_episodes || 0} episodes
              </span>
            </div>
          </div>
          <button
            onClick={() => { logout(); navigate('/'); }}
            className="px-4 py-2 rounded-lg border border-danger text-danger hover:bg-danger/10 transition-colors flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Logout
          </button>
        </div>
      </div>

      {/* API Key */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">API Key</h2>
        <p className="text-sm text-text-secondary mb-4">
          Use this API key for programmatic access to the IncidentOps API
        </p>
        <div className="flex items-center gap-3">
          <code className="flex-1 px-4 py-2 bg-bg rounded-lg border border-border text-text-primary font-mono text-sm truncate">
            {profile?.api_key || 'Not available'}
          </code>
          <button
            onClick={handleCopyApiKey}
            className="px-4 py-2 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent transition-colors flex items-center gap-2"
          >
            {apiKeyCopied ? (
              <>
                <svg className="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Copied!
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Copy
              </>
            )}
          </button>
        </div>
      </div>

      {/* LLM API Configuration */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">LLM API Key</h2>
        <p className="text-sm text-text-secondary mb-4">
          Configure an API key for the LLM baseline agent. Groq is free and default.
        </p>
        <div className="space-y-3">
          {/* Provider selector */}
          <div className="flex gap-2 flex-wrap">
            {(['groq', 'gemini', 'asksage', 'openai', 'huggingface'] as const).map((p) => (
              <button
                key={p}
                onClick={() => {
                  setSelectedProvider(p);
                  setOpenaiKey('');
                  setOpenaiValid(null);
                }}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  selectedProvider === p
                    ? 'bg-accent text-white'
                    : 'bg-bg border border-border text-text-secondary hover:border-accent'
                }`}
              >
                {p === 'groq' ? 'Groq (free)' : p === 'asksage' ? 'AskSage' : p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
          <input
            type="password"
            value={openaiKey}
            onChange={(e) => {
              setOpenaiKey(e.target.value);
              setOpenaiValid(null);
            }}
            placeholder={
              selectedProvider === 'groq' ? 'gsk_... (leave empty for default)' :
              selectedProvider === 'gemini' ? 'AIza...' :
              selectedProvider === 'asksage' ? 'Your AskSage key...' :
              selectedProvider === 'openai' ? 'sk-...' :
              'hf_...'
            }
            className="w-full px-4 py-2 bg-bg border border-border rounded-lg text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            onClick={handleSetApiKey}
            disabled={openaiValidating || !openaiKey.trim()}
            className="px-4 py-2 rounded-lg border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {openaiValidating ? 'Validating...' : 'Save API Key'}
          </button>
          {openaiValid !== null && (
            <p className={`text-sm ${openaiValid ? 'text-success' : 'text-danger'}`}>
              {openaiValid ? 'API key is valid!' : 'Invalid API key'}
            </p>
          )}
          {apiKey && !openaiKey && (
            <p className="text-sm text-success">API key is configured</p>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Statistics</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="text-center p-4 rounded-lg bg-bg">
            <p className="text-3xl font-bold text-text-primary">{profile?.total_episodes || 0}</p>
            <p className="text-sm text-text-secondary mt-1">Total Episodes</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-success/10">
            <p className="text-3xl font-bold text-success">
              {Math.max(...Object.values(profile?.best_scores || {}), 0).toFixed(2)}
            </p>
            <p className="text-sm text-text-secondary mt-1">Best Score</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-warning/10">
            <p className="text-3xl font-bold text-warning">
              {Object.keys(profile?.best_scores || {}).length}
            </p>
            <p className="text-sm text-text-secondary mt-1">Tasks Completed</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-accent/10">
            <p className="text-3xl font-bold text-accent">
              {Object.keys(profile?.leaderboard_ranks || {}).length}
            </p>
            <p className="text-sm text-text-secondary mt-1">On Leaderboard</p>
          </div>
        </div>
      </div>

      {/* Best Scores by Task */}
      {profile?.best_scores && Object.keys(profile.best_scores).length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Best Scores by Task</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {tasks?.tasks?.map((task) => {
              const score = profile.best_scores[task.id];
              if (!score) return null;
              return (
                <div key={task.id} className="flex items-center gap-4 p-4 rounded-lg bg-bg">
                  <ScoreRing score={score * 100} maxScore={100} size={50} strokeWidth={4} />
                  <div>
                    <p className="font-medium text-text-primary">{task.name}</p>
                    <p className="text-sm text-success font-mono">{score.toFixed(3)}</p>
                    {profile.leaderboard_ranks?.[task.id] && (
                      <p className="text-xs text-text-secondary">
                        Rank #{profile.leaderboard_ranks[task.id]}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Leaderboard Ranks */}
      {profile?.leaderboard_ranks && Object.keys(profile.leaderboard_ranks).length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Leaderboard Rankings</h2>
          <div className="space-y-2">
            {tasks?.tasks
              ?.filter((task) => profile.leaderboard_ranks[task.id])
              .sort((a, b) => (profile.leaderboard_ranks[a.id] || 999) - (profile.leaderboard_ranks[b.id] || 999))
              .map((task) => (
                <div key={task.id} className="flex items-center justify-between p-3 rounded-lg bg-bg">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-sm font-bold text-accent">
                      #{profile.leaderboard_ranks[task.id]}
                    </span>
                    <span className="font-medium text-text-primary">{task.name}</span>
                  </div>
                  <span className="text-sm text-text-secondary">
                    Best: {profile.best_scores?.[task.id]?.toFixed(3) || 'N/A'}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
