export type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error';
export type PageKey = 'chat' | 'retrieve' | 'diagnosis' | 'knowledge';
export type RiskLevel = 'low' | 'medium' | 'high' | 'unknown';

export type Metrics = {
  pipeline_status?: string;
  session_id?: string;
};

export type Conversation = { id: string; title: string; meta: string | { label?: string; [key: string]: unknown } };

export type Trace = {
  keyword_rank?: number | null;
  semantic_rank?: number | null;
  rrf_score?: number;
  [key: string]: string | number | null | undefined;
};

export type Source = {
  id?: string;
  title?: string;
  component?: string;
  doc_type?: string;
  content_type?: string;
  source?: string;
  page?: number;
  score?: number;
  trace?: Trace;
  ocr_text?: string;
  visual_caption?: string;
  symptoms?: string[];
  causes?: string[];
  steps?: string[];
  safety_level?: string;
};

export type CandidateCause = { cause?: string; confidence?: number; evidence?: string; check_method?: string };
export type RepairStep = { step?: number; action?: string; source?: string; expected_result?: string; risk?: string };
export type Citation = { title?: string; source?: string; page?: number; score?: number };

export type DiagnosisResult = {
  summary?: string;
  system?: string;
  component?: string;
  fault_domain?: string;
  alarm_code?: string;
  candidate_causes?: CandidateCause[];
  repair_steps?: RepairStep[];
  tools?: string[];
  spare_parts?: string[];
  risk_level?: RiskLevel;
  safety_warnings?: string[];
  citations?: Citation[];
  next_action?: string;
};

export type ChatResult = {
  session_id?: string;
  query?: string;
  answer?: string;
  confidence?: number;
  risk_level?: RiskLevel;
  safety_notice?: string;
  evidence?: Source[];
  retrieval_trace?: Record<string, unknown>;
  ticket_summary?: string;
  follow_up_questions?: string[];
  memory_summary?: string;
  llm_used?: boolean;
  diagnosis_result?: DiagnosisResult;
};

export type RetrieveResponse = { query?: string; top_k?: number; results?: Source[] };
export type DocsResponse = { count?: number; items?: Source[] };
export type ChatMessage = { id: string; role: 'user' | 'assistant'; text: string; createdAt: string; result?: ChatResult; retryQuery?: string; error?: string };
