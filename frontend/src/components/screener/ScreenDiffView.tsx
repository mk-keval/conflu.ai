import type { SavedScreenListItem } from '@/types/screener';

interface ScreenDiffViewProps {
  current: SavedScreenListItem | null;
  previous: SavedScreenListItem | null;
  onClose: () => void;
}

export function ScreenDiffView({ current, previous, onClose }: ScreenDiffViewProps) {
  if (!current || !previous) return null;

  const diffFields: { label: string; currentVal: string; prevVal: string }[] = [];

  if (current.name !== previous.name) {
    diffFields.push({
      label: 'Name',
      currentVal: current.name,
      prevVal: previous.name,
    });
  }

  if (current.description !== previous.description) {
    diffFields.push({
      label: 'Description',
      currentVal: current.description || '(empty)',
      prevVal: previous.description || '(empty)',
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-lg bg-dark-800 p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            Version Changes: v{previous.version} → v{current.version}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            ✕
          </button>
        </div>

        {diffFields.length === 0 ? (
          <div className="py-8 text-center text-gray-400">
            No visible changes between versions (metadata only).
          </div>
        ) : (
          <div className="space-y-3">
            {diffFields.map((field, i) => (
              <div key={i} className="rounded border border-dark-600 p-3">
                <div className="mb-1 text-xs font-medium text-gray-500">{field.label}</div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <div className="text-xs text-red-400">Previous (v{previous.version})</div>
                    <div className="text-gray-300 line-through">{field.prevVal}</div>
                  </div>
                  <div>
                    <div className="text-xs text-green-400">Current (v{current.version})</div>
                    <div className="text-gray-100">{field.currentVal}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm text-gray-400 hover:text-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
