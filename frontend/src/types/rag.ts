export type DocumentSummary = {
  id: string;
  filename: string;
  content_type: string;
  status: string;
  created_at: string;
  characters: number;
  size_bytes: number;
  chunk_count: number;
};

export type UserProfile = {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'user';
  is_verified: boolean;
  created_at: string;
};

export type AuthResponse = {
  user: UserProfile;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type DocumentDetail = DocumentSummary & {
  file_path: string;
  metadata: Record<string, string | number>;
};

export type DocumentPreview = {
  id: string;
  filename: string;
  content_type: string;
  render_mode: 'pdf' | 'text';
  text: string;
  file_url: string;
};

export type UploadStatusResponse = {
  status: string;
  message: string;
  document: DocumentSummary;
};

export type Citation = {
  document_id: string;
  filename: string;
  chunk_id: string;
  text: string;
  score: number;
  metadata: Record<string, string | number>;
};

export type SourceReference = {
  document: string;
  page: number | null;
};

export type StructuredAnswer = {
  answer: string;
  summary: string;
  key_points: string[];
  sources: SourceReference[];
  confidence: 'High' | 'Medium' | 'Low';
  follow_up_questions: string[];
};

export type AnswerResponse = StructuredAnswer & {
  citations: Citation[];
  session_id: string;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  attachments?: DocumentSummary[];
  structured?: StructuredAnswer;
  citations?: Citation[];
  isStreaming?: boolean;
};

export type ChatThread = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: string;
  createdAt?: string;
};

export type ServerMessage = {
  id: string;
  chat_id: string;
  role: 'user' | 'assistant';
  content: string;
  structured?: StructuredAnswer | null;
  created_at: string;
};

export type ServerConversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ServerMessage[];
};

export type ProviderStatus = {
  provider: string;
  masked_key: string | null;
  is_configured: boolean;
  is_custom: boolean;
  has_system_fallback: boolean;
  updated_at: string | null;
};
