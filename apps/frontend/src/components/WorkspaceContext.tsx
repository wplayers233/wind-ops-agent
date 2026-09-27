import type { PageKey } from '../types';

export function WorkspaceContext({ page, onStartNew }: { page: PageKey; onStartNew: () => void }) {
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
