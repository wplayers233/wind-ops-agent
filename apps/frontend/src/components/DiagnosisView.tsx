import type { ChatResult } from '../types';
import { numberText, text } from '../format';
import { EmptyState } from './EmptyState';

export function DiagnosisView({ result }: { result: ChatResult | null }) {
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
