import type { Conversation, LoadState, Metrics } from '../types';
import { metaText, text } from '../format';
import { EmptyState } from './EmptyState';

export function SessionPanel({ metrics, metricsState, conversations, onBackToChat }: {
  metrics: Metrics;
  metricsState: LoadState;
  conversations: Conversation[];
  onBackToChat: () => void;
}) {
  return (
    <aside className="session-panel panel">
      <div className="brand-row"><div className="brand-mark">W</div><div><strong>Wind Ops Agent</strong><span>多模态风电运维知识库系统</span></div></div>
      <div className="status-line"><span className={metricsState === 'error' ? 'dot danger' : 'dot'} />{metricsState === 'error' ? '服务暂不可用' : text(metrics.pipeline_status, '系统运行正常')}</div>
      <div className="session-heading"><span>近期会话</span><button type="button" className="new-session" onClick={onBackToChat}>回到问答</button></div>
      <div className="session-list">{conversations.length ? conversations.map((c) => <div key={c.id} className="session-card"><strong>{c.title}</strong><span>{metaText(c.meta)}</span></div>) : <EmptyState title="从一个问题开始" detail="你的近期会话会显示在这里。" />}</div>
    </aside>
  );
}
