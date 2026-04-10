import { useState, useEffect } from 'react';
import { useAuthStore, useUIStore } from '../stores/episodeStore';
import { login, register } from '../api/client';

export function AuthModal() {
  const { authModalOpen, closeAuthModal, authModalCallback, addToast } = useUIStore();
  const { setAuth } = useAuthStore();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!authModalOpen) return null;

  // Prevent body scroll when modal is open
  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      let response;
      if (mode === 'login') {
        response = await login(username, password);
      } else {
        response = await register(username, password);
      }
      if (response.success && response.token && response.username) {
        setAuth(response.username, response.token);
        addToast(`Successfully ${mode === 'login' ? 'logged in' : 'registered'}!`, 'success');
        closeAuthModal();
        authModalCallback?.();
      } else {
        setError(response.message || 'Authentication failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setUsername('');
    setPassword('');
    setError('');
    closeAuthModal();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={handleClose} aria-hidden="true" />
      <div className="relative w-full max-w-md mx-4 animate-fadeIn">
        <div className="bg-surface rounded-2xl border border-border p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 id="auth-modal-title" className="text-xl font-bold text-text-primary">
              {mode === 'login' ? 'Welcome Back' : 'Create Account'}
            </h2>
            <button onClick={handleClose} className="text-text-secondary hover:text-text-primary transition-colors" aria-label="Close modal">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete={mode === 'login' ? 'username' : 'new-username'}
                className="w-full px-4 py-2 bg-bg border border-border rounded-lg text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent"
                placeholder="Enter username"
                aria-label="Username"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className="w-full px-4 py-2 bg-bg border border-border rounded-lg text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent"
                placeholder="Enter password"
                aria-label="Password"
              />
            </div>
            {error && (
              <div className="p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">{error}</div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 rounded-lg bg-accent/10 text-white font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
              aria-busy={loading}
            >
              {loading ? 'Processing...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
          <div className="mt-4 text-center">
            <button
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              className="text-sm text-text-secondary hover:text-accent transition-colors"
              aria-label={mode === 'login' ? 'Switch to register mode' : 'Switch to login mode'}
            >
              {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
