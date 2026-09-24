import { useEffect, useState } from 'react';
import { listScreens, getScreen, deleteScreen } from '@/api/screens';
import type { SavedScreenListItem } from '@/types/screener';

interface LoadScreenModalProps {
  open: boolean;
  onClose: () => void;
  onLoad: (screen: SavedScreenListItem) => void;
}

export function LoadScreenModal({
  open,
  onClose,
  onLoad,
}: LoadScreenModalProps) {
  const [screens, setScreens] = useState<SavedScreenListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      loadScreens();
    }
  }, [open]);

  const loadScreens = async () => {
    setLoading(true);
    try {
      const data = await listScreens();
      setScreens(data);
    } catch (error) {
      console.error('Failed to load screens:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLoad = async (item: SavedScreenListItem) => {
    try {
      const fullScreen = await getScreen(item.id);
      onLoad(fullScreen);
      onClose();
    } catch (error) {
      console.error('Failed to load screen details:', error);
    }
  };

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await deleteScreen(id);
      setScreens((prev) => prev.filter((s) => s.id !== id));
    } catch (error) {
      console.error('Failed to delete screen:', error);
    } finally {
      setDeleting(null);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-dark-800 w-full max-w-lg rounded-lg p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Load Saved Screen
        </h2>

        {loading ? (
          <div className="py-8 text-center text-gray-400">Loading...</div>
        ) : screens.length === 0 ? (
          <div className="py-8 text-center text-gray-400">
            No saved screens yet.
          </div>
        ) : (
          <div className="max-h-80 space-y-2 overflow-y-auto">
            {screens.map((screen) => (
              <div
                key={screen.id}
                className="border-dark-600 flex items-center justify-between rounded border p-3"
              >
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => handleLoad(screen)}
                >
                  <div className="font-medium text-white">{screen.name}</div>
                  <div className="text-xs text-gray-400">
                    v{screen.version} &middot;{' '}
                    {new Date(screen.updated_at).toLocaleDateString()}
                    {screen.tags.length > 0 && ` · ${screen.tags.join(', ')}`}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(screen.id);
                  }}
                  className="ml-2 text-xs text-gray-500 hover:text-loss"
                  disabled={deleting === screen.id}
                  title="Delete"
                >
                  {deleting === screen.id ? '...' : '✕'}
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm text-gray-400 hover:text-white"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
