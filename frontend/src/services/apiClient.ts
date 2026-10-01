import axios from 'axios';

// Create a configured axios instance
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to unwrap SuccessResponse/ErrorResponse envelopes if needed,
// or just return data directly. We'll return the `.data` part of the axios response,
// which matches our `SuccessResponse` / `ErrorResponse` interfaces from the backend.
apiClient.interceptors.response.use(
  (response) => {
    // Just return the data, which is our API envelope
    return response.data;
  },
  (error) => {
    // For expected errors (400, 401, 403, 404, 503, etc) our backend returns
    // an ErrorResponse JSON body.
    if (error.response && error.response.data) {
      return Promise.reject(error.response.data);
    }
    return Promise.reject(error);
  }
);
