import { useEffect, useCallback, useRef } from 'react';
import { useScreenStore } from '@/store/screen';
import { createScreen, updateScreen } from '@/api/screens';
import type {
  CreateScreenRequest,
  UpdateScreenRequest,
} from '@/types/screener';

const AUTO_SAVE_INTERVAL_MS = 30_000;

export function useScreenDraft() {
  const {
    draftFilterJson,
    selectedScreenId,
    lastSavedAt,
    hasUnsavedChanges,
    setDraftFilterJson,
    setLastSavedAt,
    setHasUnsavedChanges,
    setIsSaving,
  } = useScreenStore();

  const autoSaveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-save draft every 30s if there are unsaved changes
  useEffect(() => {
    if (autoSaveTimerRef.current) {
      clearInterval(autoSaveTimerRef.current);
    }

    autoSaveTimerRef.current = setInterval(() => {
      if (hasUnsavedChanges && draftFilterJson) {
        handleSave();
      }
    }, AUTO_SAVE_INTERVAL_MS);

    return () => {
      if (autoSaveTimerRef.current) {
        clearInterval(autoSaveTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasUnsavedChanges, draftFilterJson]);

  const handleSave = useCallback(async () => {
    if (!draftFilterJson) return;

    setIsSaving(true);
    try {
      if (selectedScreenId) {
        // Update existing screen
        await updateScreen(selectedScreenId, {
          filter_json: draftFilterJson,
        } as UpdateScreenRequest);
      }
      setLastSavedAt(new Date().toISOString());
      setHasUnsavedChanges(false);
    } catch (error) {
      // Save failed - keep unsaved flag so retry happens
      console.error('Auto-save failed:', error);
    } finally {
      setIsSaving(false);
    }
  }, [
    draftFilterJson,
    selectedScreenId,
    setIsSaving,
    setLastSavedAt,
    setHasUnsavedChanges,
  ]);

  const handleCreateNew = useCallback(
    async (data: CreateScreenRequest) => {
      setIsSaving(true);
      try {
        const result = await createScreen(data);
        setDraftFilterJson(data.filter_json);
        setLastSavedAt(new Date().toISOString());
        setHasUnsavedChanges(false);
        return result;
      } finally {
        setIsSaving(false);
      }
    },
    [setDraftFilterJson, setLastSavedAt, setHasUnsavedChanges, setIsSaving]
  );

  const handleDiscard = useCallback(() => {
    setDraftFilterJson('');
    setHasUnsavedChanges(false);
  }, [setDraftFilterJson, setHasUnsavedChanges]);

  return {
    draftFilterJson,
    hasUnsavedChanges,
    lastSavedAt,
    setDraftFilterJson,
    save: handleSave,
    createNew: handleCreateNew,
    discard: handleDiscard,
  };
}
