import { apiDelete, apiGet, apiPost, apiPut } from './client';
import type {
  SavedScreen,
  SavedScreenListItem,
  ScreenVersionSummary,
  CreateScreenRequest,
  UpdateScreenRequest,
  ScreenReplayResult,
  ReplayRequest,
  ShareTokenResponse,
} from '@/types/screener';

export async function listScreens(): Promise<SavedScreenListItem[]> {
  return apiGet<SavedScreenListItem[]>('/api/v1/screens');
}

export async function getScreen(id: string): Promise<SavedScreen> {
  return apiGet<SavedScreen>(`/api/v1/screens/${id}`);
}

export async function createScreen(
  data: CreateScreenRequest
): Promise<SavedScreen> {
  return apiPost<SavedScreen>('/api/v1/screens', data);
}

export async function updateScreen(
  id: string,
  data: UpdateScreenRequest
): Promise<SavedScreen> {
  return apiPut<SavedScreen>(`/api/v1/screens/${id}`, data);
}

export async function deleteScreen(id: string): Promise<void> {
  await apiDelete(`/api/v1/screens/${id}`);
}

export async function listScreenVersions(
  id: string
): Promise<ScreenVersionSummary[]> {
  return apiGet<ScreenVersionSummary[]>(`/api/v1/screens/${id}/versions`);
}

export async function getScreenVersion(
  screenId: string,
  version: number
): Promise<SavedScreen> {
  return apiGet<SavedScreen>(`/api/v1/screens/${screenId}/versions/${version}`);
}

export async function revertToVersion(
  screenId: string,
  version: number
): Promise<SavedScreen> {
  return apiPost<SavedScreen>(
    `/api/v1/screens/${screenId}/versions/${version}/revert`
  );
}

export async function getReplayResult(
  screenConfigId: string,
  version?: number
): Promise<ScreenReplayResult> {
  const params = version ? { version } : {};
  return apiGet<ScreenReplayResult>(
    `/api/v1/screens/${screenConfigId}/replay`,
    { params }
  );
}

export async function startReplay(
  data: ReplayRequest
): Promise<{ result_id: string }> {
  return apiPost<{ result_id: string }>('/api/v1/screens/replay', data);
}

export async function generateShareToken(
  screenId: string,
  expiryDays?: number
): Promise<ShareTokenResponse> {
  return apiPost<ShareTokenResponse>(`/api/v1/screens/${screenId}/share`, {
    expiry_days: expiryDays,
  });
}

export async function getSharedScreen(token: string): Promise<SavedScreen> {
  return apiGet<SavedScreen>(`/api/v1/shared/${token}`);
}
