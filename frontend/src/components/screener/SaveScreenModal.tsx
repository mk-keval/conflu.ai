import { useState } from 'react';
import { createScreen } from '@/api/screens';
import type { CreateScreenRequest } from '@/types/screener';

interface SaveScreenModalProps {
  open: boolean;
  onClose: () => void;
  filterJson: string;
  onSaved: () => void;
}

export function SaveScreenModal({ open, onClose, filterJson, onSaved }: SaveScreenModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const handleSave = async () => {
    if (!name.trim() || !filterJson) return;
    setSaving(true);
    try {
      const data: CreateScreenRequest = {
        name: name.trim(),
        description: description.trim(),
        filter_json: filterJson,
        is_public: isPublic,
      };
      await createScreen(data);
      onSaved();
      onClose();
      setName('');
      setDescription('');
      setIsPublic(false);
    } catch (error) {
      console.error('Failed to save screen:', error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-dark-800 p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-white">Save Screen Configuration</h2>

        <div className="mb-4">
          <label className="mb-1 block text-sm text-gray-400">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded border border-dark-600 bg-dark-700 px-3 py-2 text-white focus:border-accent focus:outline-none"
            placeholder="My Screener Setup"
            autoFocus
          />
        </div>

        <div className="mb-4">
          <label className="mb-1 block text-sm text-gray-400">Description (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded border border-dark-600 bg-dark-700 px-3 py-2 text-white focus:border-accent focus:outline-none"
            rows={3}
            placeholder="Describe this screen configuration..."
          />
        </div>

        <div className="mb-6 flex items-center gap-2">
          <input
            type="checkbox"
            id="isPublic"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
            className="rounded border-dark-600 bg-dark-700"
          />
          <label htmlFor="isPublic" className="text-sm text-gray-400">
            Make public (shareable)
          </label>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded px-4 py-2 text-sm text-gray-400 hover:text-white"
            disabled={saving}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50"
            disabled={!name.trim() || saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
