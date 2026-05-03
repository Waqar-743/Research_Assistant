import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search, ChevronDown, User, Database, Cpu, ShieldCheck,
  FileText, Loader2, History, ExternalLink, Download, Plus,
  CheckCircle2, Terminal, AlertCircle, RefreshCw, ArrowUpRight,
  Sparkles, BookOpen, Menu, X, Globe, Zap,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Markdown from 'react-markdown';
import {
  ResearchOptions, LogEntry, AgentStatus, AgentState,
  ResearchHistory, ResearchReport, ReportSource, ReportSection, WSMessage,
} from './types';
import { researchService } from './services/researchService';

/* ─────────────────────────────────────────────────────────────
   Backend → frontend report mapper (unchanged logic)
───────────────────────────────────────────────────────────── */
function mapResultsToReport(res: Record<string, unknown>): ResearchReport | undefined {
  const report = res.report as Record<string, unknown> | undefined;
  if (!report) return undefined;

  const backendSources = (res.sources as Array<Record<string, unknown>>) ?? [];
  const backendFindings = (res.findings as Array<Record<string, unknown>>) ?? [];

  const rawSections = (report.sections as Array<Record<string, unknown>>) ?? [];
  const sections: ReportSection[] = rawSections.map((s) => ({
    heading: (s.title as string) ?? (s.heading as string) ?? '',
    content: (s.content as string) ?? '',
  }));

  const sources: ReportSource[] = backendSources.map((s) => ({
    title: (s.title as string) ?? 'Untitled Source',
    url: (s.url as string) ?? '',
    relevance: s.api_source
      ? `Source: ${s.api_source} · Credibility: ${(((s.credibility_score as number) ?? 0) * 100).toFixed(0)}%`
      : (s.content_preview as string) ?? '',
    domain: (s.domain as string) ?? undefined,
    author: (s.author as string) ?? undefined,
    credibilityScore: (s.credibility_score as number) ?? undefined,
    apiSource: (s.api_source as string) ?? undefined,
  }));

  const findings: string[] = backendFindings.map((f) => {
    const title = (f.title as string) ?? '';
    const content = (f.content as string) ?? '';
    if (title && content && !content.startsWith(title)) return `${title} — ${content}`;
    return content || title || 'Finding';
  });

  const summary = (report.summary as string) ?? '';
  const mdContent = (report.markdown_content as string) ?? '';
  const executiveSummary =
    summary || (mdContent.length > 800 ? mdContent.slice(0, 800) + '…' : mdContent) || '';

  return {
    title: (report.title as string) ?? 'Research Report',
    executiveSummary,
    methodology: undefined,
    tableOfContents: sections.length > 0 ? sections.map((s) => s.heading) : undefined,
    sections,
    sources: sources.length > 0 ? sources : undefined,
    findings: findings.length > 0 ? findings : undefined,
    quality_score: (report.quality_score as number) ?? undefined,
  };
}

/* ─────────────────────────────────────────────────────────────
   Agent name / status maps
───────────────────────────────────────────────────────────── */
const AGENT_NAME_MAP: Record<string, string> = {
  user_proxy: 'User Proxy',
  researcher: 'Researcher',
  analyst: 'Analyst',
  fact_checker: 'Fact Checker',
  report_generator: 'Report Generator',
};

const AGENT_STATUS_MAP: Record<string, AgentStatus> = {
  pending: AgentStatus.PENDING,
  in_progress: AgentStatus.IN_PROGRESS,
  completed: AgentStatus.COMPLETED,
  failed: AgentStatus.FAILED,
};

/* ─────────────────────────────────────────────────────────────
   Scroll-reveal hook
───────────────────────────────────────────────────────────── */
function useScrollReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.reveal');
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('visible'); }),
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  });
}

/* ─────────────────────────────────────────────────────────────
   Shared easing
───────────────────────────────────────────────────────────── */
const SPRING = { type: 'spring', stiffness: 380, damping: 30 } as const;
const EASE_OUT = [0.32, 0.72, 0, 1] as const;

/* ─────────────────────────────────────────────────────────────
   SceneBG — fixed OLED background with gradient orbs
───────────────────────────────────────────────────────── */
const SceneBG = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden bg-[#030305]">
    <div className="absolute -top-[35%] -left-[15%] w-[70%] h-[70%] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(99,66,245,0.13) 0%, transparent 72%)' }} />
    <div className="absolute top-[40%] -right-[20%] w-[60%] h-[60%] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.09) 0%, transparent 72%)' }} />
    <div className="absolute bottom-0 left-[20%] w-[50%] h-[40%] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(16,185,129,0.05) 0%, transparent 72%)' }} />
  </div>
);

/* ─────────────────────────────────────────────────────────────
   Double-Bezel Card
───────────────────────────────────────────────────────── */
const BezelCard = ({ children, className = '', innerClassName = '' }: {
  children: React.ReactNode; className?: string; innerClassName?: string;
}) => (
  <div className={`p-[1.5px] bg-white/[0.04] border border-white/[0.07] rounded-[1.75rem] shadow-[0_24px_64px_rgba(0,0,0,0.55)] ${className}`}>
    <div className={`bg-[#0a0a12] rounded-[calc(1.75rem-1.5px)] shadow-[inset_0_1px_1px_rgba(255,255,255,0.04)] ${innerClassName}`}>
      {children}
    </div>
  </div>
);

