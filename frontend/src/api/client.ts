import axios from 'axios';

/**
 * Shared axios instance for the grouped API helper modules.
 *
 * ``VITE_API_BASE_URL`` may be provided as either a bare origin
 * (``http://127.0.0.1:8000``) or one that already ends in ``/api``; the
 * trailing ``/api`` is stripped so helpers can call paths like ``/api/...``.
 */
const baseURL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/api\/?$/, '');

const client = axios.create({ baseURL, withCredentials: true });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default client;
