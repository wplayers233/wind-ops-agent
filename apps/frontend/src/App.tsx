import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';

import { requestJson } from './api';
import type { ChatMessage, ChatResult, Conversation, DocsResponse, LoadState, Metrics, PageKey, RetrieveResponse, Source } from './types';
import { makeId } from './format';
import { IconBar, navItems } from './components/IconBar';
import { SessionPanel } from './components/SessionPanel';
import { WorkspaceContext } from './components/WorkspaceContext';
import { DiagnosisView } from './components/DiagnosisView';
import { ChatPage } from './pages/ChatPage';
import { RetrievePage } from './pages/RetrievePage';
import { KnowledgePage } from './pages/KnowledgePage';

const defaultMetrics: Metrics = { pipeline_status: '系统运行正常', session_id: 'demo-session' };

const initialGreeting: ChatMessage = { id: 'hello', role: 'assistant', text: '你好，我是风场诊断助手。告诉我设备、报警码或现场现象，我会帮你梳理排查路径。', createdAt: '刚刚' };

export default function App() {
  const [page, setPage] = useState<PageKey>('chat');
  const [metrics, setMetrics] = useState<Metrics>(defaultMetrics);
  const [metricsState, setMetricsState] = useState<LoadState>('idle');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [query, setQuery] = useState('');
  const [chatState, setChatState] = useState<LoadState>('idle');
  const [messages, setMessages] = useState<ChatMessage[]>([initialGreeting]);
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

  const docStats = useMemo(() => {
    const types = new Set(docs.map((d) => d.doc_type).filter((t): t is string => Boolean(t)));
    const components = new Set(docs.map((d) => d.component).filter((c): c is string => Boolean(c)));
    return { types: Array.from(types), components: Array.from(components) };
  }, [docs]);

  return (
    <div className="wind-shell">
      <IconBar page={page} onSelect={setPage} />

      <SessionPanel metrics={metrics} metricsState={metricsState} conversations={conversations} onBackToChat={() => setPage('chat')} />

      <main className="main-panel">
        <div className="top-status panel"><div className="crumb"><span className="live-dot" />Wind Ops Agent 工作台 <span className="crumb-sep">/</span> {navItems.find((item) => item.key === page)?.label}<span className="top-date">实时同步</span></div></div>
        <section className={`panel page-panel page-${page}`}>
          {page === 'chat' && <ChatPage messages={messages} chatState={chatState} query={query} onQueryChange={setQuery} onSend={sendChat} chatRef={chatRef} lastResult={lastResult} />}

          {page === 'retrieve' && <RetrievePage query={retrieveQuery} onQueryChange={setRetrieveQuery} topK={topK} onTopKChange={setTopK} state={retrieveState} error={retrieveError} results={retrieveResults} onSearch={runRetrieve} />}

          {page === 'diagnosis' && <><div className="page-head"><div><strong>故障诊断</strong><span>最近一次分析的结构化结果</span></div></div><DiagnosisView result={lastResult} /></>}

          {page === 'knowledge' && <KnowledgePage docs={docs} docCount={docCount} docStats={docStats} state={docsState} error={docsError} onRefresh={loadDocs} />}
        </section>
      </main>

      <WorkspaceContext
        page={page}
        onStartNew={() => {
          setMessages([initialGreeting]);
          setLastResult(null);
          setPage('chat');
        }}
      />
    </div>
  );
}