/* ─────────────────────────────────────────────────────────────
   Pill CTA Button
───────────────────────────────────────────────────────── */
const PillButton = ({
  children, onClick, disabled = false, variant = 'primary', className = '',
}: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean;
  variant?: 'primary' | 'ghost'; className?: string;
}) => {
  const base = 'group inline-flex items-center gap-3 rounded-full font-semibold text-sm transition-all active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed';
  const variants = {
    primary: 'bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2.5 shadow-[0_0_28px_rgba(99,102,241,0.35)] hover:shadow-[0_0_40px_rgba(99,102,241,0.5)]',
    ghost: 'bg-white/[0.05] hover:bg-white/[0.09] text-white/80 hover:text-white border border-white/[0.09] px-5 py-2.5',
  };
  return (
    <motion.button
      onClick={onClick}
      disabled={disabled}
      whileTap={{ scale: 0.97 }}
      style={{ transitionTimingFunction: `cubic-bezier(${EASE_OUT.join(',')})`, transitionDuration: '400ms' }}
      className={`${base} ${variants[variant]} ${className}`}
    >
      {children}
    </motion.button>
  );
};

/* ─────────────────────────────────────────────────────────────
   Eyebrow Badge
───────────────────────────────────────────────────────── */
const Eyebrow = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-[10px] uppercase tracking-[0.2em] font-semibold text-indigo-300">
    {children}
  </span>
);

/* ─────────────────────────────────────────────────────────────
   Agent icon cell
───────────────────────────────────────────────────────── */
const AGENT_ICONS: Record<string, React.ElementType> = {
  'User Proxy': User,
  'Researcher': Globe,
  'Analyst': Cpu,
  'Fact Checker': ShieldCheck,
  'Report Generator': FileText,
};

