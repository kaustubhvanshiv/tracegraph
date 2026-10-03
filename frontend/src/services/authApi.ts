import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  username: string;
}

export const authApi = {
  /** POST /api/auth/token — issue a JWT for the given username */
  login: async (username: string): Promise<TokenResponse> => {
    const { data } = await axios.post<TokenResponse>(
      `${BASE_URL}/api/auth/token`,
      { username },
      { headers: { 'Content-Type': 'application/json' } }
    );
    return data;
  },
};

const TOKEN_KEY = 'tg_token';
const USER_KEY  = 'tg_user';

export const tokenStore = {
  save: (token: string, username: string) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, username);
  },
  getToken: (): string | null => localStorage.getItem(TOKEN_KEY),
  getUser:  (): string | null => localStorage.getItem(USER_KEY),
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  isLoggedIn: (): boolean => !!localStorage.getItem(TOKEN_KEY),
};
