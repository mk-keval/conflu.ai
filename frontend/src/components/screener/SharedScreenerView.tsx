import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { resolveSharedScreen } from '@/api/sharing';
import type { SavedScreen } from '@/types/screener';

export function SharedScreenerView() {
  const { token } = useParams<{ token: string }>();
  const [screen, setScreen] = useState<SavedScreen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError('No share token provided');
      setLoading(false);
      return;
    }

    const loadShared = async () => {
      try {
        const data = await resolveSharedScreen(token);
        setScreen(data as unknown as SavedScreen);
      } catch (err) {
        setError('This share link is invalid or has expired.');
      } finally {
        setLoading(false);
      }
    };

    loadShared();
  }, [token]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-gray-400">Loading shared screen...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="rounded-lg border border-red-800 bg-red-900/20 p-6 text-center">
          <h2 className="mb-2 text-lg font-semibold text-red-400">Access Denied</h2>
          <p className="text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  if (!screen) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-gray-400">Screen not found.</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-6">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-white">{screen.name}</h1>
        {screen.description && (
          <p className="mt-1 text-sm text-gray-400">{screen.description}</p>
        )}
        <div className="mt-2 flex gap-3 text-xs text-gray-500">
          <span>Version {screen.version}</span>
          <span>Shared configuration</span>
        </div>
      </div>

      <div className="flex-1 rounded-lg border border-dark-600 bg-dark-800 p-4">
        <h3 className="mb-3 text-sm font-medium text-gray-400">Configuration</h3>
        <pre className="overflow-auto rounded bg-dark-900 p-3 text-xs text-gray-300">
          {screen.filter_json}
        </pre>
      </div>
    </div>
  );
}
