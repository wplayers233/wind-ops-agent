import type { LoadState, Source } from '../types';
import { ErrorState } from '../components/EmptyState';
import { DocCard } from '../components/DocCard';

export function KnowledgePage({ docs, docCount, docStats, state, error, onRefresh }: {
  docs: Source[];
  docCount: number;
  docStats: { types: string[]; components: string[] };
  state: LoadState;
  error: string;
  onRefresh: () => void;
}) {
  return (
    <>
      <div className="page-head"><div><strong>知识库</strong><span>现场手册、维修记录与部件资料</span></div><button type="button" onClick={onRefresh} disabled={state === 'loading'}>刷新</button></div>
      {state === 'loading' && <div className="loading-card">正在加载资料…</div>}
      {state === 'error' && <ErrorState message={error} onRetry={onRefresh} />}
      {(state === 'success' || state === 'empty') && <>
        <div className="kb-stats-grid">
          <div className="diag-card"><h3>资料总量</h3><p>{docCount}</p><small>当前知识库中的可用文档数量</small></div>
          <div className="diag-card"><h3>文档类型</h3><p>{docStats.types.join('、') || '暂无'}</p><small>手册、流程、案例、图纸等</small></div>
          <div className="diag-card"><h3>覆盖部件</h3><p>{docStats.components.join('、') || '暂无'}</p><small>当前文档覆盖的关键部件</small></div>
          <div className="diag-card"><h3>资料状态</h3><p>{state === 'empty' ? '空结果' : '已加载'}</p><small>{state === 'empty' ? '暂时没有可展示的资料' : '可直接浏览下方资料卡片'}</small></div>
        </div>
        <div className="kb-summary panel-soft">
          <div>
            <strong>展示说明</strong>
            <p>顶部统计用于快速确认知识库规模与覆盖范围，下方仅展示最近的 8 条资料卡片，避免列表过长影响演示。</p>
          </div>
        </div>
        <div className="doc-list compact-docs">{docs.slice(0, 8).map((doc, i) => <DocCard key={`${doc.id ?? doc.source ?? 'kb'}-${doc.page ?? i}-${i}`} doc={doc} index={i} />)}</div>
      </>}
    </>
  );
}
