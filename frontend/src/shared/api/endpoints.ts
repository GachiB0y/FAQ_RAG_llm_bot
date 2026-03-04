import { api, apiClient } from './client';
import type {
  ChatHistoryResponse,
  ChatRequest,
  ChatResponse,
  Document,
  DocumentListResponse,
  LoginRequest,
  SystemSettings,
  TokenResponse,
  User,
  UserCreate,
  UserUpdate,
} from './types';

// Auth API
export const authApi = {
  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>('/api/v1/auth/login', data);
    apiClient.setTokens(response.data.access_token, response.data.refresh_token);
    return response.data;
  },

  logout: () => {
    apiClient.clearTokens();
  },

  isAuthenticated: () => apiClient.isAuthenticated(),
};

// Users API
export const usersApi = {
  list: async (): Promise<User[]> => {
    const response = await api.get<User[]>('/api/v1/admin/users');
    return response.data;
  },

  create: async (data: UserCreate): Promise<User> => {
    const response = await api.post<User>('/api/v1/admin/users', data);
    return response.data;
  },

  update: async (id: string, data: UserUpdate): Promise<User> => {
    const response = await api.put<User>(`/api/v1/admin/users/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/admin/users/${id}`);
  },
};

// Documents API
export const documentsApi = {
  list: async (): Promise<DocumentListResponse> => {
    const response = await api.get<DocumentListResponse>('/api/v1/admin/documents');
    return response.data;
  },

  get: async (id: string): Promise<Document> => {
    const response = await api.get<Document>(`/api/v1/admin/documents/${id}`);
    return response.data;
  },

  upload: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<Document>('/api/v1/admin/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  replace: async (id: string, file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.put<Document>(`/api/v1/admin/documents/${id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/admin/documents/${id}`);
  },
};

// Chat API
export const chatApi = {
  send: async (data: ChatRequest, sessionId?: string): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/api/v1/chat', data, {
      headers: sessionId ? { 'X-Session-Id': sessionId } : {},
    });
    return response.data;
  },

  getHistory: async (params: {
    limit: number;
    offset: number;
  }): Promise<ChatHistoryResponse> => {
    const response = await api.get<ChatHistoryResponse>('/api/v1/chat/history', {
      params,
    });
    return response.data;
  },

  clearHistory: async (): Promise<{ deleted_count: number }> => {
    const response = await api.delete<{ deleted_count: number }>('/api/v1/chat/history');
    return response.data;
  },
};

// Settings API
export const settingsApi = {
  get: async (): Promise<SystemSettings> => {
    const response = await api.get<SystemSettings>('/api/v1/admin/settings');
    return response.data;
  },

  update: async (data: Partial<SystemSettings>): Promise<{ message: string }> => {
    const response = await api.put<{ message: string }>('/api/v1/admin/settings', data);
    return response.data;
  },
};
