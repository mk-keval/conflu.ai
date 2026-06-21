import apiClient from './client';
import type { SavedScreen, ShareTokenResponse } from '@/types/screener';

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

export async function resolveSharedScreen(
  token: string
): Promise<SavedScreen> {
  const response = await apiClient.get<SavedScreen>(
    `/api/v1/shared/${token}`
  );
  return response.data;
}
