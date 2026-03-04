import type { ChatSource } from '@shared/api';

export interface ChatMessageItem {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  confidence?: number;
  created_at?: string;
}
