import type { ChatMessage, ChatResult } from '../types';
import { text } from '../format';
import { ErrorState } from './EmptyState';

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

export function Message({ message, onRetry }: { message: ChatMessage; onRetry: (query: string) => void }) {
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