const AgentCell = ({ agent, isActive }: { agent: AgentState; isActive: boolean }) => {
  const Icon = AGENT_ICONS[agent.name] || Search;
  const isComplete = agent.status === AgentStatus.COMPLETED;
  const isFailed = agent.status === AgentStatus.FAILED;

  const ringColor = isActive ? 'border-amber-400/50 text-amber-300 bg-amber-400/[0.08]'
    : isComplete ? 'border-emerald-400/40 text-emerald-300 bg-emerald-400/[0.08]'
    : isFailed ? 'border-rose-400/40 text-rose-300 bg-rose-400/[0.08]'
    : 'border-white/[0.08] text-white/25 bg-white/[0.03]';

  return (
    <div className="flex flex-col items-center gap-3 relative z-10 flex-1">
      <div className="relative">
        {isActive && (
          <motion.div
            className="absolute -inset-3 rounded-2xl border border-amber-400/25"
            animate={{ scale: [1, 1.22, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ repeat: Infinity, duration: 2.2, ease: 'easeInOut' }}
          />
        )}
        <motion.div
          animate={isActive ? { scale: [1, 1.06, 1] } : {}}
          transition={isActive ? { repeat: Infinity, duration: 2.4, ease: 'easeInOut' } : {}}
          className={`p-3 rounded-xl border transition-all duration-500 ${ringColor}`}
        >
          <Icon size={22} strokeWidth={1.5} />
        </motion.div>
      </div>

      <div className="text-center">
        <p className="font-semibold text-xs leading-tight text-white/80" style={{ fontFamily: 'var(--font-display)' }}>
          {agent.name}
        </p>
        <p className="text-[9px] text-white/30 uppercase tracking-wider mt-0.5">{agent.description}</p>
        <div className="mt-1.5 flex items-center justify-center gap-1">
          {isActive && (
            <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
              <Loader2 size={10} className="text-amber-400" />
            </motion.div>
          )}
          {isComplete && (
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={SPRING}>
              <CheckCircle2 size={10} className="text-emerald-400" />
            </motion.div>
          )}
          {isFailed && <AlertCircle size={10} className="text-rose-400" />}
          <span className={`text-[9px] font-bold uppercase tracking-wider ${
            isComplete ? 'text-emerald-400' : isActive ? 'text-amber-400' : isFailed ? 'text-rose-400' : 'text-white/20'
          }`}>
            {agent.status}
          </span>
        </div>
      </div>

      {/* Flow dots when complete */}
      {isComplete && (
        <div className="absolute top-[28px] left-[calc(50%+24px)] right-0 h-[2px] pointer-events-none overflow-hidden hidden md:block">
          {[0, 1, 2].map((i) => (
            <motion.div key={i}
              className="absolute top-[-3px] w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]"
              animate={{ left: ['0%', '100%'], opacity: [0, 1, 1, 0] }}
              transition={{ repeat: Infinity, duration: 1.4, delay: i * 0.45, ease: 'linear' }}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Feature card (landing)
───────────────────────────────────────────────────────── */
const FeatureChip = ({ icon: Icon, label }: { icon: React.ElementType; label: string }) => (
  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-white/50 text-xs">
    <Icon size={12} strokeWidth={1.5} />
    <span>{label}</span>
  </div>
);

/* ─────────────────────────────────────────────────────────────
   Main Application
───────────────────────────────────────────────────────── */
export default function App() {
  const [view, setView] = useState<'landing' | 'progress' | 'report' | 'history'>('landing');
  const [history, setHistory] = useState<ResearchHistory[]>([]);
  const [options, setOptions] = useState<ResearchOptions>({
    query: '',
    focusAreas: 'social, environmental, ethical',
    sources: ['Academic', 'News', 'Official', 'Wikipedia'],
    format: 'Markdown',
    citationStyle: 'APA',
    maxSources: 300,
    mode: 'Automatic',
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [agents, setAgents] = useState<AgentState[]>([
    { id: '1', name: 'User Proxy', description: 'Query analysis', status: AgentStatus.PENDING, icon: 'user' },
    { id: '2', name: 'Researcher', description: 'Data collection', status: AgentStatus.PENDING, icon: 'database' },
    { id: '3', name: 'Analyst', description: 'Synthesis & patterns', status: AgentStatus.PENDING, icon: 'cpu' },
    { id: '4', name: 'Fact Checker', description: 'Verification', status: AgentStatus.PENDING, icon: 'shield' },
    { id: '5', name: 'Report Generator', description: 'Report creation', status: AgentStatus.PENDING, icon: 'file' },
  ]);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [reportTab, setReportTab] = useState<'Report' | 'Findings' | 'Sources'>('Report');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useScrollReveal();

  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => { researchService.checkHealth().then(setBackendOnline); }, []);
  useEffect(() => {
    researchService.getHistory().then(({ sessions }) => setHistory(sessions)).catch(() => {});
  }, []);
  useEffect(() => () => {
    wsRef.current?.close();
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  const addLog = useCallback((agent: string, message: string, type: LogEntry['type'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString('en-GB', { hour12: false });
    setLogs((prev) => [...prev, { timestamp, agent, message, type }]);
  }, []);

  const handleWSMessage = useCallback((msg: WSMessage) => {
    switch (msg.type) {
      case 'connection_established':
        addLog('System', 'Connected to research pipeline', 'success');
        break;
      case 'agent_status_update': {
        const displayName = AGENT_NAME_MAP[msg.agent] ?? msg.agent;
        const mappedStatus = AGENT_STATUS_MAP[msg.status] ?? AgentStatus.PENDING;
        setAgents((prev) => prev.map((a) => a.name === displayName ? { ...a, status: mappedStatus } : a));
        const overallPct =
          (msg.data?.overall_progress as number | undefined) ??
          (msg.agent === 'orchestrator' ? msg.progress : undefined);
        if (overallPct !== undefined) setProgress((prev) => Math.max(prev, overallPct));
        if (msg.output) addLog(displayName, msg.output, 'info');
        if (msg.error) addLog(displayName, msg.error, 'error');
        break;
      }
      case 'phase_update':
        addLog('Pipeline', msg.message ?? `Phase: ${msg.phase} → ${msg.status}`, 'info');
        break;
      case 'research_complete':
        addLog('System', 'Research complete — loading report…', 'success');
        setProgress(100);
        if (sessionId) {
          researchService.getResearchResults(sessionId)
            .then((res) => {
              const r = mapResultsToReport(res as Record<string, unknown>);
              if (r) {
                setReport(r);
                setView('report');
                researchService.getHistory().then(({ sessions }) => setHistory(sessions)).catch(() => {});
              }
            })
            .catch((e) => addLog('System', `Error loading results: ${e}`, 'error'));
        }
        break;
      case 'research_error':
        addLog('System', `Error: ${msg.error}`, 'error');
        setError(msg.error);
        break;
    }
  }, [addLog, sessionId]);

  const startResearch = async () => {
    if (!options.query.trim()) return;
    setView('progress');
    setProgress(0);
    setLogs([]);
    setError(null);
    setReport(null);
    setReportTab('Report');
    setAgents((prev) => prev.map((a) => ({ ...a, status: AgentStatus.PENDING })));
    try {
      addLog('System', 'Submitting research request…', 'info');
      const result = await researchService.startResearch(options);
      const sid = result.session_id;
      setSessionId(sid);
      addLog('System', `Session started: ${sid}`, 'success');
      wsRef.current?.close();
      wsRef.current = researchService.connectWebSocket(
        sid, handleWSMessage,
        () => addLog('System', 'WebSocket disconnected', 'warning'),
      );
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const status = await researchService.getResearchStatus(sid);
          setProgress((prev) => Math.max(prev, status.progress));
          if (status.status === 'completed' || status.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
          }
          if (status.status === 'completed' && view !== 'report') {
            const res = await researchService.getResearchResults(sid);
            const r = mapResultsToReport(res as Record<string, unknown>);
            if (r) {
              setReport(r);
              setView('report');
              researchService.getHistory().then(({ sessions }) => setHistory(sessions)).catch(() => {});
            }
          }
        } catch { /* polling errors are non-fatal */ }
      }, 5000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addLog('System', `Failed to start research: ${msg}`, 'error');
      setError(msg);
    }
  };

  const exportMarkdown = () => {
    if (!report) return;
    const md = [
      `# ${report.title}\n`,
      `## Executive Summary\n${report.executiveSummary}\n`,
      report.methodology ? `## Methodology\n${report.methodology}\n` : '',
      ...(report.sections ?? []).map((s) => `## ${s.heading}\n${s.content}\n`),
      report.sources?.length
        ? `## Sources\n${report.sources.map((s) => `- [${s.title}](${s.url}) — ${s.relevance}`).join('\n')}` : '',
    ].join('\n');
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([md], { type: 'text/markdown' })),
      download: `${report.title?.replace(/\s+/g, '_') ?? 'report'}.md`,
    });
    a.click();
  };

  const exportHTML = () => {
    if (!report) return;
    const html = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${report.title}</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:0 auto;padding:2rem;color:#1e293b}h1{color:#4f46e5}a{color:#4f46e5}</style></head><body>
<h1>${report.title}</h1><h2>Executive Summary</h2><p>${report.executiveSummary}</p>
${(report.sections ?? []).map((s) => `<h2>${s.heading}</h2><div>${s.content}</div>`).join('')}
${report.sources?.length ? `<h2>Sources</h2><ul>${report.sources.map((s) => `<li><a href="${s.url}">${s.title}</a></li>`).join('')}</ul>` : ''}
</body></html>`;
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([html], { type: 'text/html' })),
      download: `${report.title?.replace(/\s+/g, '_') ?? 'report'}.html`,
    });
    a.click();
  };

  /* ─────────────────────────────────────────────────────────
     Render
  ───────────────────────────────────────────────────────── */
  return (
    <div className="grain-overlay min-h-[100dvh] text-white" style={{ fontFamily: 'var(--font-sans)' }}>
      <SceneBG />

      {/* ══════════════════════════════════════════════════
          FLOATING NAV ISLAND
      ══════════════════════════════════════════════════ */}
      <div className="fixed top-5 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none">
        <motion.nav
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE_OUT }}
          className="pointer-events-auto flex items-center gap-6 bg-[#0a0a12]/80 backdrop-blur-2xl border border-white/[0.08] rounded-full pl-4 pr-4 py-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
        >
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_12px_rgba(99,102,241,0.5)]">
              <Sparkles size={14} strokeWidth={2} className="text-white" />
            </div>
            <span className="text-sm font-bold tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
              Research<span className="text-indigo-400">AI</span>
            </span>
          </div>

          {/* Divider */}
          <div className="h-4 w-px bg-white/10 hidden sm:block" />

          {/* Nav links — desktop */}
          <div className="hidden sm:flex items-center gap-1">
            {(['Research', 'History'] as const).map((label) => {
              const targetView = label === 'Research' ? 'landing' : 'history';
              const isActive = view === targetView || (label === 'Research' && (view === 'progress' || view === 'report'));
              return (
                <button
                  key={label}
                  onClick={() => {
                    if (label === 'History') {
                      researchService.getHistory().then(({ sessions }) => setHistory(sessions)).catch(() => {});
                    }
                    setView(targetView);
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-300 ${
                    isActive ? 'bg-white/[0.09] text-white' : 'text-white/45 hover:text-white/80'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Status badge */}
          {backendOnline !== null && (
            <div className={`hidden sm:flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[9px] uppercase tracking-[0.15em] font-bold ${
              backendOnline ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-emerald-400' : 'bg-rose-400'}`} />
              {backendOnline ? 'Online' : 'Offline'}
            </div>
          )}

          {/* Mobile hamburger */}
          <button
            className="sm:hidden w-8 h-8 flex items-center justify-center"
            onClick={() => setNavOpen(!navOpen)}
          >
            <motion.div animate={navOpen ? { rotate: 0 } : { rotate: 0 }} className="relative w-4 h-4">
              <motion.span
                animate={navOpen ? { rotate: 45, y: 6 } : { rotate: 0, y: 0 }}
                transition={{ duration: 0.25, ease: EASE_OUT }}
                className="absolute left-0 top-0 w-full h-0.5 bg-white rounded-full block"
              />
              <motion.span
                animate={navOpen ? { opacity: 0 } : { opacity: 1 }}
                transition={{ duration: 0.2 }}
                className="absolute left-0 top-1.5 w-full h-0.5 bg-white rounded-full block"
              />
              <motion.span
                animate={navOpen ? { rotate: -45, y: -6 } : { rotate: 0, y: 0 }}
                transition={{ duration: 0.25, ease: EASE_OUT }}
                className="absolute left-0 top-3 w-full h-0.5 bg-white rounded-full block"
              />
            </motion.div>
          </button>
        </motion.nav>
      </div>

      {/* Mobile nav overlay */}
      <AnimatePresence>
        {navOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 z-40 bg-[#030305]/90 backdrop-blur-3xl flex flex-col items-center justify-center gap-6"
          >
            {(['Research', 'History'] as const).map((label, i) => (
              <motion.button
                key={label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                transition={{ delay: i * 0.08, duration: 0.4, ease: EASE_OUT }}
                onClick={() => {
                  setNavOpen(false);
                  if (label === 'History') {
                    researchService.getHistory().then(({ sessions }) => setHistory(sessions)).catch(() => {});
                    setView('history');
                  } else {
                    setView('landing');
                  }
                }}
                className="text-3xl font-bold text-white/80 hover:text-white transition-colors"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                {label}
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══════════════════════════════════════════════════
          MAIN CONTENT
      ══════════════════════════════════════════════════ */}
      <main className="pt-24 pb-20 px-4 max-w-6xl mx-auto">
        <AnimatePresence mode="wait">

          {/* ────────────────────────────────────────────
              LANDING VIEW
          ──────────────────────────────────────────── */}
          {view === 'landing' && (
            <motion.div
              key="landing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.5, ease: EASE_OUT }}
            >
              {/* Hero */}
              <section className="min-h-[40vh] flex flex-col items-center justify-center text-center py-16 md:py-24 gap-6">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.1, ease: EASE_OUT }}
                >
                  <Eyebrow><Sparkles size={10} strokeWidth={2} /> Multi-Agent AI Research</Eyebrow>
                </motion.div>

                <motion.h1
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.7, delay: 0.2, ease: EASE_OUT }}
                  className="text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight leading-[0.95] max-w-4xl"
                  style={{ fontFamily: 'var(--font-display)' }}
                >
                  Research at the{' '}
                  <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-violet-400 bg-clip-text text-transparent">
                    speed of intelligence
                  </span>
                </motion.h1>

                <motion.p
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.35, ease: EASE_OUT }}
                  className="text-base md:text-lg text-white/45 max-w-xl leading-relaxed"
                >
                  Five specialised AI agents — research, analyse, verify and generate
                  comprehensive reports on any topic in minutes.
                </motion.p>

                {/* Feature chips */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.45, ease: EASE_OUT }}
                  className="flex flex-wrap justify-center gap-2"
                >
                  <FeatureChip icon={Globe} label="Multi-source search" />
                  <FeatureChip icon={ShieldCheck} label="Fact-checked" />
                  <FeatureChip icon={BookOpen} label="APA / MLA citations" />
                  <FeatureChip icon={Zap} label="Real-time updates" />
                </motion.div>
              </section>

              {/* Offline banner */}
              {backendOnline === false && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-6 flex items-center gap-3 px-5 py-3 bg-rose-500/[0.08] border border-rose-500/25 rounded-2xl text-rose-300 text-sm"
                >
                  <AlertCircle size={16} strokeWidth={1.5} />
                  <span>Backend is unreachable. Ensure the server is running on port 8000.</span>
                  <button
                    onClick={() => researchService.checkHealth().then(setBackendOnline)}
                    className="ml-auto p-1 hover:text-white transition-colors"
                  >
                    <RefreshCw size={14} strokeWidth={1.5} />
                  </button>
                </motion.div>
              )}

              {/* Research input — double-bezel card */}
              <motion.div
                initial={{ opacity: 0, y: 32 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.5, ease: EASE_OUT }}
              >
                <BezelCard>
                  <div className="p-6 md:p-8">
                    {/* Textarea */}
                    <div className="relative mb-5">
                      <div className="p-px bg-white/[0.06] rounded-2xl border border-white/[0.06]">
                        <textarea
                          value={options.query}
                          onChange={(e) => setOptions({ ...options, query: e.target.value })}
                          onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) startResearch(); }}
                          placeholder="What are the major challenges of AI safety in 2026?"
                          className="w-full bg-[#07070e] rounded-[calc(1rem-1px)] p-5 pb-16 text-base md:text-lg focus:outline-none transition-all min-h-[160px] resize-none placeholder:text-white/20 text-white/90"
                        />
                      </div>

                      {/* Submit button — pinned bottom-right */}
                      <div className="absolute bottom-4 right-4 flex items-center gap-2">
                        <span className="text-[10px] text-white/20 hidden sm:block">⌘↵ to submit</span>
                        <PillButton
                          onClick={startResearch}
                          disabled={!options.query.trim() || backendOnline === false}
                        >
                          <span>Start Research</span>
                          <span className="w-7 h-7 rounded-full bg-black/20 flex items-center justify-center group-hover:translate-x-0.5 group-hover:-translate-y-px transition-transform duration-400" style={{ transitionTimingFunction: `cubic-bezier(${EASE_OUT.join(',')})` }}>
                            <ArrowUpRight size={14} strokeWidth={2} />
                          </span>
                        </PillButton>
                      </div>
                    </div>

                    {/* Advanced options toggle */}
                    <button
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="flex items-center gap-2 text-xs font-semibold text-white/35 hover:text-white/70 transition-colors mb-4"
                    >
                      <motion.div animate={{ rotate: showAdvanced ? 180 : 0 }} transition={{ duration: 0.3, ease: EASE_OUT }}>
                        <ChevronDown size={14} strokeWidth={1.5} />
                      </motion.div>
                      Advanced Options
                    </button>

                    <AnimatePresence>
                      {showAdvanced && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.4, ease: EASE_OUT }}
                          className="overflow-hidden"
                        >
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                            {/* Left column */}
                            <div className="space-y-4">
                              <div>
                                <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">
                                  Focus Areas
                                </label>
                                <input
                                  type="text"
                                  value={options.focusAreas}
                                  onChange={(e) => setOptions({ ...options, focusAreas: e.target.value })}
                                  className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 focus:outline-none focus:border-indigo-500/40 transition-colors placeholder:text-white/20"
                                />
                              </div>
                              <div className="grid grid-cols-2 gap-3">
                                {[
                                  { label: 'Report Format', key: 'format' as const, opts: ['Markdown', 'PDF', 'HTML'] },
                                  { label: 'Citation Style', key: 'citationStyle' as const, opts: ['APA', 'MLA', 'Chicago', 'Harvard'] },
                                ].map(({ label, key, opts }) => (
                                  <div key={key}>
                                    <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">{label}</label>
                                    <select
                                      value={options[key]}
                                      onChange={(e) => setOptions({ ...options, [key]: e.target.value })}
                                      className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 appearance-none focus:outline-none focus:border-indigo-500/40 transition-colors cursor-pointer"
                                    >
                                      {opts.map((o) => <option key={o} value={o}>{o}</option>)}
                                    </select>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Right column */}
                            <div className="space-y-4">
                              <div>
                                <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">
                                  Source Preferences
                                </label>
                                <div className="bg-[#07070e] border border-white/[0.07] rounded-2xl p-3 flex flex-wrap gap-2">
                                  {options.sources.map((s) => (
                                    <span key={s} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-[10px] font-semibold uppercase tracking-wider">
                                      <span className="w-1 h-1 rounded-full bg-indigo-400" />
                                      {s}
                                    </span>
                                  ))}
                                </div>
                              </div>
                              <div className="grid grid-cols-2 gap-3">
                                <div>
                                  <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">Max Sources</label>
                                  <input
                                    type="number"
                                    value={options.maxSources}
                                    onChange={(e) => setOptions({ ...options, maxSources: parseInt(e.target.value) || 50 })}
                                    className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 focus:outline-none focus:border-indigo-500/40 transition-colors"
                                  />
                                </div>
                                <div>
                                  <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">Mode</label>
                                  <select
                                    value={options.mode}
                                    onChange={(e) => setOptions({ ...options, mode: e.target.value })}
                                    className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 appearance-none focus:outline-none focus:border-indigo-500/40 transition-colors cursor-pointer"
                                  >
                                    {['Automatic', 'Manual', 'Deep Research'].map((o) => <option key={o} value={o}>{o}</option>)}
                                  </select>
                                </div>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </BezelCard>
              </motion.div>

              {/* Agent preview strip */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.7, ease: EASE_OUT }}
                className="mt-8"
              >
                <BezelCard innerClassName="p-5 md:p-6">
                  <p className="text-[10px] uppercase tracking-[0.2em] font-semibold text-white/25 mb-5 text-center">
                    5-Stage Research Pipeline
                  </p>
                  <div className="flex items-start justify-between relative">
                    {/* Track line */}
                    <div className="absolute top-[22px] left-[40px] right-[40px] h-px bg-white/[0.06]" />
                    {[
                      { icon: User, label: 'User Proxy', desc: 'Analysis' },
                      { icon: Globe, label: 'Researcher', desc: 'Collection' },
                      { icon: Cpu, label: 'Analyst', desc: 'Synthesis' },
                      { icon: ShieldCheck, label: 'Fact Checker', desc: 'Verify' },
                      { icon: FileText, label: 'Generator', desc: 'Report' },
                    ].map(({ icon: Icon, label, desc }, i) => (
                      <motion.div
                        key={label}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.8 + i * 0.07, duration: 0.4, ease: EASE_OUT }}
                        className="flex flex-col items-center gap-2 flex-1 relative z-10"
                      >
                        <div className="p-2.5 rounded-xl border border-white/[0.07] bg-[#0d0d18] text-white/30">
                          <Icon size={16} strokeWidth={1.5} />
                        </div>
                        <div className="text-center">
                          <p className="text-[9px] font-semibold text-white/40 leading-tight" style={{ fontFamily: 'var(--font-display)' }}>{label}</p>
                          <p className="text-[8px] text-white/20 mt-0.5">{desc}</p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </BezelCard>
              </motion.div>
            </motion.div>
          )}

          {/* ────────────────────────────────────────────
              PROGRESS VIEW
          ──────────────────────────────────────────── */}
          {view === 'progress' && (
            <motion.div
              key="progress"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5, ease: EASE_OUT }}
              className="space-y-5"
            >
              {/* Error banner */}
              {error && (
                <div className="flex items-center gap-3 px-5 py-3.5 bg-rose-500/[0.08] border border-rose-500/25 rounded-2xl text-rose-300 text-sm">
                  <AlertCircle size={16} strokeWidth={1.5} />
                  <span className="flex-1">{error}</span>
                  <button
                    onClick={() => { setError(null); startResearch(); }}
                    className="flex items-center gap-1.5 text-xs font-semibold hover:text-white transition-colors"
                  >
                    <RefreshCw size={12} strokeWidth={1.5} /> Retry
                  </button>
                </div>
              )}

              {/* Page heading */}
              <div className="flex items-baseline justify-between mb-2">
                <div>
                  <Eyebrow><Loader2 size={10} className="animate-spin" /> Processing</Eyebrow>
                  <h2 className="text-2xl md:text-3xl font-extrabold mt-3 tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
                    Research in Progress
                  </h2>
                  <p className="text-sm text-white/35 mt-1 max-w-md truncate">{options.query}</p>
                </div>
                <span className="text-3xl font-extrabold tabular-nums text-indigo-400" style={{ fontFamily: 'var(--font-display)' }}>
                  {progress}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-violet-500 relative"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.9, ease: EASE_OUT }}
                >
                  <motion.div
                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                    animate={{ x: ['-100%', '200%'] }}
                    transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
                  />
                </motion.div>
              </div>

              {/* Agent pipeline */}
              <BezelCard innerClassName="p-6 md:p-8">
                <div className="flex items-center justify-between mb-8">
                  <h3 className="font-bold text-sm text-white/60" style={{ fontFamily: 'var(--font-display)' }}>
                    Agent Pipeline
                  </h3>
                  <span className="text-[10px] font-mono text-white/25">
                    {agents.filter((a) => a.status === AgentStatus.COMPLETED).length}/{agents.length} complete
                  </span>
                </div>

                {/* Agent row */}
                <div className="flex items-start justify-between relative px-2 md:px-4">
                  {/* Background track */}
                  <div className="absolute top-[26px] left-[52px] right-[52px] h-px bg-white/[0.06]" />
                  {/* Progress fill */}
                  <motion.div
                    className="absolute top-[26px] left-[52px] h-px bg-gradient-to-r from-indigo-500 to-emerald-500"
                    style={{ originX: 0 }}
                    initial={{ width: 0 }}
                    animate={{
                      width: (() => {
                        const completed = agents.filter((a) => a.status === AgentStatus.COMPLETED).length;
                        const inProgress = agents.findIndex((a) => a.status === AgentStatus.IN_PROGRESS);
                        const step = inProgress >= 0 ? inProgress : completed;
                        return `${(step / Math.max(agents.length - 1, 1)) * (100 - 80 / agents.length)}%`;
                      })(),
                    }}
                    transition={{ duration: 0.8, ease: EASE_OUT }}
                  />

                  {agents.map((agent, idx) => (
                    <motion.div
                      key={agent.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.08, duration: 0.45, ease: EASE_OUT }}
                      className="w-1/5"
                    >
                      <AgentCell agent={agent} isActive={agent.status === AgentStatus.IN_PROGRESS} />
                    </motion.div>
                  ))}
                </div>
              </BezelCard>

              {/* Live terminal log */}
              <BezelCard innerClassName="overflow-hidden">
                <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between bg-white/[0.02]">
                  <div className="flex items-center gap-2.5">
                    <Terminal size={14} strokeWidth={1.5} className="text-indigo-400" />
                    <span className="text-xs font-semibold text-white/60" style={{ fontFamily: 'var(--font-display)' }}>Live Activity</span>
                  </div>
                  <button
                    onClick={() => setLogs([])}
                    className="text-[10px] uppercase tracking-widest font-bold px-3 py-1 bg-white/[0.04] hover:bg-white/[0.08] rounded-full transition-colors text-white/30 hover:text-white/60"
                  >
                    Clear
                  </button>
                </div>
                <div className="h-[280px] overflow-y-auto p-5 font-mono text-[11px] space-y-1.5 scrollbar-hide">
                  {logs.length === 0 && (
                    <p className="text-white/20 text-center mt-8">Awaiting pipeline events…</p>
                  )}
                  {logs.map((log, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.25 }}
                      className="flex gap-3"
                    >
                      <span className="text-white/20 shrink-0 tabular-nums">{log.timestamp}</span>
                      <span className={`font-bold shrink-0 w-32 ${
                        log.agent === 'Researcher' ? 'text-emerald-400'
                        : log.agent === 'Analyst' ? 'text-amber-400'
                        : log.agent === 'Fact Checker' ? 'text-blue-400'
                        : log.agent === 'Report Generator' ? 'text-purple-400'
                        : log.agent === 'System' ? 'text-cyan-400'
                        : 'text-white/40'
                      }`}>
                        [{log.agent}]
                      </span>
                      <span className={
                        log.type === 'error' ? 'text-rose-400'
                        : log.type === 'success' ? 'text-emerald-400'
                        : log.type === 'warning' ? 'text-amber-400'
                        : 'text-white/60'
                      }>
                        {log.message}
                      </span>
                    </motion.div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              </BezelCard>
            </motion.div>
          )}

          {/* ────────────────────────────────────────────
              HISTORY VIEW
          ──────────────────────────────────────────── */}
          {view === 'history' && (
            <motion.div
              key="history"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.5, ease: EASE_OUT }}
              className="space-y-6"
            >
              <div className="flex items-end justify-between pt-4 mb-8">
                <div>
                  <Eyebrow><History size={10} /> Sessions</Eyebrow>
                  <h2 className="text-3xl md:text-4xl font-extrabold mt-3 tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
                    Research History
                  </h2>
                </div>
                <PillButton variant="ghost" onClick={() => setView('landing')}>
                  <Plus size={14} strokeWidth={2} />
                  New Research
                </PillButton>
              </div>

              {history.length === 0 ? (
                <BezelCard innerClassName="py-20 text-center">
                  <History size={40} strokeWidth={1} className="mx-auto mb-4 text-white/15" />
                  <p className="text-white/30 text-lg font-medium" style={{ fontFamily: 'var(--font-display)' }}>
                    No research history yet
                  </p>
                  <button
                    onClick={() => setView('landing')}
                    className="mt-4 text-indigo-400 text-sm font-semibold hover:text-indigo-300 transition-colors"
                  >
                    Start your first research →
                  </button>
                </BezelCard>
              ) : (
                <div className="grid gap-3">
                  {history.map((item, i) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05, duration: 0.4, ease: EASE_OUT }}
                    >
                      <div
                        className="p-[1.5px] bg-white/[0.03] border border-white/[0.06] rounded-2xl hover:border-indigo-500/30 transition-all duration-500 cursor-pointer group"
                        onClick={async () => {
                          try {
                            const res = await researchService.getResearchResults(item.id);
                            const r = mapResultsToReport(res as Record<string, unknown>);
                            if (r) { setReport(r); setOptions(item.options); setView('report'); }
                          } catch { /* no results yet */ }
                        }}
                      >
                        <div className="bg-[#0a0a12] rounded-[calc(1rem-1.5px)] px-5 py-4 flex items-center justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-sm text-white/80 group-hover:text-white transition-colors truncate" style={{ fontFamily: 'var(--font-display)' }}>
                              {item.query}
                            </h3>
                            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                              <span className="text-[10px] text-white/25">
                                {new Date(item.timestamp).toLocaleString()}
                              </span>
                              <span className="px-2 py-0.5 bg-white/[0.04] rounded-full text-[9px] uppercase tracking-wider text-white/30 border border-white/[0.06]">
                                {item.options.format}
                              </span>
                              <span className="px-2 py-0.5 bg-white/[0.04] rounded-full text-[9px] uppercase tracking-wider text-white/30 border border-white/[0.06]">
                                {item.options.citationStyle}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <span className={`text-[10px] font-bold uppercase tracking-wider ${
                              item.status === 'completed' ? 'text-emerald-400'
                              : item.status === 'failed' ? 'text-rose-400'
                              : 'text-amber-400'
                            }`}>
                              {item.status}
                            </span>
                            <div className="w-7 h-7 rounded-full bg-white/[0.04] group-hover:bg-indigo-500/15 flex items-center justify-center transition-colors duration-300">
                              <ArrowUpRight size={13} strokeWidth={1.5} className="text-white/30 group-hover:text-indigo-400 transition-colors" />
                            </div>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ────────────────────────────────────────────
              REPORT VIEW
          ──────────────────────────────────────────── */}
          {view === 'report' && report && (
            <motion.div
              key="report"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.55, ease: EASE_OUT }}
              className="space-y-6"
            >
              {/* Report header */}
              <div className="pt-4 pb-2">
                <Eyebrow><CheckCircle2 size={10} /> Report Ready</Eyebrow>
                <h1
                  className="text-2xl md:text-3xl lg:text-4xl font-extrabold mt-3 mb-5 tracking-tight leading-tight max-w-4xl"
                  style={{ fontFamily: 'var(--font-display)' }}
                >
                  {report.title}
                </h1>

                {/* Quality score + actions */}
                <div className="flex flex-wrap items-center gap-3">
                  {report.quality_score != null && (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/[0.08]">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                        Quality {(report.quality_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}

                  <PillButton variant="ghost" onClick={exportMarkdown}>
                    <Download size={13} strokeWidth={1.5} /> Markdown
                  </PillButton>
                  <PillButton variant="ghost" onClick={exportHTML}>
                    <Download size={13} strokeWidth={1.5} /> HTML
                  </PillButton>
                  <PillButton onClick={() => setView('landing')}>
                    <Plus size={13} strokeWidth={2} />
                    New Research
                    <span className="w-6 h-6 rounded-full bg-black/20 flex items-center justify-center group-hover:translate-x-0.5 transition-transform" style={{ transitionTimingFunction: `cubic-bezier(${EASE_OUT.join(',')})`, transitionDuration: '400ms' }}>
                      <ArrowUpRight size={12} strokeWidth={2} />
                    </span>
                  </PillButton>
                </div>
              </div>

              {/* Report content panel */}
              <BezelCard innerClassName="overflow-hidden">
                {/* Tab bar */}
                <div className="px-6 py-0 border-b border-white/[0.06] flex items-center gap-0 bg-white/[0.015]">
                  {(['Report', 'Findings', 'Sources'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setReportTab(tab)}
                      className={`relative px-5 py-4 text-xs font-semibold transition-colors duration-300 ${
                        reportTab === tab ? 'text-white' : 'text-white/35 hover:text-white/60'
                      }`}
                      style={{ fontFamily: 'var(--font-display)' }}
                    >
                      {tab}
                      {tab === 'Sources' && report.sources ? ` (${report.sources.length})` : ''}
                      {tab === 'Findings' && report.findings ? ` (${report.findings.length})` : ''}
                      {reportTab === tab && (
                        <motion.div
                          layoutId="report-tab-indicator"
                          className="absolute bottom-0 left-4 right-4 h-px bg-indigo-400"
                          transition={{ duration: 0.3, ease: EASE_OUT }}
                        />
                      )}
                    </button>
                  ))}
                </div>

                {/* Content area — white panel for readability */}
                <div className="bg-white min-h-[500px]">
                  <div className="p-6 md:p-10 max-w-4xl mx-auto report-prose">

                    {/* ── REPORT TAB ── */}
                    {reportTab === 'Report' && (
                      <>
                        {report.tableOfContents && report.tableOfContents.length > 0 && (
                          <section className="mb-10 p-5 bg-indigo-50 rounded-2xl border border-indigo-100">
                            <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-indigo-500 mb-3">
                              Table of Contents
                            </p>
                            <ul className="space-y-2 list-none p-0 m-0">
                              {report.tableOfContents.map((item, i) => (
                                <li key={i} className="flex items-center gap-2.5 text-sm text-indigo-700 font-medium">
                                  <span className="text-[10px] font-bold text-indigo-300 tabular-nums w-5 shrink-0">{String(i + 1).padStart(2, '0')}</span>
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </section>
                        )}

                        <section className="mb-10">
                          <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 mb-3">Executive Summary</p>
                          <div className="text-base leading-relaxed">
                            <Markdown>{report.executiveSummary}</Markdown>
                          </div>
                        </section>

                        {report.methodology && (
                          <section className="mb-10 p-5 bg-slate-50 rounded-2xl border border-slate-100 italic text-slate-600 text-sm leading-relaxed">
                            <p className="text-[10px] uppercase tracking-[0.2em] font-bold not-italic text-slate-400 mb-3">Methodology</p>
                            <Markdown>{report.methodology}</Markdown>
                          </section>
                        )}

                        {report.sections?.map((section, i) => (
                          <section key={i} className="mb-10">
                            <Markdown>{`## ${section.heading}\n\n${section.content}`}</Markdown>
                          </section>
                        ))}
                      </>
                    )}

                    {/* ── FINDINGS TAB ── */}
                    {reportTab === 'Findings' && (
                      <section>
                        <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 mb-6">
                          Key Findings {report.findings && <span className="text-slate-300">({report.findings.length})</span>}
                        </p>
                        {report.findings && report.findings.length > 0 ? (
                          <ul className="space-y-3">
                            {report.findings.map((f, i) => (
                              <li key={i} className="flex items-start gap-3 p-4 bg-emerald-50 rounded-xl border border-emerald-100">
                                <div className="w-5 h-5 rounded-full bg-emerald-100 flex items-center justify-center shrink-0 mt-0.5">
                                  <CheckCircle2 size={12} className="text-emerald-600" strokeWidth={2} />
                                </div>
                                <span className="text-sm text-slate-700 leading-relaxed">{f}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-400 italic text-sm">No findings recorded for this session.</p>
                        )}
                      </section>
                    )}

                    {/* ── SOURCES TAB ── */}
                    {reportTab === 'Sources' && (
                      <section>
                        <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 mb-6">
                          Sources & References {report.sources && <span className="text-slate-300">({report.sources.length})</span>}
                        </p>
                        {report.sources && report.sources.length > 0 ? (
                          <div className="grid gap-3">
                            {report.sources.map((source, i) => (
                              <div key={i} className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-indigo-200 transition-colors">
                                <div className="flex items-start justify-between gap-4">
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap mb-1">
                                      <h4 className="font-semibold text-sm text-slate-900 leading-tight">
                                        {i + 1}. {source.title}
                                      </h4>
                                      {source.credibilityScore != null && (
                                        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                          source.credibilityScore >= 0.7 ? 'bg-emerald-100 text-emerald-700'
                                          : source.credibilityScore >= 0.4 ? 'bg-amber-100 text-amber-700'
                                          : 'bg-rose-100 text-rose-700'
                                        }`}>
                                          {(source.credibilityScore * 100).toFixed(0)}% credible
                                        </span>
                                      )}
                                      {source.apiSource && (
                                        <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                                          {source.apiSource}
                                        </span>
                                      )}
                                    </div>
                                    {source.author && (
                                      <p className="text-xs text-slate-500 mb-1">By {source.author}</p>
                                    )}
                                    {source.url && (
                                      <a href={source.url} target="_blank" rel="noreferrer"
                                        className="text-xs text-indigo-600 hover:text-indigo-800 hover:underline break-all flex items-center gap-1">
                                        <ExternalLink size={11} strokeWidth={1.5} className="shrink-0" />
                                        {source.url}
                                      </a>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-slate-400 italic text-sm">No sources recorded for this session.</p>
                        )}
                      </section>
                    )}

                  </div>
                </div>
              </BezelCard>
            </motion.div>
          )}

        </AnimatePresence>
      </main>

      {/* ══════════════════════════════════════════════════
          FOOTER
      ══════════════════════════════════════════════════ */}
      <footer className="py-10 text-center">
        <p className="text-[10px] uppercase tracking-[0.2em] font-semibold text-white/15">
          &copy; {new Date().getFullYear()} Research Assistant — Multi-Agent AI
        </p>
      </footer>
    </div>
  );
}
