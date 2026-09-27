import type { PageKey } from '../types';

export const navItems: { key: PageKey; icon: string; label: string }[] = [
  { key: 'chat', icon: '✦', label: '问答' },
  { key: 'retrieve', icon: '⌕', label: '检索' },
  { key: 'diagnosis', icon: '◈', label: '诊断' },
  { key: 'knowledge', icon: '▤', label: '知识库' },
];

export function IconBar({ page, onSelect }: { page: PageKey; onSelect: (key: PageKey) => void }) {
  return (
    <aside className="iconbar panel" aria-label="主导航">
      <div className="brand-dot" />
      {navItems.map((item) => <button key={item.key} type="button" className={`icon-item ${page === item.key ? 'active' : ''}`} onClick={() => onSelect(item.key)} title={item.label} aria-label={item.label}>{item.icon}</button>)}
    </aside>
  );
}
