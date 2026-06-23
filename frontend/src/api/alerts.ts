import apiClient from './client';
import type {
  AlertRule,
  AlertHistoryEntry,
  CreateAlertRequest,
  UpdateAlertRequest,
} from '@/types/screener';
import type { ApiResponse } from '@/types/api';

export async function listAlerts(): Promise<AlertRule[]> {
  const response = await apiClient.get<ApiResponse<AlertRule[]>>('/api/v1/alerts') as unknown as ApiResponse<AlertRule[]>;
  return response.data;
}

export async function getAlert(id: string): Promise<AlertRule> {
  const response = await apiClient.get<ApiResponse<AlertRule>>(`/api/v1/alerts/${id}`) as unknown as ApiResponse<AlertRule>;
  return response.data;
}

export async function createAlert(data: CreateAlertRequest): Promise<AlertRule> {
  const response = await apiClient.post<ApiResponse<AlertRule>>('/api/v1/alerts', data) as unknown as ApiResponse<AlertRule>;
  return response.data;
}

export async function updateAlert(
  id: string,
  data: UpdateAlertRequest
): Promise<AlertRule> {
  const response = await apiClient.put<ApiResponse<AlertRule>>(`/api/v1/alerts/${id}`, data) as unknown as ApiResponse<AlertRule>;
  return response.data;
}

export async function deleteAlert(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/alerts/${id}`);
}

export async function toggleAlert(
  id: string,
  isActive: boolean
): Promise<AlertRule> {
  const response = await apiClient.patch<ApiResponse<AlertRule>>(`/api/v1/alerts/${id}`, {
    is_active: isActive,
  }) as unknown as ApiResponse<AlertRule>;
  return response.data;
}

export async function getAlertHistory(
  alertId: string,
  limit?: number
): Promise<AlertHistoryEntry[]> {
  const params: Record<string, string | number> = {};
  if (limit) params.limit = limit;
  const response = await apiClient.get<ApiResponse<AlertHistoryEntry[]>>(
    `/api/v1/alerts/${alertId}/history`,
    { params }
  ) as unknown as ApiResponse<AlertHistoryEntry[]>;
  return response.data;
}

export async function dismissAlertHistory(id: string): Promise<void> {
  await apiClient.patch(`/api/v1/alerts/history/${id}`, { dismissed: true });
}
