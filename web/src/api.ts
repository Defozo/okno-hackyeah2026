import type { paths } from './api.generated';

export interface InputIssue { path: string; message: string }
export class ApiValidationError extends Error {
  issues: InputIssue[];
  constructor(issues: InputIssue[]) {
    super('Niektóre dane wymagają poprawy. Sprawdź wskazane pola i ponów analizę.');
    this.name = 'ApiValidationError';
    this.issues = issues;
  }
}
function validationIssue(item: { loc?: Array<string | number>; type?: string }): InputIssue {
  const parts = [...(item.loc || [])];
  while (['body', 'query', 'path', 'scenario'].includes(String(parts[0]))) parts.shift();
  if (typeof parts.at(-1) === 'number' && ['dates', 'excluded_dates'].includes(String(parts.at(-2)))) parts.pop();
  if (parts.join('.') === 'minimum_paid_minutes') return { path: 'minimum_paid_minutes', message: 'Podaj poprawny wymagany czas pracy: co najmniej 0 godzin.' };
  const isDate = item.type?.includes('date') || parts.some(part => ['dates', 'excluded_dates', 'start_date', 'end_date', 'valid_from', 'valid_to', 'checked_at', 'confirmation_valid_to'].includes(String(part)));
  return { path: parts.join('.'), message: isDate ? 'Wpisz istniejącą datę w formacie RRRR-MM-DD, np. 2026-10-10.' : item.type === 'missing' ? 'Uzupełnij wymagane pole.' : 'Sprawdź wartość tego pola. Nie spełnia wymaganych warunków.' };
}

type PostPath = { [P in keyof paths]: paths[P] extends { post: unknown } ? P : never }[keyof paths];
type RequestBody<P extends PostPath> = paths[P]['post'] extends { requestBody: { content: { 'application/json': infer Body } } } ? Body : never;

/** Request paths and payloads are checked against the generated OpenAPI contract. */
export function apiPost<P extends PostPath, T = any>(path: P, body: RequestBody<P>, options: RequestInit = {}): Promise<T> {
  return api<T>(path, body, { ...options, method: 'POST' });
}

let csrf = '';
export function setCsrf(value: string) { csrf = value; }
export async function api<T = any>(path: string, body?: unknown, options: RequestInit = {}): Promise<T> {
  const method = options.method || (body === undefined ? 'GET' : 'POST');
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', ...options, method, headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(method === 'GET' ? {} : { 'X-CSRF-Token': csrf, 'Idempotency-Key': crypto.randomUUID() }), ...options.headers }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (Array.isArray(data.detail)) throw new ApiValidationError(data.detail.map(validationIssue));
    const detail = typeof data.detail === 'string' ? data.detail : data.detail?.message || data.message;
    throw new Error(response.status === 409 ? 'Plan zmienił się od ostatniego odczytu. Otwórz jego aktualną wersję i ponów zmianę.' : detail || (response.status === 503 ? 'Analiza jest chwilowo niedostępna. Twoje dane pozostają w formularzu. Spróbuj ponownie.' : `Nie udało się wykonać działania (${response.status}). Dane pozostają w formularzu.`));
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) return response.json();
  return response.blob() as Promise<T>;
}
export function download(data: Blob | object | string, name: string, type = 'application/json') {
  const blob = data instanceof Blob ? data : new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], { type });
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 5000);
}
