import { create } from 'zustand';
import api from '../services/api';

const useAuthStore = create((set, get) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  loading: false,
  error: null,

  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/auth/login', { email, password });
      const { access_token } = response.data.data;
      localStorage.setItem('access_token', access_token);
      
      set({ isAuthenticated: true, loading: false });
      
      // Fetch user profile immediately after login
      await get().fetchUser();
      
      return true;
    } catch (err) {
      set({ 
        error: err.response?.data?.message || 'Login failed. Please check your credentials.', 
        loading: false 
      });
      return false;
    }
  },

  register: async (userData) => {
    set({ loading: true, error: null });
    try {
      await api.post('/auth/register', userData);
      set({ loading: false });
      return true;
    } catch (err) {
      set({ 
        error: err.response?.data?.message || 'Registration failed. Please try again.', 
        loading: false 
      });
      return false;
    }
  },

  logout: () => {
    localStorage.removeItem('access_token');
    set({ user: null, isAuthenticated: false });
    window.location.href = '/login';
  },

  fetchUser: async () => {
    if (!localStorage.getItem('access_token')) return;
    try {
      const response = await api.get('/users/me'); 
      set({ user: response.data.data, isAuthenticated: true });
    } catch (err) {
      console.error('Failed to fetch user profile:', err);
      // If profile fetching fails, we might still be authenticated, but without user info
      // Or we can choose to logout if it's a 401
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token');
        set({ isAuthenticated: false, user: null });
      }
    }
  }
}));

export default useAuthStore;
