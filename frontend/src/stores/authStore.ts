import { create } from 'zustand';
import api from '../api/client';

interface User {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  loginTime: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

const _setLoginTime = () => {
  const t = new Date().toISOString();
  localStorage.setItem('login_time', t);
  return t;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  loginTime: localStorage.getItem('login_time'),

  login: async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    localStorage.setItem('access_token', res.data.access_token);
    localStorage.setItem('refresh_token', res.data.refresh_token);
    const loginTime = _setLoginTime();
    const me = await api.get('/auth/me');
    set({ user: me.data, loginTime });
  },

  register: async (email, password, displayName) => {
    const res = await api.post('/auth/register', {
      email,
      password,
      display_name: displayName || '',
    });
    localStorage.setItem('access_token', res.data.access_token);
    localStorage.setItem('refresh_token', res.data.refresh_token);
    const loginTime = _setLoginTime();
    const me = await api.get('/auth/me');
    set({ user: me.data, loginTime });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('login_time');
    set({ user: null, loginTime: null });
  },

  fetchUser: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ loading: false });
      return;
    }
    try {
      const res = await api.get('/auth/me');
      set({ user: res.data, loading: false, loginTime: localStorage.getItem('login_time') });
    } catch {
      set({ user: null, loading: false });
    }
  },
}));
