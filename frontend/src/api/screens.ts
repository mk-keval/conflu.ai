import apiClient from './client';
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
  const response = await apiClient.get<SavedScreenListItem[]>('/api/v1/screens');
  return response.data;
}

export async function getScreen(id: string): Promise<SavedScreen> {
  const response = await apiClient.get<SavedScreen>(`/api/v1/screens/${id}`);
  return response.data;
}

export async function createScreen(data: CreateScreenRequest): Promise<SavedScreen> {
  const response = await apiClient.post<SavedScreen>('/api/v1/screens', data);
  return response.data;
}

export async function updateScreen(
  id: string,
  data: UpdateScreenRequest
): Promise<SavedScreen> {
  const response = await apiClient.put<SavedScreen>(`/api/v1/screens/${id}`, data);
  return response.data;
}

export async function deleteScreen(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/screens/${id}`);
}

export async function listScreenVersions(
  id: string
): Promise<ScreenVersionSummary[]> {
  const response = await apiClient.get<ScreenVersionSummary[]>(
    `/api/v1/screens/${id}/versions`
  );
  return response.data;
}

export async function getScreenVersion(
  screenId: string,
  version: number
): Promise<SavedScreen> {
  const response = await apiClient.get<SavedScreen>(
    `/api/v1/screens/${screenId}/versions/${version}`
  );
  return response.data;
}

export async function revertToVersion(
  screenId: string,
  version: number
): Promise<SavedScreen> {
  const response = await apiClient.post<SavedScreen>(
    `/api/v1/screens/${screenId}/versions/${version}/revert`
  );
  return response.data;
}

export async function getReplayResult(
  screenConfigId: string,
  version?: number
): Promise<ScreenReplayResult> {
  const params = version ? { version } : {};
  const response = await apiClient.get<ScreenReplayResult>(
    `/api/v1/screens/${screenConfigId}/replay`,
    { params }
  );
  return response.data;
}

export async function startReplay(data: ReplayRequest): Promise<{ result_id: string }> {
  const response = await apiClient.post<{ result_id: string }>(
    '/api/v1/screens/replay',
    data
  );
  return response.data;
}

export async function generateShareToken(
  screenId: string,
  expiryDays?: number
): Promise<ShareTokenResponse> {
  const response = await apiClient.post<ShareTokenResponse>(
    `/api/v1/screens/${screenId}/share`,
    { expiry_days: expiryDays }
  );
  return response.data;
}

export async function getSharedScreen(
  token: string
): Promise<SavedScreen> {
  const response = await apiClient.get<SavedScreen>(
    `/api/v1/shared/${token}`
  );
  return response.data;
}
