/** Headless engine client. The eventual interface owns layout and interaction. */
export type JobState = 'queued' | 'running' | 'completed' | 'paused' | 'failed' |
  'cancelled' | 'interrupted' | 'needs_recompile';
export interface Snapshot {
  qubits: number;
  branches: [string, [number, number]][];
  norm_squared?: number;
}
export interface StepReceipt {
  index: number; operator: string; glyph: string;
  parameters: Record<string, unknown>;
  compiled_from?: { source_index: number; definitions: Record<string, unknown>[] };
  result: Record<string, unknown>;
  event_id: string;
}
export interface Job {
  id: string; request_id: string; state: JobState;
  source_sha256: string; engine_sha256: string;
  error: string | null; cancel_requested: boolean;
  result: null | { world_id: string; closed: boolean; completed_steps: number; steps: StepReceipt[];
    integrity: { ok: boolean } };
}
export interface EventPage {
  events: { sequence: number; job_id: string; at: string; kind: string; data: Record<string, unknown> }[];
  next_cursor: number;
}
export class LivingCircuitClient {
  constructor(readonly baseUrl: string, private readonly token: string) {}
  async request<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(this.baseUrl.replace(/\/$/, '') + path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${this.token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error ?? `HTTP ${response.status}`);
    return value as T;
  }
  capabilities() { return this.request<Record<string, unknown>>('/capabilities'); }
  examples() { return this.request<{ examples: string[] }>('/examples'); }
  example(name: string) { return this.request<{ source: string }>('/examples/' + encodeURIComponent(name)); }
  compile(source: string) { return this.request<Record<string, unknown>>('/compile', { source }); }
  submit(source: string, requestId: string) { return this.request<Job>('/jobs', { source, request_id: requestId }); }
  job(id: string) { return this.request<Job>('/jobs/' + encodeURIComponent(id)); }
  events(id: string, after = 0) { return this.request<EventPage>(`/jobs/${encodeURIComponent(id)}/events?after=${after}`); }
  cancel(id: string) { return this.request<Job>(`/jobs/${encodeURIComponent(id)}/cancel`, {}); }
  resume(id: string) { return this.request<Job>(`/jobs/${encodeURIComponent(id)}/resume`, {}); }
}
