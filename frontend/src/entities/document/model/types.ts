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
