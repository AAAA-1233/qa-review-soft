export type ReviewStatus = "PASS" | "FAIL" | "SKIP" | "UNREVIEWED";
export type AiStatus = "PASS" | "FAIL" | "PENDING";
export type ExportMode = "human_pass" | "ai_pass" | "merged_pass";
export type AIRangeFilter = "HUMAN_UNREVIEWED" | "AI_PENDING" | "ALL";
export type ReviewQueueFilter = "ALL" | "MERGED_PASS" | "MERGED_FAIL" | "MERGED_PENDING";
export type PageKey = "projects" | "import" | "review" | "ai" | "prompts" | "stats" | "export" | "settings";

export interface Project {
  id: string;
  name: string;
  type: string;
  total: number;
  reviewed: number;
  ai_reviewed: number;
  path: string;
  source_path: string;
  media_path?: string;
  created_at: string;
  updated_at: string;
}

export interface Sample {
  id: number;
  external_id: string;
  question: string;
  answer: string;
  media: string[];
  tags: string[];
  review: ReviewStatus;
  ai: AiStatus;
  ai_score: number;
  ai_reason?: string;
  note?: string;
  edited_question?: string;
  edited_answer?: string;
  conversation?: ConversationTurn[];
}

export interface ConversationTurn {
  role: "system" | "user" | "assistant" | "message" | string;
  content: string;
  index?: string;
}

export interface ActionHistory {
  sampleId: number;
  previous: ReviewStatus;
  next: ReviewStatus;
  at: string;
}

export interface ProviderPreset {
  id: string;
  name: string;
  protocol: string;
  base_url: string;
  default_model: string;
  key_hint: string;
}

export interface AIConfig {
  id?: number;
  project_id?: string;
  provider_id: string;
  name: string;
  protocol: string;
  base_url: string;
  model: string;
  api_key: string;
  proxy_url: string;
  temperature: number;
  max_tokens: number;
  timeout: number;
}

export interface PromptTemplate {
  id: number;
  project_id: string;
  name: string;
  content: string;
}

export interface AITask {
  id: number;
  project_id: string;
  config_id: number;
  prompt_id: number;
  status: string;
  range_filter: string;
  total: number;
  completed: number;
  failed: number;
  error?: string;
  updated_at: string;
}

export interface AITaskResult {
  sample_id: number;
  external_id: string;
  question: string;
  ai_status: AiStatus;
  ai_score: number;
  ai_reason?: string;
  review_status: ReviewStatus;
  updated_at: string;
}

export interface Stats {
  review: Record<ReviewStatus, number>;
  ai: Record<AiStatus, number>;
  agreement: number;
  total: number;
}

export interface AuthUser {
  id: number;
  email: string;
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  user: AuthUser;
}
