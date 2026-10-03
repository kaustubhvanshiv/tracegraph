import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT on every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('tg_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 globally
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('tg_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/** Unwrap SuccessResponse envelope or throw */
export function unwrap<T>(data: { status: string; data?: T }): T {
  if (data.status !== 'success' || data.data === undefined) {
    throw new Error('Unexpected API response shape');
  }
  return data.data;
}
