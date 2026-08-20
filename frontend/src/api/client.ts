import axios from 'axios';
import type { AxiosRequestConfig } from 'axios';
import type { ApiErrorResponse, ApiResponse } from '@/types/api';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(
  (config) => {
    config.headers.set('X-Request-ID', crypto.randomUUID());
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.data?.error) {
      const apiError = error.response.data as ApiErrorResponse;
      return Promise.reject(apiError.error);
    }
    return Promise.reject({
      code: 'NETWORK_ERROR',
      message: error.message || 'An unexpected network error occurred',
      details: null,
      request_id: null,
    });
  }
);

export default apiClient;

// ── Envelope unwrapping ──────────────────────────────────────────────────────
// The response interceptor returns the HTTP body. Most endpoints wrap the
// payload in the standard ApiResponse envelope ({ data, meta }); a few (e.g.
// the TV screener) return the payload directly. `unwrap` normalizes both so
// callers always receive the unwrapped payload.

/** True when the body is a standard ApiResponse envelope ({ data, meta }). */
function isEnvelope<T>(body: unknown): body is ApiResponse<T> {
  return (
    typeof body === 'object' &&
    body !== null &&
    'data' in body &&
    'meta' in body
  );
}

/** Unwrap the ApiResponse envelope if present; otherwise return the raw body. */
export function unwrap<T>(body: ApiResponse<T> | T): T {
  return isEnvelope<T>(body) ? body.data : (body as T);
}

async function request<T>(promise: Promise<unknown>): Promise<T> {
  const body = (await promise) as ApiResponse<T> | T;
  return unwrap<T>(body);
}

/** GET that unwraps the ApiResponse envelope (or returns the raw body). */
export function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return request<T>(apiClient.get(url, config));
}

/** POST that unwraps the ApiResponse envelope (or returns the raw body). */
export function apiPost<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return request<T>(apiClient.post(url, data, config));
}

/** PUT that unwraps the ApiResponse envelope (or returns the raw body). */
export function apiPut<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return request<T>(apiClient.put(url, data, config));
}

/** PATCH that unwraps the ApiResponse envelope (or returns the raw body). */
export function apiPatch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return request<T>(apiClient.patch(url, data, config));
}

/** DELETE that unwraps the ApiResponse envelope (or returns the raw body). */
export function apiDelete<T = void>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return request<T>(apiClient.delete(url, config));
}
