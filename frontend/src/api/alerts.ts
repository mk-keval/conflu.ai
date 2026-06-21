import apiClient from './client';
import type {
  AlertRule,
  AlertHistoryEntry,
  CreateAlertRequest,
  UpdateAlertRequest,
} from '@/types/screener';

export async function listAlerts(): Promise<AlertRule[]> {
  const response = await apiClient.get<AlertRule[]>('/api/v1/alerts');
  return response.data;
}

export async function getAlert(id: string): Promise<AlertRule> {
  const response = await apiClient.get<AlertRule>(`/api/v1/alerts/${id}`);
  return response.data;
}

export async function createAlert(data: CreateAlertRequest): Promise<AlertRule> {
  const response = await apiClient.post<AlertRule>('/api/v1/alerts', data);
  return response.data;
}

export async function updateAlert(
  id: string,
  data: UpdateAlertRequest
): Promise<AlertRule> {
  const response = await apiClient.put<AlertRule>(`/api/v1/alerts/${id}`, data);
  return response.data;
}

export async function deleteAlert(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/alerts/${id}`);
}

export async function toggleAlert(
  id: string,
  isActive: boolean
): Promise<AlertRule> {
  const response = await apiClient.patch<AlertRule>(`/api/v1/alerts/${id}`, {
    is_active: isActive,
  });
  return response.data;
}

export async function getAlertHistory(
  alertId: string,
  limit?: number
): Promise<AlertHistoryEntry[]> {
  const params: Record<string, string | number> = {};
  if (limit) params.limit = limit;
  const response = await apiClient.get<AlertHistoryEntry[]>(
    `/api/v1/alerts/${alertId}/history`,
    { params }
  );
  return response.data;
}

export async function dismissAlertHistory(id: string): Promise<void> {
  await apiClient.patch(`/api/v1/alerts/history/${id}`, { dismissed: true });
}
