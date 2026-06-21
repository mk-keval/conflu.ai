import axios from 'axios';
import type { ApiErrorResponse } from '@/types/api';

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
