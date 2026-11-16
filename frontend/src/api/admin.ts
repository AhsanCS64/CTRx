import axios from './client';

/**
 * Admin API utilities
 */

// Users
export const getUsers = async (params?: {search?: string; role?: string; is_active?: boolean}) => {
  const response = await axios.get('/api/admin/users/', { params });
  return response.data;
};

export const setUserActive = async (id: string, isActive: boolean) => {
  const response = await axios.patch(`/api/admin/users/${id}/active`, { is_active: isActive });
  return response.data;
};

// Officials
export const createOfficial = async (payload: {email: string; password: string; full_name: string; level: string; area_id?: string}) => {
  const response = await axios.post('/api/admin/officials', payload);
  return response.data;
};

// Areas
export const getAreas = async () => {
  const response = await axios.get('/api/admin/areas/');
  return response.data;
};

export const createArea = async (payload: {division: string; division_code: string; district: string; district_code: string; name: string; upazila_code: string}) => {
  const response = await axios.post('/api/admin/areas/', payload);
  return response.data;
};

export const updateArea = async (id: string, payload: Partial<any>) => {
  const response = await axios.patch(`/api/admin/areas/${id}`, payload);
  return response.data;
};

// Settings
export const getSettings = async () => {
  const response = await axios.get('/api/admin/settings/');
  return response.data;
};

export const updateSetting = async (key: string, value: string) => {
  const response = await axios.patch(`/api/admin/settings/${key}`, { value });
  return response.data;
};

// Templates
export const getTemplates = async () => {
  const response = await axios.get('/api/admin/templates/');
  return response.data;
};

export const createTemplate = async (payload: {name: string; version: string}) => {
  const response = await axios.post('/api/admin/templates/', payload);
  return response.data;
};

export const setDefaultTemplate = async (id: string) => {
  const response = await axios.post(`/api/admin/templates/${id}/set-default`);
  return response.data;
};

// Audit logs
export const getAuditLogs = async (params?: {actor_id?: string; action?: string; entity_type?: string; date_from?: string; date_to?: string}) => {
  const response = await axios.get('/api/admin/audit-logs/', { params });
  return response.data;
};
