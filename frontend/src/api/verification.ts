import axios from './client';

/**
 * Verification / Auth API utilities
 */

export const login = async (email: string, password: string): Promise<string> => {
  const response = await axios.post('/api/auth/login', { email, password });
  // Assuming API returns { access_token: string }
  return response.data.access_token;
};

export const registerTenant = async (payload: { email: string; password: string; full_name: string; national_id: string }) => {
  const response = await axios.post('/api/auth/register/tenant', payload);
  return response.data;
};

export const registerLandlord = async (payload: { email: string; password: string; full_name: string }) => {
  const response = await axios.post('/api/auth/register/landlord', payload);
  return response.data;
};
