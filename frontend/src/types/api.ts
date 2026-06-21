export interface MetaInfo {
  timestamp: string;
  request_id: string;
  duration_ms: number | null;
}

export interface ApiResponse<T> {
  data: T;
  meta: MetaInfo;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  request_id: string | null;
}

export interface ApiErrorResponse {
  error: ErrorDetail;
}
