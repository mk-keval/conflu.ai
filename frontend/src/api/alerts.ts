import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client';
import type {
  AlertRule,
  AlertHistoryEntry,
  CreateAlertRequest,
  UpdateAlertRequest,
} from '@/types/screener';

export async function listAlerts(): Promise<AlertRule[]> {
  return apiGet<AlertRule[]>('/api/v1/alerts');
}

export async function getAlert(id: string): Promise<AlertRule> {
  return apiGet<AlertRule>(`/api/v1/alerts/${id}`);
}

export async function createAlert(
  data: CreateAlertRequest
): Promise<AlertRule> {
  return apiPost<AlertRule>('/api/v1/alerts', data);
}

export async function updateAlert(
  id: string,
  data: UpdateAlertRequest
): Promise<AlertRule> {
  return apiPut<AlertRule>(`/api/v1/alerts/${id}`, data);
}

export async function deleteAlert(id: string): Promise<void> {
  await apiDelete(`/api/v1/alerts/${id}`);
}

export async function toggleAlert(
  id: string,
  isActive: boolean
): Promise<AlertRule> {
  return apiPatch<AlertRule>(`/api/v1/alerts/${id}`, {
    is_active: isActive,
  });
}

export async function getAlertHistory(
  alertId: string,
  limit?: number
): Promise<AlertHistoryEntry[]> {
  const params: Record<string, string | number> = {};
  if (limit) params.limit = limit;
  return apiGet<AlertHistoryEntry[]>(`/api/v1/alerts/${alertId}/history`, {
    params,
  });
}

export async function dismissAlertHistory(id: string): Promise<void> {
  await apiPatch(`/api/v1/alerts/history/${id}`, { dismissed: true });
}
