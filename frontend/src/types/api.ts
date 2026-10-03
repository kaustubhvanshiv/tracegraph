export interface SuccessResponse<T> {
  status: 'success';
  data: T;
}

export interface ErrorResponse {
  status: 'error';
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export type ApiResponse<T> = SuccessResponse<T> | ErrorResponse;
