import axios from './client';

/**
 * Government API utilities
 */

export const getReviewQueue = async (status?: string, areaId?: string) => {
  const params: any = {};
  if (status) params.status = status;
  if (areaId) params.area_id = areaId;
  const response = await axios.get('/api/ric-applications/', { params });
  return response.data;
};

export const getApplication = async (id: string) => {
  const response = await axios.get(`/api/ric-applications/${id}/`);
  return response.data;
};

export const forwardApp = async (id: string) => {
  const response = await axios.post(`/api/ric-applications/${id}/forward`);
  return response.data;
};

export const rejectApp = async (id: string) => {
  const response = await axios.post(`/api/ric-applications/${id}/reject`);
  return response.data;
};

export const approveApp = async (id: string) => {
  const response = await axios.post(`/api/ric-applications/${id}/approve`);
  return response.data;
};

// Central reject uses the same endpoint as local reject but kept separate for clarity
export const rejectCentralApp = async (id: string) => {
  const response = await axios.post(`/api/ric-applications/${id}/reject`);
  return response.data;
};
