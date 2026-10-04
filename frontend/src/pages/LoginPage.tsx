import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi, tokenStore } from '../services/authApi';

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await authApi.login(username.trim());
      tokenStore.save(data.access_token, data.username);
      navigate('/investigations', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <span className="text-5xl" role="img" aria-label="TraceGraph">🛡</span>
          <h1 className="text-2xl font-bold text-on-surface tracking-tight">TraceGraph</h1>
          <p className="text-sm text-on-surface-muted">SOC Investigation Platform</p>
        </div>

        {/* Card */}
        <div className="bg-surface-container rounded-2xl p-6 shadow-sentinel-md">
          <h2 className="text-base font-semibold text-on-surface mb-1">Sign in</h2>
          <p className="text-xs text-on-surface-muted mb-5">
            Enter any username to get a session token.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-on-surface-muted mb-1" htmlFor="username">
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                className="input-ghost w-full"
                placeholder="e.g. analyst"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoFocus
                required
              />
            </div>

            {error && (
              <p className="text-xs text-error bg-error-container/20 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={!username.trim() || loading}
              className="btn-primary w-full"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-on-surface-muted mt-6">
          Token is stored in localStorage and sent as{' '}
          <code className="font-mono bg-surface-highest px-1 rounded">Authorization: Bearer</code>
          {' '}on every request.
        </p>
      </div>
    </div>
  );
}
