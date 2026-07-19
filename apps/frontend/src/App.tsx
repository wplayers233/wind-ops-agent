/// <reference types="vite/client" />

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';

type LoadState = 'idle' | 'loading' | 'success' | 'empty' | 'error';
type PageKey = 'chat' | 'retrieve' | 'diagnosis' | 'knowledge';
type RiskLevel = 'low' | 'medium' | 'high' | 'unknown';

type Metrics = {
  pipeline_status?: string;
  session_id?: string;
};

type Conversation = { id: string; title: string; meta: string | { label?: string; [key: string]: unknown } };

type Trace = {
  keyword_rank?: number | null;
  semantic_rank?: number | null;
  rrf_score?: number;
  [key: string]: string | number | null | undefined;
};

type Source = {
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

type CandidateCause = { cause?: string; confidence?: number; evidence?: string; check_method?: string };
type RepairStep = { step?: number; action?: string; source?: string; expected_result?: string; risk?: string };
type Citation = { title?: string; source?: string; page?: number; score?: number };

type DiagnosisResult = {
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

type ChatResult = {
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

type RetrieveResponse = { query?: string; top_k?: number; results?: Source[] };
type DocsResponse = { count?: number; items?: Source[] };
type ChatMessage = { id: string; role: 'user' | 'assistant'; text: string; createdAt: string; result?: ChatResult; retryQuery?: string; error?: string };

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || 'http://127.0.0.1:8000';

const navItems: { key: PageKey; icon: string; label: string }[] = [
  { key: 'chat', icon: '✦', label: '问答' },
  { key: 'retrieve', icon: '⌕', label: '检索' },
  { key: 'diagnosis', icon: '◈', label: '诊断' },
  { key: 'knowledge', icon: '▤', label: '知识库' },
];

const defaultMetrics: Metrics = { pipeline_status: '系统运行正常', session_id: 'demo-session' };

function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function text(value: unknown, fallback = '未返回') {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function metaText(value: Conversation['meta']) {
  if (typeof value === 'string') return value;
  return text(value?.label, '暂无元信息');
}

function numberText(value: unknown, digits = 2, fallback = '未返回') {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : fallback;
}

function normalizeScore(score: unknown) {
  if (typeof score !== 'number' || !Number.isFinite(score)) return 0;
  return Math.max(0, Math.min(1, score > 1 ? score / 100 : score));
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const body = await response.text();
  if (!response.ok) throw new Error(body || `请求失败：HTTP ${response.status}`);
  return (body ? JSON.parse(body) : {}) as T;
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><strong>{title}</strong><span>{detail}</span></div>;
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-state"><strong>请求失败</strong><span>{message}</span>{onRetry && <button type="button" onClick={onRetry}>重试</button>}</div>;
}

function DocCard({ doc, index }: { doc: Source; index: number }) {
  const score = normalizeScore(doc.score);
  const trace = doc.trace ?? {};
  return (
    <article className="doc-card">
      <div className={`doc-icon ${(doc.doc_type ?? 'doc').toLowerCase()}`}>{text(doc.doc_type, 'DOC')}</div>
      <div className="doc-content">
        <div className="doc-title-row">
          <strong>{text(doc.title)}</strong>
          <div className="doc-meta-inline">
            <span>#{index + 1}</span>
            <span>{text(doc.doc_type, 'DOC')}</span>
          </div>
        </div>
        <div className="doc-primary-meta">
          <span>{text(doc.component, '未知部件')}</span>
          <span>{text(doc.source, '未知来源')}</span>
          <span>第 {typeof doc.page === 'number' ? doc.page : '未知'} 页</span>
        </div>
        <div className="doc-score-row">
          <div className="doc-score-label">
            <span>分数</span>
            <strong>{numberText(doc.score)}</strong>
          </div>
          <div className="relevance-bar"><i style={{ width: `${score * 100}%` }} /></div>
        </div>
        <div className="doc-secondary-meta">
          <span>OCR：{text(doc.ocr_text, '暂无 OCR 文本')}</span>
          <span>视觉描述：{text(doc.visual_caption, '暂无视觉描述')}</span>
        </div>
        <div className="trace-row">
          <span>keyword rank {trace.keyword_rank ?? '—'}</span>
          <span>semantic rank {trace.semantic_rank ?? '—'}</span>
          <span>RRF {numberText(trace.rrf_score, 4, '—')}</span>
        </div>
      </div>
    </article>
  );
}

function AssistantResult({ result }: { result: ChatResult }) {
  const evidence = result.evidence ?? [];
  return (
    <div className="assistant-result">
      <div className="result-summary panel-soft">
        <div>
          <div className="section-title">答案</div>
          <p>{text(result.answer, '暂无回答')}</p>
        </div>
      </div>
      <section className="result-section">
        <h4>引用证据</h4>
        {evidence.length ? <ul>{evidence.map((s, i) => <li key={`${s.id ?? s.source ?? 'source'}-${s.page ?? i}-${i}`}>{text(s.title)} · {text(s.source)} · 第 {s.page ?? '未知'} 页</li>)}</ul> : <p className="muted">暂无引用文档。</p>}
      </section>
      {result.ticket_summary && (
        <section className="result-section">
          <h4>工单摘要</h4>
          <p>{result.ticket_summary}</p>
        </section>
      )}
      {result.diagnosis_result?.summary && (
        <section className="result-section">
          <h4>结构化诊断</h4>
          <p>{result.diagnosis_result.summary}</p>
        </section>
      )}
    </div>
  );
}

function Message({ message, onRetry }: { message: ChatMessage; onRetry: (query: string) => void }) {
  return (
    <div className={`msg-row ${message.role}`}>
      {message.role === 'assistant' && <div className="avatar ai">AI</div>}
      <article className={`msg-card ${message.role}`}>
        <div className="msg-top"><strong>{message.role === 'user' ? 'OP' : 'Wind Ops Agent'}</strong><span>{message.createdAt}</span></div>
        {message.result ? <AssistantResult result={message.result} /> : <p>{message.text}</p>}
        {message.error && <ErrorState message={message.error} onRetry={message.retryQuery ? () => onRetry(message.retryQuery as string) : undefined} />}
      </article>
      {message.role === 'user' && <div className="avatar op">OP</div>}
    </div>
  );
}

function DiagnosisView({ result }: { result: ChatResult | null }) {
  const d = result?.diagnosis_result;
  if (!d) return <EmptyState title="暂无诊断结果" detail="在问答页提交故障问题后，这里会保留并展示结构化诊断。" />;
  return (
    <div className="diagnosis-view">
      <div className="diag-hero panel">
        <div>
          <div className="section-title">当前定位</div>
          <h3>{text(d.component)}</h3>
          <p>{text(d.summary)}</p>
        </div>
        <span className={`risk-pill ${d.risk_level ?? result?.risk_level ?? 'unknown'}`}>风险 {text(d.risk_level ?? result?.risk_level)}</span>
      </div>
      <div className="diag-grid compact-grid">
        <div className="diag-card"><h3>定位部件</h3><p>{text(d.component)}</p><small>{text(d.system)}</small></div>
        <div className="diag-card"><h3>故障域</h3><p>{text(d.fault_domain)}</p><small>报警码：{text(d.alarm_code)}</small></div>
        <div className="diag-card"><h3>工具</h3><p>{(d.tools ?? []).filter(Boolean).join('、') || '暂无'}</p></div>
        <div className="diag-card"><h3>备件</h3><p>{(d.spare_parts ?? []).filter(Boolean).join('、') || '暂无'}</p></div>
      </div>
      <div className="diag-stack">
        <div className="wide-card"><h3>候选原因</h3>{d.candidate_causes?.length ? <ul>{d.candidate_causes.map((c, i) => <li key={`${c.cause ?? 'cause'}-${i}`}>{text(c.cause)} · 置信度 {numberText(c.confidence)} · {text(c.check_method)}</li>)}</ul> : <p>暂无候选原因。</p>}</div>
        <div className="wide-card"><h3>排查步骤</h3>{d.repair_steps?.length ? <ol>{d.repair_steps.map((s, i) => <li key={`${s.step ?? i}-${s.action ?? 'step'}`}>{text(s.action)} · 预期：{text(s.expected_result)} · 风险：{text(s.risk)}</li>)}</ol> : <p>暂无排查步骤。</p>}</div>
      </div>
      <div className="diag-grid">
        <div className="diag-card"><h3>安全警告</h3>{d.safety_warnings?.length ? <ul>{d.safety_warnings.map((w, i) => <li key={`${w}-${i}`}>{w}</li>)}</ul> : <p>暂无安全警告。</p>}</div>
        <div className="diag-card"><h3>下一步</h3><p>{text(d.next_action)}</p></div>
      </div>
      <div className="wide-card"><h3>引用</h3>{d.citations?.length ? <ul>{d.citations.map((c, i) => <li key={`${c.title ?? 'cite'}-${c.page ?? i}-${i}`}>{text(c.title)} · {text(c.source)} · 第 {c.page ?? '未知'} 页 · {numberText(c.score)}</li>)}</ul> : <p>暂无引用。</p>}</div>
    </div>
  );
}

function WorkspaceContext({ page, onStartNew }: { page: PageKey; onStartNew: () => void }) {
  const content: Record<PageKey, { title: string; detail: string }> = {
    chat: { title: '故障问答', detail: '把现场现象转化为清晰的排查路径。' },
    retrieve: { title: '资料检索', detail: '从设备资料中快速定位相关证据。' },
    diagnosis: { title: '故障诊断', detail: '梳理最近一次分析的处理重点。' },
    knowledge: { title: '知识库', detail: '浏览支撑日常运维的现场资料。' },
  };
  const current = content[page];

  return (
    <aside className="workspace-context panel" aria-label="工作辅助">
      <header className="context-header">
        <div><span className="context-kicker">WORKSPACE</span><h2>工作辅助</h2></div>
        <span className="context-status">在线</span>
      </header>
      <section className="context-focus">
        <span>当前任务</span>
        <strong>{current.title}</strong>
        <p>{current.detail}</p>
      </section>
      <section className="context-guide" aria-label="处理要点">
        <div className="context-guide-item"><span>01</span><div><strong>描述现象</strong><p>记录设备、报警码和现场变化。</p></div></div>
        <div className="context-guide-item"><span>02</span><div><strong>确认边界</strong><p>先识别安全风险，再推进排查。</p></div></div>
        <div className="context-guide-item"><span>03</span><div><strong>保留证据</strong><p>将关键结论沉淀到本次会话。</p></div></div>
      </section>
      <button className="context-action" type="button" onClick={onStartNew}>开始新会话</button>
    </aside>
  );
}
export default function App() {
  const [page, setPage] = useState<PageKey>('chat');
  const [metrics, setMetrics] = useState<Metrics>(defaultMetrics);
  const [metricsState, setMetricsState] = useState<LoadState>('idle');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [query, setQuery] = useState('');
  const [chatState, setChatState] = useState<LoadState>('idle');
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: 'hello', role: 'assistant', text: '你好，我是风场诊断助手。告诉我设备、报警码或现场现象，我会帮你梳理排查路径。', createdAt: '刚刚' }]);
  const [lastResult, setLastResult] = useState<ChatResult | null>(null);
  const [retrieveQuery, setRetrieveQuery] = useState('齿轮箱油温高');
  const [topK, setTopK] = useState(5);
  const [retrieveState, setRetrieveState] = useState<LoadState>('idle');
  const [retrieveError, setRetrieveError] = useState('');
  const [retrieveResults, setRetrieveResults] = useState<Source[]>([]);
  const [docsState, setDocsState] = useState<LoadState>('idle');
  const [docsError, setDocsError] = useState('');
  const [docs, setDocs] = useState<Source[]>([]);
  const [docCount, setDocCount] = useState(0);
  const chatRef = useRef<HTMLDivElement>(null);

  const sessionId = metrics.session_id || 'demo-session';

  useEffect(() => {
    setMetricsState('loading');
    requestJson<Metrics>('/metrics')
      .then((data) => {
        setMetrics({ ...defaultMetrics, ...data });
        setMetricsState('success');
      })
      .catch(() => setMetricsState('error'));
    requestJson<{ items?: Conversation[] }>('/conversations')
      .then((data) => setConversations(Array.isArray(data.items) ? data.items : []))
      .catch(() => setConversations([]));
  }, []);

  useEffect(() => { chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' }); }, [messages]);

  useEffect(() => {
    if (page !== 'knowledge' || docsState !== 'idle') return;
    loadDocs();
  }, [page, docsState]);

  const loadDocs = () => {
    setDocsState('loading');
    setDocsError('');
    requestJson<DocsResponse>('/docs')
      .then((data) => {
        const items = Array.isArray(data.items) ? data.items : [];
        setDocs(items);
        setDocCount(typeof data.count === 'number' ? data.count : items.length);
        setDocsState(items.length ? 'success' : 'empty');
      })
      .catch((error: Error) => { setDocsError(error.message); setDocsState('error'); });
  };

  const sendChat = async (forcedQuery?: string) => {
    const payloadQuery = (forcedQuery ?? query).trim();
    if (!payloadQuery || chatState === 'loading') return;
    setChatState('loading');
    setMessages((prev) => [...prev, { id: makeId('user'), role: 'user', text: payloadQuery, createdAt: new Date().toLocaleTimeString() }]);
    if (!forcedQuery) setQuery('');
    try {
      const data = await requestJson<ChatResult>('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, query: payloadQuery }) });
      setLastResult(data);
      setMessages((prev) => [...prev, { id: makeId('assistant'), role: 'assistant', text: data.answer ?? '', result: data, createdAt: new Date().toLocaleTimeString() }]);
      setChatState('success');
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      setQuery(payloadQuery);
      setMessages((prev) => [...prev, { id: makeId('error'), role: 'assistant', text: '请求未完成。', error: message, retryQuery: payloadQuery, createdAt: new Date().toLocaleTimeString() }]);
      setChatState('error');
    }
  };

  const runRetrieve = (event?: FormEvent) => {
    event?.preventDefault();
    if (!retrieveQuery.trim()) return;
    setRetrieveState('loading');
    setRetrieveError('');
    requestJson<RetrieveResponse>('/retrieve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: retrieveQuery.trim(), top_k: topK }) })
      .then((data) => {
        const results = Array.isArray(data.results) ? data.results : [];
        setRetrieveResults(results);
        setRetrieveState(results.length ? 'success' : 'empty');
      })
      .catch((error: Error) => { setRetrieveError(error.message); setRetrieveState('error'); });
  };

  const onChatKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendChat();
    }
  };

  const docStats = useMemo(() => {
    const types = new Set(docs.map((d) => d.doc_type).filter(Boolean));
    const components = new Set(docs.map((d) => d.component).filter(Boolean));
    return { types: Array.from(types), components: Array.from(components) };
  }, [docs]);

  return (
    <div className="wind-shell">
      <aside className="iconbar panel" aria-label="主导航">
        <div className="brand-dot" />
        {navItems.map((item) => <button key={item.key} type="button" className={`icon-item ${page === item.key ? 'active' : ''}`} onClick={() => setPage(item.key)} title={item.label} aria-label={item.label}>{item.icon}</button>)}
      </aside>

      <aside className="session-panel panel">
        <div className="brand-row"><div className="brand-mark">W</div><div><strong>Wind Ops Agent</strong><span>多模态风电运维知识库系统</span></div></div>
        <div className="status-line"><span className={metricsState === 'error' ? 'dot danger' : 'dot'} />{metricsState === 'error' ? '服务暂不可用' : text(metrics.pipeline_status, '系统运行正常')}</div>
        <div className="session-heading"><span>近期会话</span><button type="button" className="new-session" onClick={() => setPage('chat')}>回到问答</button></div>
        <div className="session-list">{conversations.length ? conversations.map((c) => <div key={c.id} className="session-card"><strong>{c.title}</strong><span>{metaText(c.meta)}</span></div>) : <EmptyState title="从一个问题开始" detail="你的近期会话会显示在这里。" />}</div>
      </aside>

      <main className="main-panel">
        <div className="top-status panel"><div className="crumb"><span className="live-dot" />Wind Ops Agent 工作台 <span className="crumb-sep">/</span> {navItems.find((item) => item.key === page)?.label}<span className="top-date">实时同步</span></div></div>
        <section className={`panel page-panel page-${page}`}>
          {page === 'chat' && <>
            <div className="page-head"><div><strong>今天需要解决什么？</strong><span>从报警现象开始，逐步缩小问题范围</span></div></div>
            <div className="chat-layout">
              <div className="chat-column">
                <div className="chat-scroll" ref={chatRef} aria-live="polite">{messages.map((m) => <Message key={m.id} message={m} onRetry={(q) => void sendChat(q)} />)}{chatState === 'loading' && <div className="loading-card loading-answer"><span className="loading-orb" /><div><strong>正在整理现场信息</strong><span>正在匹配相关资料并生成排查建议</span></div></div>}</div>
                <div className="input-row"><textarea value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onChatKeyDown} placeholder="描述设备、报警码和现场现象…" /><button type="button" onClick={() => void sendChat()} disabled={chatState === 'loading' || !query.trim()} aria-label="发送问题">↗</button></div>
              </div>
              <aside className="chat-side">
                <div className="side-card alert-card"><div className="section-title">安全提示</div><strong>{text(lastResult?.risk_level)}</strong><p>{text(lastResult?.safety_notice, '提交问题后显示安全提示。')}</p></div>
                <div className="side-card follow-card"><div className="section-title">建议追问</div>{lastResult?.follow_up_questions?.length ? <div className="follow-list">{lastResult.follow_up_questions.map((q, i) => <button key={`${q}-${i}`} type="button" onClick={() => setQuery(q)}>{q}</button>)}</div> : <p>暂无建议追问。</p>}</div>
                <div className="side-card summary-card"><div className="section-title">工单摘要</div><p>{text(lastResult?.ticket_summary, '提交问题后显示工单摘要。')}</p></div>
              </aside>
            </div>
          </>}

          {page === 'retrieve' && <>
            <div className="page-head"><div><strong>查找现场资料</strong><span>按设备、部件或报警码搜索知识库</span></div></div>
            <form className="search-row" onSubmit={runRetrieve}><input value={retrieveQuery} onChange={(e) => setRetrieveQuery(e.target.value)} placeholder="输入设备、报警码、关键字" /><label>Top K<input type="number" min={1} max={10} value={topK} onChange={(e) => setTopK(Number(e.target.value))} /></label><button type="submit" disabled={retrieveState === 'loading'}>{retrieveState === 'loading' ? '检索中…' : '搜索'}</button></form>
            {retrieveState === 'idle' && <EmptyState title="等待检索" detail="输入查询后将展示标题、类型、来源、页码、分数、OCR/视觉描述和追踪信息。" />}
            {retrieveState === 'loading' && <div className="loading-card">正在搜索资料…</div>}
            {retrieveState === 'error' && <ErrorState message={retrieveError} onRetry={() => runRetrieve()} />}
            {retrieveState === 'empty' && <EmptyState title="没有匹配结果" detail="暂时没有匹配内容，可以调整关键词后重试。" />}
            {retrieveState === 'success' && <div className="doc-list">{retrieveResults.map((doc, i) => <DocCard key={`${doc.id ?? doc.source ?? 'doc'}-${doc.page ?? i}-${i}`} doc={doc} index={i} />)}</div>}
          </>}

          {page === 'diagnosis' && <><div className="page-head"><div><strong>故障诊断</strong><span>最近一次分析的结构化结果</span></div></div><DiagnosisView result={lastResult} /></>}

          {page === 'knowledge' && <>
            <div className="page-head"><div><strong>知识库</strong><span>现场手册、维修记录与部件资料</span></div><button type="button" onClick={loadDocs} disabled={docsState === 'loading'}>刷新</button></div>
            {docsState === 'loading' && <div className="loading-card">正在加载资料…</div>}
            {docsState === 'error' && <ErrorState message={docsError} onRetry={loadDocs} />}
            {(docsState === 'success' || docsState === 'empty') && <>
              <div className="kb-stats-grid">
                <div className="diag-card"><h3>资料总量</h3><p>{docCount}</p><small>当前知识库中的可用文档数量</small></div>
                <div className="diag-card"><h3>文档类型</h3><p>{docStats.types.join('、') || '暂无'}</p><small>手册、流程、案例、图纸等</small></div>
                <div className="diag-card"><h3>覆盖部件</h3><p>{docStats.components.join('、') || '暂无'}</p><small>当前文档覆盖的关键部件</small></div>
                <div className="diag-card"><h3>资料状态</h3><p>{docsState === 'empty' ? '空结果' : '已加载'}</p><small>{docsState === 'empty' ? '暂时没有可展示的资料' : '可直接浏览下方资料卡片'}</small></div>
              </div>
              <div className="kb-summary panel-soft">
                <div>
                  <strong>展示说明</strong>
                  <p>顶部统计用于快速确认知识库规模与覆盖范围，下方仅展示最近的 8 条资料卡片，避免列表过长影响演示。</p>
                </div>
              </div>
              <div className="doc-list compact-docs">{docs.slice(0, 8).map((doc, i) => <DocCard key={`${doc.id ?? doc.source ?? 'kb'}-${doc.page ?? i}-${i}`} doc={doc} index={i} />)}</div>
            </>}
          </>}
        </section>
      </main>

      <WorkspaceContext
        page={page}
        onStartNew={() => {
          setMessages([{ id: 'hello', role: 'assistant', text: '你好，我是风场诊断助手。告诉我设备、报警码或现场现象，我会帮你梳理排查路径。', createdAt: '刚刚' }]);
          setLastResult(null);
          setPage('chat');
        }}
      />
    </div>
  );
}








