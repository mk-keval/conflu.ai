import { useState } from 'react';
import { generateShareToken } from '@/api/sharing';

interface ShareModalProps {
  open: boolean;
  onClose: () => void;
  screenId: string;
}

export function ShareModal({ open, onClose, screenId }: ShareModalProps) {
  const [token, setToken] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [expiryDays, setExpiryDays] = useState(7);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!open) return null;

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await generateShareToken(screenId, expiryDays);
      setToken(result.token);
      setShareUrl(result.url);
    } catch (error) {
      console.error('Failed to generate share token:', error);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (shareUrl) {
      try {
        await navigator.clipboard.writeText(
          `${window.location.origin}${shareUrl}`
        );
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        console.error('Failed to copy to clipboard');
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-dark-800 w-full max-w-md rounded-lg p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Share Screen Configuration
        </h2>

        <div className="mb-4">
          <label className="mb-1 block text-sm text-gray-400">
            Expires in (days)
          </label>
          <input
            type="number"
            min={1}
            max={365}
            value={expiryDays}
            onChange={(e) => setExpiryDays(Number(e.target.value))}
            className="border-dark-600 bg-dark-700 w-full rounded border px-3 py-2 text-white focus:border-accent focus:outline-none"
          />
        </div>

        {!token ? (
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full rounded bg-accent px-4 py-2 font-medium text-white hover:bg-accent/90 disabled:opacity-50"
          >
            {generating ? 'Generating...' : 'Generate Share Link'}
          </button>
        ) : (
          <div>
            <div className="mb-3">
              <label className="mb-1 block text-sm text-gray-400">
                Share URL
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={`${window.location.origin}${shareUrl}`}
                  className="border-dark-600 bg-dark-700 flex-1 rounded border px-3 py-2 text-sm text-white"
                />
                <button
                  onClick={handleCopy}
                  className="bg-dark-600 rounded px-3 py-2 text-sm text-gray-300 hover:text-white"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <p className="text-xs text-gray-500">
              Anyone with this link can view this screen configuration.
              {expiryDays > 0 && ` Link expires in ${expiryDays} day(s).`}
            </p>
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
