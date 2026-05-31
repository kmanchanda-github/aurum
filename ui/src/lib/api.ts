import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE || "";

export const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("aurum_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("aurum_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Auth
export const authApi = {
  register: (data: { email: string; password: string; full_name?: string; risk_tolerance?: string }) =>
    api.post("/api/auth/register", data),
  login: (data: { email: string; password: string }) => api.post("/api/auth/login", data),
  me: () => api.get("/api/auth/me"),
};

// Chat
export const chatApi = {
  createConversation: (title?: string) => api.post("/api/chat/conversations", { title }),
  listConversations: () => api.get("/api/chat/conversations"),
  getMessages: (id: string) => api.get(`/api/chat/conversations/${id}/messages`),
  deleteConversation: (id: string) => api.delete(`/api/chat/conversations/${id}`),
};

// Portfolio
export const portfolioApi = {
  list: () => api.get("/api/portfolio"),
  create: (name: string) => api.post("/api/portfolio", { name }),
  get: (id: string) => api.get(`/api/portfolio/${id}`),
  addHolding: (portfolioId: string, data: object) =>
    api.post(`/api/portfolio/${portfolioId}/holdings`, data),
  updateHolding: (portfolioId: string, holdingId: string, data: object) =>
    api.patch(`/api/portfolio/${portfolioId}/holdings/${holdingId}`, data),
  deleteHolding: (portfolioId: string, holdingId: string) =>
    api.delete(`/api/portfolio/${portfolioId}/holdings/${holdingId}`),
  performance: (id: string, period = "1mo") =>
    api.get(`/api/portfolio/${id}/performance`, { params: { period } }),
};

// Market
export const marketApi = {
  quote: (symbol: string) => api.get(`/api/market/quote/${symbol}`),
  history: (symbol: string, period = "1mo", interval = "1d") =>
    api.get(`/api/market/history/${symbol}`, { params: { period, interval } }),
  indices: () => api.get("/api/market/indices"),
  search: (q: string) => api.get("/api/market/search", { params: { q } }),
  movers: (type = "gainers") => api.get("/api/market/movers", { params: { type } }),
};

// Goals
export const goalsApi = {
  list: () => api.get("/api/goals"),
  create: (data: object) => api.post("/api/goals", data),
  update: (id: string, data: object) => api.patch(`/api/goals/${id}`, data),
  delete: (id: string) => api.delete(`/api/goals/${id}`),
  projection: (id: string, years = 10) =>
    api.post(`/api/goals/${id}/projection`, null, { params: { years } }),
};

// News
export const newsApi = {
  get: (query = "financial markets", limit = 10) =>
    api.get("/api/news", { params: { query, limit } }),
};

// Settings
export const settingsApi = {
  get: () => api.get("/api/settings"),
  update: (data: object) => api.patch("/api/settings", data),
  adapterHealth: () => api.get("/api/settings/adapters/health"),
};

// Admin
export const adminApi = {
  stats: () => api.get("/api/admin/stats"),
  conversations: (params?: { page?: number; per_page?: number; user_id?: string }) =>
    api.get("/api/admin/conversations", { params }),
  conversationTrace: (id: string) => api.get(`/api/admin/conversations/${id}/trace`),
  users: (params?: { page?: number; per_page?: number }) =>
    api.get("/api/admin/users", { params }),
};
