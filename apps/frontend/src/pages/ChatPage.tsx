import { useEffect, useRef } from 'react';
import type { KeyboardEvent, RefObject } from 'react';
import type { ChatMessage, ChatResult, LoadState } from '../types';
import { text } from '../format';
import { Message } from '../components/Message';

export function ChatPage({ messages, chatState, query, onQueryChange, onSend, chatRef, lastResult }: {
  messages: ChatMessage[];
  chatState: LoadState;
  query: string;
  onQueryChange: (value: string) => void;
  onSend: (forcedQuery?: string) => void;
  chatRef: RefObject<HTMLDivElement>;
  lastResult: ChatResult | null;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = '50px';
    el.style.height = `${Math.min(el.scrollHeight + 2, 140)}px`;
  }, [query]);

  const onChatKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void onSend();
    }
  };

  return (
    <>
      <div className="page-head"><div><strong>今天需要解决什么？</strong><span>从报警现象开始，逐步缩小问题范围</span></div></div>
      <div className="chat-layout">
        <div className="chat-column">
          <div className="chat-scroll" ref={chatRef} aria-live="polite">{messages.map((m) => <Message key={m.id} message={m} onRetry={(q) => void onSend(q)} />)}{chatState === 'loading' && <div className="loading-card loading-answer"><span className="loading-orb" /><div><strong>正在整理现场信息</strong><span>正在匹配相关资料并生成排查建议</span></div></div>}</div>
          <div className="input-row"><textarea ref={textareaRef} value={query} onChange={(e) => onQueryChange(e.target.value)} onKeyDown={onChatKeyDown} placeholder="描述设备、报警码和现场现象…" /><button type="button" onClick={() => void onSend()} disabled={chatState === 'loading' || !query.trim()} aria-label="发送问题"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M7 17 17 7" /><path d="M9 7h8v8" /></svg></button></div>
        </div>
        <aside className="chat-side">
          <div className="side-card alert-card"><div className="section-title">安全提示</div><strong>{text(lastResult?.risk_level)}</strong><p>{text(lastResult?.safety_notice, '提交问题后显示安全提示。')}</p></div>
          <div className="side-card follow-card"><div className="section-title">建议追问</div>{lastResult?.follow_up_questions?.length ? <div className="follow-list">{lastResult.follow_up_questions.map((q, i) => <button key={`${q}-${i}`} type="button" onClick={() => onQueryChange(q)}>{q}</button>)}</div> : <p>暂无建议追问。</p>}</div>
          <div className="side-card summary-card"><div className="section-title">工单摘要</div><p>{text(lastResult?.ticket_summary, '提交问题后显示工单摘要。')}</p></div>
        </aside>
      </div>
    </>
  );
}
