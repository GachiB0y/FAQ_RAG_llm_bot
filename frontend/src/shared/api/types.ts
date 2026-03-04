// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// User types
export interface User {
  id: string;
  email: string;
  role: 'admin' | 'user';
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  role?: 'admin' | 'user';
}

export interface UserUpdate {
  email?: string;
  password?: string;
  role?: 'admin' | 'user';
  is_active?: boolean;
}

// Document types
export interface Document {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: 'processing' | 'ready' | 'error';
  error_message: string | null;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
}

// Chat types
export interface ChatRequest {
  message: string;
}

export interface ChatSource {
  document: string;
  page: number | null;
  chunk: string;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  confidence: number;
  session_id: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// Settings types
export interface SystemSettings {
  llm_provider: 'openai' | 'anthropic' | 'ollama';
  embedding_provider: 'openai' | 'local';
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  similarity_threshold: number;
  top_k_results: number;
}
