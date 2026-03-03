/**
 * RYX API Client — Centralisé
 * Toutes les requêtes API passent par ici.
 */

import axios, { AxiosInstance } from "axios";

const API_BASE = "/api";

function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: API_BASE,
    headers: { "Content-Type": "application/json" },
    timeout: 30000,
  });

  // Intercepteur auth
  client.interceptors.request.use((config) => {
    const token = localStorage.getItem("ryx_access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // Intercepteur erreurs
  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response?.status === 401) {
        // Tenter refresh token
        const refreshed = await tryRefreshToken();
        if (!refreshed) {
          localStorage.removeItem("ryx_access_token");
          localStorage.removeItem("ryx_refresh_token");
          window.location.href = "/auth/login";
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
}

async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem("ryx_refresh_token");
  if (!refreshToken) return false;
  try {
    const response = await axios.post(`${API_BASE}/auth/refresh`, {
      refresh_token: refreshToken,
    });
    localStorage.setItem("ryx_access_token", response.data.access_token);
    return true;
  } catch {
    return false;
  }
}

export const api = createApiClient();

// ─── API functions ────────────────────────────────────────────────────────────

export const authApi = {
  login: (username: string, password: string) =>
    api.post("/auth/token", { username, password }),
  me: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
};

export const patientsApi = {
  list: (params?: { page?: number; per_page?: number; q?: string }) =>
    api.get("/patients", { params }),
  get: (id: string) => api.get(`/patients/${id}`),
  create: (data: unknown) => api.post("/patients", data),
  timeline: (id: string) => api.get(`/patients/${id}/timeline`),
  search: (query: string) => api.post("/patients/search", { query }),
};

export const encountersApi = {
  get: (id: string) => api.get(`/encounters/${id}`),
  create: (data: unknown) => api.post("/encounters", data),
  documents: (id: string) => api.get(`/encounters/${id}/documents`),
  labs: (id: string) => api.get(`/encounters/${id}/labs`),
};

export const reportsApi = {
  getLatest: (encounterId: string) => api.get(`/reports/${encounterId}/latest`),
  generate: (encounterId: string) => api.post(`/reports/${encounterId}/generate`),
  claims: (reportId: string) => api.get(`/reports/${reportId}/claims`),
  updateClaim: (reportId: string, claimId: string, data: unknown) =>
    api.patch(`/reports/${reportId}/claims/${claimId}`, data),
};

export const predictionsApi = {
  get: (patientId: string, window?: string) =>
    api.get(`/predictions/${patientId}`, { params: { window } }),
  compute: (patientId: string) => api.post(`/predictions/${patientId}/compute`),
};

export const searchApi = {
  query: (data: { query: string; context_type?: string; patient_id?: string }) =>
    api.post("/docsearch/query", data),
  status: () => api.get("/docsearch/status"),
};

export const notificationsApi = {
  list: (params?: { page?: number; per_page?: number }) =>
    api.get("/notifications", { params }),
  markRead: (id: string) => api.patch(`/notifications/${id}/read`),
};

export const documentsApi = {
  upload: (formData: FormData) =>
    api.post("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  status: (docId: string) => api.get(`/documents/${docId}/status`),
};
