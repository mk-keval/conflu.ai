import { apiGet, apiPost } from './client';
import type { SavedScreen, ShareTokenResponse } from '@/types/screener';

export async function generateShareToken(
  screenId: string,
  expiryDays?: number
): Promise<ShareTokenResponse> {
  return apiPost<ShareTokenResponse>(`/api/v1/screens/${screenId}/share`, {
    expiry_days: expiryDays,
  });
}

export async function resolveSharedScreen(token: string): Promise<SavedScreen> {
  return apiGet<SavedScreen>(`/api/v1/shared/${token}`);
}
