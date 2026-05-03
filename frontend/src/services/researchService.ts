/* ------------------------------------------------------------------ */
/*  Research Service — communicates with FastAPI backend                */
/*  REST  endpoints : /api/v1/research, /api/v1/history, /api/v1/health*/
/*  WebSocket       : /ws/{session_id}                                 */
/* ------------------------------------------------------------------ */

import {
  ResearchOptions,
  ResearchReport,
  ResearchHistory,
  WSMessage,
} from '../types';

const envApiUrl = import.meta.env.VITE_API_URL?.trim();
const envWsUrl = import.meta.env.VITE_WS_URL?.trim();

function stripTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, '');
}

const API_ORIGIN = envApiUrl ? stripTrailingSlashes(envApiUrl) : '';
const API_BASE = API_ORIGIN ? `${API_ORIGIN}/api/v1` : '/api/v1';

function resolveWebSocketBase(): string {
  if (envWsUrl) {
    return stripTrailingSlashes(envWsUrl);
  }

  if (API_ORIGIN) {
    return API_ORIGIN.replace(/^http/i, 'ws');
  }

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}`;
}

/* ---------- helpers ---------- */

async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body}`);
  }
  const json = await res.json();
  return json.data ?? json;
}

/* ---------- Health ---------- */

export async function checkHealth(): Promise<boolean> {
  try {
    await apiFetch('/health/live');
    return true;
  } catch {
    return false;
  }
}

/* ---------- Start research ---------- */

export interface StartResearchResult {
  session_id: string;
  status: string;
  query: string;
  websocket_url: string;
}

export async function startResearch(
  opts: ResearchOptions,
): Promise<StartResearchResult> {
  return apiFetch<StartResearchResult>('/research/start', {
    method: 'POST',
    body: JSON.stringify({
      query: opts.query,
      focus_areas: opts.focusAreas
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      source_preferences: opts.sources.map((s) => s.toLowerCase()),
      max_sources: opts.maxSources,
      report_format: opts.format.toLowerCase(),
      citation_style: opts.citationStyle,
      research_mode: 'auto',
    }),
  });
}

/* ---------- Poll status ---------- */

export interface ResearchStatus {
  research_id: string;
  query: string;
  status: string;
  current_stage: string | null;
  progress: number;
  agents: Record<string, unknown>;
  sources_found: Record<string, number>;
  error: string | null;
}

export async function getResearchStatus(
  sessionId: string,
): Promise<ResearchStatus> {
  return apiFetch<ResearchStatus>(`/research/${sessionId}`);
}

/* ---------- Get results ---------- */

export async function getResearchResults(
  sessionId: string,
): Promise<{ report: ResearchReport; sources: unknown[]; findings: unknown[] }> {
  return apiFetch(`/research/${sessionId}/results`);
}

/* ---------- History ---------- */

export async function getHistory(
  page = 1,
  limit = 20,
): Promise<{ sessions: ResearchHistory[]; total: number }> {
  const data = await apiFetch<{
    sessions: Array<Record<string, unknown>>;
    total: number;
    pagination: unknown;
  }>(`/history/?page=${page}&limit=${limit}`);

  const sessions: ResearchHistory[] = (data.sessions ?? []).map((s) => ({
    id: (s.session_id as string) ?? '',
    query: (s.query as string) ?? '',
    timestamp: (s.created_at as string) ?? '',
    report: null,
    options: {
      query: (s.query as string) ?? '',
      focusAreas: '',
      sources: [],
      format: (s.report_format as string) ?? 'markdown',
      citationStyle: (s.citation_style as string) ?? 'APA',
      maxSources: 300,
      mode: 'Automatic',
    },
    status: (s.status as string) ?? 'unknown',
  }));

  return { sessions, total: data.total ?? 0 };
}

/* ---------- WebSocket ---------- */

export function connectWebSocket(
  sessionId: string,
  onMessage: (msg: WSMessage) => void,
  onClose?: () => void,
): WebSocket {
  const wsBase = resolveWebSocketBase();
  const ws = new WebSocket(`${wsBase}/ws/${sessionId}`);

  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      // Respond to server heartbeat pings to keep the connection alive
      if (data.type === 'ping') {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'pong' }));
        }
        return;
      }
      onMessage(data as WSMessage);
    } catch {
      /* ignore non-JSON frames */
    }
  };

  ws.onclose = () => onClose?.();
  ws.onerror = () => ws.close();

  return ws;
}

/* ---------- Singleton-style wrapper (keeps the import simple) ---------- */

export const researchService = {
  checkHealth,
  startResearch,
  getResearchStatus,
  getResearchResults,
  getHistory,
  connectWebSocket,
};
