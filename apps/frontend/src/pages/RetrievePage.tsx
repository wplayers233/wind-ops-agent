import type { FormEvent } from 'react';
import type { LoadState, Source } from '../types';
import { EmptyState, ErrorState } from '../components/EmptyState';
import { DocCard } from '../components/DocCard';

export function RetrievePage({ query, onQueryChange, topK, onTopKChange, state, error, results, onSearch }: {
  query: string;
  onQueryChange: (value: string) => void;
  topK: number;
  onTopKChange: (value: number) => void;
  state: LoadState;
  error: string;
  results: Source[];
  onSearch: (event?: FormEvent) => void;
}) {
  return (
    <>
      <div className="page-head"><div><strong>查找现场资料</strong><span>按设备、部件或报警码搜索知识库</span></div></div>
      <form className="search-row" onSubmit={onSearch}><input value={query} onChange={(e) => onQueryChange(e.target.value)} placeholder="输入设备、报警码、关键字" /><label>Top K<input type="number" min={1} max={10} value={topK} onChange={(e) => onTopKChange(Number(e.target.value))} /></label><button type="submit" disabled={state === 'loading'}>{state === 'loading' ? '检索中…' : '搜索'}</button></form>
      {state === 'idle' && <EmptyState title="等待检索" detail="输入查询后将展示标题、类型、来源、页码、分数、OCR/视觉描述和追踪信息。" />}
      {state === 'loading' && <div className="loading-card">正在搜索资料…</div>}
      {state === 'error' && <ErrorState message={error} onRetry={() => onSearch()} />}
      {state === 'empty' && <EmptyState title="没有匹配结果" detail="暂时没有匹配内容，可以调整关键词后重试。" />}
      {state === 'success' && <div className="doc-list">{results.map((doc, i) => <DocCard key={`${doc.id ?? doc.source ?? 'doc'}-${doc.page ?? i}-${i}`} doc={doc} index={i} />)}</div>}
    </>
  );
}
