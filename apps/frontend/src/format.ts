import type { Conversation } from './types';

export function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function text(value: unknown, fallback = '未返回') {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

export function metaText(value: Conversation['meta']) {
  if (typeof value === 'string') return value;
  return text(value?.label, '暂无元信息');
}

export function numberText(value: unknown, digits = 2, fallback = '未返回') {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : fallback;
}

export function normalizeScore(score: unknown) {
  if (typeof score !== 'number' || !Number.isFinite(score)) return 0;
  return Math.max(0, Math.min(1, score > 1 ? score / 100 : score));
}
