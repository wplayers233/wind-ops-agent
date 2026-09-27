import type { Source } from '../types';
import { numberText, normalizeScore, text } from '../format';

export function DocCard({ doc, index }: { doc: Source; index: number }) {
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
