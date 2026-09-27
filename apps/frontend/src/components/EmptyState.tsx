export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><strong>{title}</strong><span>{detail}</span></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-state"><strong>请求失败</strong><span>{message}</span>{onRetry && <button type="button" onClick={onRetry}>重试</button>}</div>;
}
