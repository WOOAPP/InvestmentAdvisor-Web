import api from './client';

export const getAdminUsers = () => api.get('/admin/users');
export const getAdminActivity = (limit = 50) => api.get(`/admin/activity?limit=${limit}`);
export const getAdminStats = () => api.get('/admin/stats');
