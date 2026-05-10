import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search, ChevronDown, User, Database, Cpu, ShieldCheck,
  FileText, Loader2, History, ExternalLink, Download, Plus,
  CheckCircle2, Terminal, AlertCircle, RefreshCw, ArrowUpRight,
  Sparkles, BookOpen, Globe, Zap, Info, Printer,
  BarChart2, Clock, Target, Menu, X,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Markdown from 'react-markdown';
import {
  ResearchOptions, LogEntry, AgentStatus, AgentState,
  ResearchHistory, ResearchReport, ReportSource, ReportSection, WSMessage,
} from './types';
import { researchService } from './services/researchService';

/* ─────────────────────────────────────────────────────────────
   Backend → frontend report mapper
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
   Agent maps
───────────────────────────────────────────────────────── */
const AGENT_NAME_MAP: Record<string, string> = {
  user_proxy: 'User Proxy', researcher: 'Researcher',
  analyst: 'Analyst', fact_checker: 'Fact Checker', report_generator: 'Report Generator',
};
const AGENT_STATUS_MAP: Record<string, AgentStatus> = {
  pending: AgentStatus.PENDING, in_progress: AgentStatus.IN_PROGRESS,
  completed: AgentStatus.COMPLETED, failed: AgentStatus.FAILED,
};

/* ─────────────────────────────────────────────────────────────
   Scroll-reveal — runs once on mount only
───────────────────────────────────────────────────────── */
function useScrollReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.reveal');
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('visible'); }),
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

const SPRING = { type: 'spring', stiffness: 380, damping: 30 } as const;
const EASE_OUT = [0.32, 0.72, 0, 1] as const;

/* ─────────────────────────────────────────────────────────────
   Scene Background
───────────────────────────────────────────────────────── */
const SceneBG = () => (
  <div className="fixed inset-0 overflow-hidden pointer-events-none" style={{ zIndex: 0 }}>
    <div className="absolute inset-0 bg-[#030305]" />
    <div className="absolute -top-[35%] -left-[15%] w-[75%] h-[75%] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(20,184,166,0.18) 0%, transparent 70%)' }} />
    <div className="absolute top-[30%] -right-[20%] w-[65%] h-[65%] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(13,148,136,0.12) 0%, transparent 70%)' }} />
    <div className="absolute bottom-[-10%] left-[15%] w-[55%] h-[45%] rounded-full"
      style={{ background: 'radial-gradient(circle, rgba(16,185,129,0.07) 0%, transparent 70%)' }} />
    <div className="absolute inset-0 opacity-[0.025]"
      style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />
  </div>
);

/* ─────────────────────────────────────────────────────────────
   Shared UI components
───────────────────────────────────────────────────────── */
const BezelCard = ({ children, className = '', innerClassName = '' }: {
  children: React.ReactNode; className?: string; innerClassName?: string;
}) => (
  <div className={`p-[1px] rounded-[1.75rem] shadow-[0_32px_80px_rgba(0,0,0,0.7),0_0_0_1px_rgba(255,255,255,0.06)] ${className}`}
    style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 50%, rgba(255,255,255,0.06) 100%)' }}>
    <div className={`bg-[#0b0b14] rounded-[calc(1.75rem-1px)] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ${innerClassName}`}>
      {children}
    </div>
  </div>
);

const PillButton = ({
  children, onClick, disabled = false, variant = 'primary', className = '',
}: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean;
  variant?: 'primary' | 'ghost'; className?: string;
}) => {
  const base = 'group inline-flex items-center gap-2.5 rounded-full font-semibold text-sm transition-all active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed';
  const variants = { primary: 'text-white px-6 py-2.5', ghost: 'text-white/70 hover:text-white px-5 py-2.5' };
  const variantStyles = {
    primary: { background: 'linear-gradient(135deg, #14b8a6 0%, #0f766e 100%)', boxShadow: '0 0 32px rgba(20,184,166,0.4), inset 0 1px 0 rgba(255,255,255,0.15)' },
    ghost: { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' },
  };
  return (
    <motion.button onClick={onClick} disabled={disabled} whileTap={{ scale: 0.97 }}
      style={{ ...variantStyles[variant] }} className={`${base} ${variants[variant]} ${className}`}>
      {children}
    </motion.button>
  );
};

const Eyebrow = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[10px] uppercase tracking-[0.22em] font-bold text-teal-200"
    style={{ background: 'linear-gradient(135deg, rgba(20,184,166,0.2) 0%, rgba(13,148,136,0.15) 100%)', border: '1px solid rgba(13,148,136,0.35)', boxShadow: '0 0 20px rgba(20,184,166,0.15)' }}>
    {children}
  </span>
);

const FeatureChip = ({ icon: Icon, label }: { icon: React.ElementType; label: string }) => (
  <div className="flex items-center gap-2 px-4 py-2 rounded-full text-white/60 text-xs font-medium"
    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(8px)' }}>
    <Icon size={12} strokeWidth={1.5} className="text-teal-400" />
    <span>{label}</span>
  </div>
);

/* ─────────────────────────────────────────────────────────────
   Agent Cell (progress pipeline)
───────────────────────────────────────────────────────── */
const AGENT_ICONS: Record<string, React.ElementType> = {
  'User Proxy': User, 'Researcher': Globe, 'Analyst': Cpu,
  'Fact Checker': ShieldCheck, 'Report Generator': FileText,
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
    <div className="flex flex-col items-center gap-2.5 relative z-10 flex-1">
      <div className="relative">
        {isActive && (
          <motion.div className="absolute -inset-3 rounded-2xl border border-amber-400/25"
            animate={{ scale: [1, 1.22, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ repeat: Infinity, duration: 2.2, ease: 'easeInOut' }} />
        )}
        <motion.div
          animate={isActive ? { scale: [1, 1.06, 1] } : {}}
          transition={isActive ? { repeat: Infinity, duration: 2.4, ease: 'easeInOut' } : {}}
          className={`p-3 rounded-xl border transition-all duration-500 ${ringColor}`}
        >
          <Icon size={20} strokeWidth={1.5} />
        </motion.div>
      </div>
      <div className="text-center">
        <p className="font-semibold text-[11px] leading-tight text-white/80" style={{ fontFamily: 'var(--font-display)' }}>{agent.name}</p>
        <p className="text-[9px] text-white/30 uppercase tracking-wider mt-0.5">{agent.description}</p>
        <div className="mt-1.5 flex items-center justify-center gap-1">
          {isActive && <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}><Loader2 size={10} className="text-amber-400" /></motion.div>}
          {isComplete && <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={SPRING}><CheckCircle2 size={10} className="text-emerald-400" /></motion.div>}
          {isFailed && <AlertCircle size={10} className="text-rose-400" />}
          <span className={`text-[9px] font-bold uppercase tracking-wider ${isComplete ? 'text-emerald-400' : isActive ? 'text-amber-400' : isFailed ? 'text-rose-400' : 'text-white/20'}`}>
            {agent.status}
          </span>
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   About Page
───────────────────────────────────────────────────────── */
const AboutPage = ({ onStart }: { onStart: () => void }) => {
  const agents = [
    { icon: User, name: 'User Proxy', color: 'indigo', desc: 'Parses and validates your research query, breaks it into sub-questions, and coordinates the overall pipeline.' },
    { icon: Globe, name: 'Researcher', color: 'sky', desc: 'Queries multiple sources in parallel — academic APIs, news feeds, Wikipedia, and the open web via SerpAPI.' },
    { icon: Cpu, name: 'Analyst', color: 'amber', desc: 'Synthesises raw data into coherent patterns, cross-references findings, and identifies knowledge gaps.' },
    { icon: ShieldCheck, name: 'Fact Checker', color: 'emerald', desc: 'Scores each claim for credibility using source authority, corroboration, and recency signals.' },
    { icon: FileText, name: 'Report Generator', color: 'purple', desc: 'Assembles the final structured report with executive summary, sections, citations, and key findings.' },
  ];
  const features = [
    { icon: Globe, title: 'Multi-source Search', desc: 'ArXiv, PubMed, Wikipedia, NewsAPI, SerpAPI queried simultaneously.' },
    { icon: ShieldCheck, title: 'Fact Checking', desc: 'Every claim scored for credibility before entering the final report.' },
    { icon: BookOpen, title: 'Citation Styles', desc: 'APA, MLA, Chicago, and Harvard formats supported.' },
    { icon: Zap, title: 'Real-time Updates', desc: 'WebSocket streaming gives live agent status and logs.' },
    { icon: BarChart2, title: 'Quality Scoring', desc: 'Reports receive a score based on source diversity and coverage depth.' },
    { icon: Download, title: 'Export Options', desc: 'Download as Markdown or HTML for further editing.' },
  ];
  const colorMap: Record<string, string> = {
    indigo: 'border-teal-500/25 bg-teal-500/[0.07] text-teal-400',
    sky: 'border-sky-500/25 bg-sky-500/[0.07] text-sky-400',
    amber: 'border-amber-500/25 bg-amber-500/[0.07] text-amber-400',
    emerald: 'border-emerald-500/25 bg-emerald-500/[0.07] text-emerald-400',
    purple: 'border-purple-500/25 bg-purple-500/[0.07] text-purple-400',
  };
  return (
    <div className="space-y-16 pt-4">
      <section className="text-center space-y-5">
        <Eyebrow><Info size={10} /> About Research AI</Eyebrow>
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight leading-tight" style={{ fontFamily: 'var(--font-display)' }}>
          Five agents. One comprehensive report.
        </h1>
        <p className="text-white/50 max-w-2xl mx-auto text-lg leading-relaxed">
          Research AI is a multi-agent system built on OpenRouter LLMs. Each agent specialises in one stage of the research pipeline.
        </p>
        <div className="flex justify-center">
          <PillButton onClick={onStart}>
            <Sparkles size={14} strokeWidth={2} /> Start Researching
            <span className="w-7 h-7 rounded-full bg-black/20 flex items-center justify-center"><ArrowUpRight size={14} strokeWidth={2} /></span>
          </PillButton>
        </div>
      </section>

      <section>
        <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-white/25 text-center mb-8">The 5-Stage Pipeline</p>
        <div className="space-y-4">
          {agents.map((agent, i) => {
            const Icon = agent.icon;
            return (
              <BezelCard key={agent.name} innerClassName="p-5 flex items-start gap-5">
                <div className={`p-3 rounded-xl border shrink-0 ${colorMap[agent.color]}`}><Icon size={20} strokeWidth={1.5} /></div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[9px] text-white/25 font-bold tabular-nums">0{i + 1}</span>
                    <h3 className="font-bold text-sm text-white" style={{ fontFamily: 'var(--font-display)' }}>{agent.name}</h3>
                  </div>
                  <p className="text-sm text-white/50 leading-relaxed">{agent.desc}</p>
                </div>
              </BezelCard>
            );
          })}
        </div>
      </section>

      <section>
        <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-white/25 text-center mb-8">Features</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <BezelCard key={f.title} innerClassName="p-5 h-full">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg border border-white/[0.07] bg-white/[0.03] text-teal-400 shrink-0 mt-0.5"><Icon size={15} strokeWidth={1.5} /></div>
                  <div>
                    <h4 className="font-semibold text-sm text-white mb-1" style={{ fontFamily: 'var(--font-display)' }}>{f.title}</h4>
                    <p className="text-xs text-white/40 leading-relaxed">{f.desc}</p>
                  </div>
                </div>
              </BezelCard>
            );
          })}
        </div>
      </section>

      <section>
        <BezelCard innerClassName="p-6 md:p-8">
          <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-white/25 mb-6 text-center">Technology Stack</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            {[
              { label: 'Backend', value: 'FastAPI + Python 3.11' },
              { label: 'LLMs', value: 'OpenRouter (DeepSeek, Claude, GPT-4o)' },
              { label: 'Database', value: 'MongoDB Atlas' },
              { label: 'Frontend', value: 'React 19 + Vite + Tailwind 4' },
            ].map((t) => (
              <div key={t.label} className="space-y-1.5">
                <p className="text-[9px] uppercase tracking-[0.18em] font-bold text-white/25">{t.label}</p>
                <p className="text-sm font-semibold text-white/70">{t.value}</p>
              </div>
            ))}
          </div>
        </BezelCard>
      </section>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Full Report Page — always white background, full content
───────────────────────────────────────────────────────── */
const ReportPage = ({
  report, query, onNew, onBack,
}: {
  report: ResearchReport; query?: string;
  onNew: () => void; onBack: () => void;
}) => {
  const [tab, setTab] = useState<'Report' | 'Findings' | 'Sources'>('Report');
  const sectionRefs = useRef<(HTMLElement | null)[]>([]);
  const [activeToc, setActiveToc] = useState(0);

  const exportMarkdown = () => {
    const md = [`# ${report.title}\n\n## Executive Summary\n\n${report.executiveSummary}\n`,
      ...(report.sections ?? []).map((s) => `## ${s.heading}\n\n${s.content}\n`),
      report.sources?.length ? `## Sources\n\n${report.sources.map((s, i) => `${i + 1}. [${s.title}](${s.url})`).join('\n')}` : '',
    ].join('\n');
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([md], { type: 'text/markdown' })),
      download: `${(report.title ?? 'report').replace(/\s+/g, '_')}.md`,
    });
    a.click();
  };

  const exportHTML = () => {
    const html = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>${report.title}</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:0 auto;padding:2rem;color:#1e293b}h1,h2{color:#0d9488}a{color:#0d9488}</style></head><body>
<h1>${report.title}</h1><h2>Executive Summary</h2><p>${report.executiveSummary}</p>
${(report.sections ?? []).map((s) => `<h2>${s.heading}</h2><p>${s.content}</p>`).join('')}
${report.sources?.length ? `<h2>Sources</h2><ol>${report.sources.map((s) => `<li><a href="${s.url}">${s.title}</a></li>`).join('')}</ol>` : ''}
</body></html>`;
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([html], { type: 'text/html' })),
      download: `${(report.title ?? 'report').replace(/\s+/g, '_')}.html`,
    });
    a.click();
  };

  const scrollToSection = (i: number) => {
    sectionRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setActiveToc(i);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pt-2">
        <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-white/35 hover:text-white/70 transition-colors mb-5">
          <span className="rotate-180 inline-block"><ArrowUpRight size={12} strokeWidth={1.5} /></span>
          Back
        </button>
        <Eyebrow><CheckCircle2 size={10} /> Report Ready</Eyebrow>
        <h1 className="text-2xl md:text-3xl lg:text-4xl font-extrabold mt-3 mb-4 tracking-tight leading-tight max-w-4xl"
          style={{ fontFamily: 'var(--font-display)' }}>
          {report.title}
        </h1>
        {query && <p className="text-sm text-white/35 mb-4 italic">"{query}"</p>}

        {/* Meta badges */}
        <div className="flex flex-wrap items-center gap-2 mb-5">
          {report.quality_score != null && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/[0.08] text-[10px] font-bold uppercase tracking-wider text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Quality {(report.quality_score * 100).toFixed(0)}%
            </span>
          )}
          {report.sources && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] text-[10px] text-white/40 font-semibold uppercase tracking-wider">
              <Database size={10} strokeWidth={1.5} /> {report.sources.length} sources
            </span>
          )}
          {report.findings && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] text-[10px] text-white/40 font-semibold uppercase tracking-wider">
              <Target size={10} strokeWidth={1.5} /> {report.findings.length} findings
            </span>
          )}
          <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] text-[10px] text-white/40 font-semibold uppercase tracking-wider">
            <Clock size={10} strokeWidth={1.5} /> {new Date().toLocaleDateString()}
          </span>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <PillButton variant="ghost" onClick={exportMarkdown}><Download size={13} strokeWidth={1.5} /> Markdown</PillButton>
          <PillButton variant="ghost" onClick={exportHTML}><Download size={13} strokeWidth={1.5} /> HTML</PillButton>
          <PillButton variant="ghost" onClick={() => window.print()}><Printer size={13} strokeWidth={1.5} /> Print</PillButton>
          <PillButton onClick={onNew}>
            <Plus size={13} strokeWidth={2} /> New Research
            <span className="w-6 h-6 rounded-full bg-black/20 flex items-center justify-center"><ArrowUpRight size={12} strokeWidth={2} /></span>
          </PillButton>
        </div>
      </div>

      {/* Layout: TOC sidebar (desktop) + content */}
      <div className="flex gap-6 items-start">
        {/* TOC Sidebar */}
        {report.tableOfContents && report.tableOfContents.length > 0 && (
          <aside className="hidden lg:block w-52 shrink-0 sticky top-24">
            <BezelCard innerClassName="p-4">
              <p className="text-[9px] uppercase tracking-[0.2em] font-bold text-white/25 mb-3">Contents</p>
              <nav className="space-y-0.5">
                {['Executive Summary', ...report.tableOfContents].map((item, i) => (
                  <button key={i} onClick={() => scrollToSection(i)}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors leading-tight ${activeToc === i ? 'bg-teal-500/15 text-teal-300 font-semibold' : 'text-white/35 hover:text-white/70 hover:bg-white/[0.04]'}`}>
                    {item}
                  </button>
                ))}
              </nav>
            </BezelCard>
          </aside>
        )}

        {/* Content panel */}
        <div className="flex-1 min-w-0">
          <BezelCard innerClassName="overflow-hidden">
            {/* Tab bar */}
            <div className="px-4 py-0 border-b border-white/[0.06] flex items-center bg-white/[0.015] overflow-x-auto">
              {(['Report', 'Findings', 'Sources'] as const).map((t) => (
                <button key={t} onClick={() => setTab(t)}
                  className={`relative px-5 py-4 text-xs font-semibold transition-colors whitespace-nowrap ${tab === t ? 'text-white' : 'text-white/35 hover:text-white/60'}`}
                  style={{ fontFamily: 'var(--font-display)' }}>
                  {t}{t === 'Sources' && report.sources ? ` (${report.sources.length})` : ''}{t === 'Findings' && report.findings ? ` (${report.findings.length})` : ''}
                  {tab === t && <motion.div layoutId="report-tab" className="absolute bottom-0 left-4 right-4 h-px bg-teal-400" transition={{ duration: 0.25 }} />}
                </button>
              ))}
            </div>

            {/* White content area */}
            <div className="bg-white" style={{ minHeight: '520px' }}>
              <div className="p-6 md:p-10 max-w-4xl mx-auto report-prose">

                {/* REPORT TAB */}
                {tab === 'Report' && (
                  <>
                    {report.tableOfContents && report.tableOfContents.length > 0 && (
                      <section className="mb-10 p-5 bg-teal-50 rounded-2xl border border-teal-100"
                        ref={(el) => { sectionRefs.current[0] = el; }}>
                        <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-teal-500 mb-3">Table of Contents</p>
                        <ul className="space-y-2 list-none p-0 m-0">
                          {report.tableOfContents.map((item, i) => (
                            <li key={i} className="flex items-center gap-2.5 text-sm text-teal-700 font-medium">
                              <span className="text-[10px] font-bold text-teal-300 tabular-nums w-5 shrink-0">{String(i + 1).padStart(2, '0')}</span>
                              {item}
                            </li>
                          ))}
                        </ul>
                      </section>
                    )}

                    <section className="mb-10" ref={(el) => { sectionRefs.current[report.tableOfContents ? 0 : 0] = el; }}>
                      <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 mb-4">Executive Summary</p>
                      <div className="text-base leading-relaxed text-slate-700">
                        <Markdown>{report.executiveSummary || 'No summary available.'}</Markdown>
                      </div>
                    </section>

                    {report.methodology && (
                      <section className="mb-10 p-5 bg-slate-50 rounded-2xl border border-slate-100">
                        <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 mb-3">Methodology</p>
                        <div className="italic text-slate-600 text-sm leading-relaxed"><Markdown>{report.methodology}</Markdown></div>
                      </section>
                    )}

                    {(report.sections ?? []).map((section, i) => (
                      <section key={i} className="mb-10" ref={(el) => { sectionRefs.current[i + 1] = el; }}>
                        <Markdown>{`## ${section.heading}\n\n${section.content}`}</Markdown>
                      </section>
                    ))}

                    {(!report.sections || report.sections.length === 0) && !report.executiveSummary && (
                      <div className="text-center py-12 text-slate-400">
                        <FileText size={40} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">Report content is being processed. Check back shortly.</p>
                      </div>
                    )}
                  </>
                )}

                {/* FINDINGS TAB */}
                {tab === 'Findings' && (
                  <section>
                    <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 mb-6">
                      Key Findings {report.findings && <span className="text-slate-300 ml-1">({report.findings.length})</span>}
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
                      <p className="text-slate-400 italic text-sm py-8 text-center">No findings recorded for this session.</p>
                    )}
                  </section>
                )}

                {/* SOURCES TAB */}
                {tab === 'Sources' && (
                  <section>
                    <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-400 mb-6">
                      Sources & References {report.sources && <span className="text-slate-300 ml-1">({report.sources.length})</span>}
                    </p>
                    {report.sources && report.sources.length > 0 ? (
                      <div className="grid gap-3">
                        {report.sources.map((source, i) => (
                          <div key={i} className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-teal-200 transition-colors">
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap mb-1">
                                  <h4 className="font-semibold text-sm text-slate-900 leading-tight">{i + 1}. {source.title}</h4>
                                  {source.credibilityScore != null && (
                                    <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${source.credibilityScore >= 0.7 ? 'bg-emerald-100 text-emerald-700' : source.credibilityScore >= 0.4 ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700'}`}>
                                      {(source.credibilityScore * 100).toFixed(0)}% credible
                                    </span>
                                  )}
                                  {source.apiSource && (
                                    <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-teal-100 text-teal-700">{source.apiSource}</span>
                                  )}
                                </div>
                                {source.author && <p className="text-xs text-slate-500 mb-1">By {source.author}</p>}
                                {source.url && (
                                  <a href={source.url} target="_blank" rel="noreferrer"
                                    className="text-xs text-teal-600 hover:text-teal-800 hover:underline break-all flex items-center gap-1">
                                    <ExternalLink size={11} strokeWidth={1.5} className="shrink-0" />{source.url}
                                  </a>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-400 italic text-sm py-8 text-center">No sources recorded for this session.</p>
                    )}
                  </section>
                )}

              </div>
            </div>
          </BezelCard>
        </div>
      </div>
    </div>
  );
};

/* ─────────────────────────────────────────────────────────────
   Main App
───────────────────────────────────────────────────────── */
type View = 'landing' | 'progress' | 'report' | 'history' | 'about';

export default function App() {
  const [view, setView] = useState<View>('landing');
  const [history, setHistory] = useState<ResearchHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [options, setOptions] = useState<ResearchOptions>({
    query: '', focusAreas: 'social, environmental, ethical',
    sources: ['Academic', 'News', 'Official', 'Wikipedia'],
    format: 'Markdown', citationStyle: 'APA', maxSources: 300, mode: 'Automatic',
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [agents, setAgents] = useState<AgentState[]>([
    { id: '1', name: 'User Proxy', description: 'Query analysis', status: AgentStatus.PENDING, icon: 'user' },
    { id: '2', name: 'Researcher', description: 'Data collection', status: AgentStatus.PENDING, icon: 'database' },
    { id: '3', name: 'Analyst', description: 'Synthesis', status: AgentStatus.PENDING, icon: 'cpu' },
    { id: '4', name: 'Fact Checker', description: 'Verification', status: AgentStatus.PENDING, icon: 'shield' },
    { id: '5', name: 'Report Generator', description: 'Report creation', status: AgentStatus.PENDING, icon: 'file' },
  ]);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [currentQuery, setCurrentQuery] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useScrollReveal();

  /* ── scroll log to bottom ── */
  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  /* ── health check ── */
  useEffect(() => {
    researchService.checkHealth().then(setBackendOnline);
  }, []);

  /* ── fetch history (retry when backend comes online) ── */
  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(false);
    try {
      const { sessions } = await researchService.getHistory();
      setHistory(sessions);
    } catch {
      setHistoryError(true);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (backendOnline === true) fetchHistory();
  }, [backendOnline, fetchHistory]);

  /* ── cleanup WS + poll on unmount ── */
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
        const overallPct = (msg.data?.overall_progress as number | undefined) ?? (msg.agent === 'orchestrator' ? msg.progress : undefined);
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
                fetchHistory();
              } else {
                addLog('System', 'Report data unavailable — check History to retry.', 'warning');
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
  }, [addLog, sessionId, fetchHistory]);

  const startResearch = async () => {
    if (!options.query.trim()) return;
    setCurrentQuery(options.query);
    setView('progress');
    setProgress(0);
    setLogs([]);
    setError(null);
    setReport(null);
    setAgents((prev) => prev.map((a) => ({ ...a, status: AgentStatus.PENDING })));
    try {
      addLog('System', 'Submitting research request…', 'info');
      const result = await researchService.startResearch(options);
      const sid = result.session_id;
      setSessionId(sid);
      addLog('System', `Session started: ${sid}`, 'success');
      wsRef.current?.close();
      wsRef.current = researchService.connectWebSocket(sid, handleWSMessage,
        () => addLog('System', 'WebSocket disconnected', 'warning'));
      if (pollRef.current) clearInterval(pollRef.current);
      let pollView = 'progress';
      pollRef.current = setInterval(async () => {
        try {
          const status = await researchService.getResearchStatus(sid);
          setProgress((prev) => Math.max(prev, status.progress));
          if (status.status === 'completed' || status.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
          }
          if (status.status === 'completed' && pollView !== 'report') {
            pollView = 'report';
            const res = await researchService.getResearchResults(sid);
            const r = mapResultsToReport(res as Record<string, unknown>);
            if (r) { setReport(r); setView('report'); fetchHistory(); }
          }
        } catch { /* non-fatal */ }
      }, 5000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      addLog('System', `Failed to start research: ${msg}`, 'error');
      setError(msg);
    }
  };

  /* ── Nav items ── */
  const navItems: { label: string; targetView: View; show?: boolean }[] = [
    { label: 'Research', targetView: 'landing' },
    { label: 'History', targetView: 'history' },
    { label: 'About', targetView: 'about' },
    { label: 'Report', targetView: 'report', show: !!report },
  ];

  /* ══════════════════════════════════════════════════════════
     RENDER
  ══════════════════════════════════════════════════════════ */
  return (
    <div className="grain-overlay relative min-h-[100dvh] text-white bg-[#030305]" style={{ fontFamily: 'var(--font-sans)', zIndex: 1 }}>
      <SceneBG />

      {/* ── FLOATING NAV ── */}
      <div className="fixed top-5 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none">
        <nav className="pointer-events-auto flex items-center gap-5 backdrop-blur-2xl rounded-full pl-4 pr-4 py-2.5"
          style={{ background: 'rgba(11,11,20,0.85)', border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 8px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06)' }}>
          {/* Logo */}
          <button className="flex items-center gap-2.5" onClick={() => setView('landing')}>
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-teal-500 to-teal-700 flex items-center justify-center shadow-[0_0_12px_rgba(20,184,166,0.5)]">
              <Sparkles size={14} strokeWidth={2} className="text-white" />
            </div>
            <span className="text-sm font-bold tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
              Research<span className="text-teal-400">AI</span>
            </span>
          </button>

          <div className="h-4 w-px bg-white/10 hidden sm:block" />

          {/* Links — desktop */}
          <div className="hidden sm:flex items-center gap-1">
            {navItems.filter((n) => n.show !== false).map(({ label, targetView }) => {
              const isActive = view === targetView;
              return (
                <button key={label} onClick={() => {
                  if (label === 'History') fetchHistory();
                  setView(targetView);
                }}
                  className={`px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-300 ${isActive ? 'bg-white/[0.09] text-white' : 'text-white/45 hover:text-white/80'} ${label === 'Report' ? 'border border-teal-500/30 text-teal-300' : ''}`}>
                  {label}
                </button>
              );
            })}
          </div>

          {/* Backend status */}
          {backendOnline !== null && (
            <div className={`hidden sm:flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[9px] uppercase tracking-[0.15em] font-bold ${backendOnline ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
              {backendOnline ? 'Online' : 'Offline'}
            </div>
          )}
          {backendOnline === null && (
            <div className="hidden sm:flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[9px] uppercase tracking-[0.15em] font-bold bg-amber-500/10 text-amber-400">
              <Loader2 size={9} className="animate-spin" /> Connecting
            </div>
          )}

          {/* Mobile menu button */}
          <button className="sm:hidden w-8 h-8 flex items-center justify-center" onClick={() => setNavOpen(!navOpen)}>
            {navOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </nav>
      </div>

      {/* Mobile nav overlay */}
      <AnimatePresence>
        {navOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-[#030305]/95 backdrop-blur-3xl flex flex-col items-center justify-center gap-6"
          >
            {navItems.filter((n) => n.show !== false).map(({ label, targetView }, i) => (
              <motion.button key={label}
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
                transition={{ delay: i * 0.07 }}
                onClick={() => { setNavOpen(false); if (label === 'History') fetchHistory(); setView(targetView); }}
                className="text-3xl font-bold text-white/80 hover:text-white transition-colors"
                style={{ fontFamily: 'var(--font-display)' }}>
                {label}
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══════════════════════════════════════════════════
          MAIN CONTENT
          NOTE: No opacity-0 initial states on view wrappers.
          All content renders visible immediately.
      ══════════════════════════════════════════════════ */}
      <main className="relative pt-24 pb-20 px-4 max-w-6xl mx-auto">

        {/* ─── LANDING ─── */}
        {view === 'landing' && (
          <div>
            {/* Hero — plain HTML, always visible, no animation opacity */}
            <section className="flex flex-col items-center justify-center text-center pt-10 pb-10 md:pt-14 md:pb-12 gap-6">
              <Eyebrow><Sparkles size={10} strokeWidth={2} /> Multi-Agent AI Research</Eyebrow>

              <h1 className="text-5xl sm:text-7xl md:text-8xl font-extrabold tracking-tight leading-[0.92] max-w-4xl"
                style={{ fontFamily: 'var(--font-display)', letterSpacing: '-0.03em' }}>
                Research at the{' '}
                <br className="hidden sm:block" />
                <span style={{
                  background: 'linear-gradient(135deg, #2dd4bf 0%, #14b8a6 40%, #10b981 70%, #059669 100%)',
                  WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
                }}>
                  speed of intelligence
                </span>
              </h1>

              <p className="text-lg md:text-xl text-white/55 max-w-2xl leading-relaxed">
                Five specialised AI agents collaborate to research, analyse, verify and
                generate comprehensive reports on any topic — in minutes.
              </p>

              <div className="flex flex-wrap justify-center gap-2">
                <FeatureChip icon={Globe} label="Multi-source search" />
                <FeatureChip icon={ShieldCheck} label="Fact-checked" />
                <FeatureChip icon={BookOpen} label="APA / MLA citations" />
                <FeatureChip icon={Zap} label="Real-time updates" />
              </div>
            </section>

            {/* Backend offline / DB not ready banner */}
            {backendOnline === false && (
              <div className="mb-6 flex items-start gap-3 px-5 py-4 bg-amber-500/[0.08] border border-amber-500/25 rounded-2xl text-amber-300 text-sm">
                <AlertCircle size={16} strokeWidth={1.5} className="shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold">Backend not ready</p>
                  <p className="text-amber-300/70 text-xs mt-0.5">
                    The Render server may be waking from sleep (30–60 s), or MongoDB isn't configured yet.
                    Check that <span className="font-mono">MONGODB_URL</span> and <span className="font-mono">OPENROUTER_API_KEY</span> are set in the Render dashboard.
                  </p>
                </div>
                <button onClick={() => researchService.checkHealth().then(setBackendOnline)} className="shrink-0 p-1.5 hover:text-white transition-colors">
                  <RefreshCw size={14} strokeWidth={1.5} />
                </button>
              </div>
            )}

            {/* Search input card */}
            <BezelCard>
              <div className="p-6 md:p-8">
                <div className="relative mb-5">
                  <div className="p-px rounded-2xl" style={{ background: 'linear-gradient(135deg, rgba(20,184,166,0.25) 0%, rgba(13,148,136,0.1) 50%, rgba(255,255,255,0.06) 100%)' }}>
                    <textarea
                      value={options.query}
                      onChange={(e) => setOptions({ ...options, query: e.target.value })}
                      onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) startResearch(); }}
                      placeholder="What are the major challenges of AI safety in 2026?"
                      className="w-full rounded-[calc(1rem-1px)] p-5 pb-16 text-base md:text-lg focus:outline-none min-h-[160px] resize-none text-white/90"
                      style={{ background: '#08080f', fontFamily: 'var(--font-sans)' }}
                    />
                    <style>{`textarea::placeholder{color:rgba(240,240,248,0.22)}`}</style>
                  </div>
                  <div className="absolute bottom-4 right-4 flex items-center gap-2">
                    <span className="text-[10px] text-white/20 hidden sm:block">⌘↵</span>
                    <PillButton onClick={startResearch} disabled={!options.query.trim() || backendOnline === false}>
                      Start Research
                      <span className="w-7 h-7 rounded-full bg-black/20 flex items-center justify-center"><ArrowUpRight size={14} strokeWidth={2} /></span>
                    </PillButton>
                  </div>
                </div>

                <button onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-2 text-xs font-semibold text-white/35 hover:text-white/70 transition-colors mb-4">
                  <motion.div animate={{ rotate: showAdvanced ? 180 : 0 }} transition={{ duration: 0.25 }}>
                    <ChevronDown size={14} strokeWidth={1.5} />
                  </motion.div>
                  Advanced Options
                </button>

                <AnimatePresence>
                  {showAdvanced && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3 }} className="overflow-hidden">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                        <div className="space-y-4">
                          <div>
                            <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">Focus Areas</label>
                            <input type="text" value={options.focusAreas} onChange={(e) => setOptions({ ...options, focusAreas: e.target.value })}
                              className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 focus:outline-none focus:border-teal-500/40 transition-colors" />
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            {[{ label: 'Report Format', key: 'format' as const, opts: ['Markdown', 'PDF', 'HTML'] },
                              { label: 'Citation Style', key: 'citationStyle' as const, opts: ['APA', 'MLA', 'Chicago', 'Harvard'] }
                            ].map(({ label, key, opts }) => (
                              <div key={key}>
                                <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">{label}</label>
                                <select value={options[key]} onChange={(e) => setOptions({ ...options, [key]: e.target.value })}
                                  className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 appearance-none focus:outline-none focus:border-teal-500/40 cursor-pointer">
                                  {opts.map((o) => <option key={o} value={o}>{o}</option>)}
                                </select>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="space-y-4">
                          <div>
                            <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">Source Preferences</label>
                            <div className="bg-[#07070e] border border-white/[0.07] rounded-2xl p-3 flex flex-wrap gap-2">
                              {options.sources.map((s) => (
                                <span key={s} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-500/10 border border-teal-500/25 text-teal-300 text-[10px] font-semibold uppercase tracking-wider">
                                  <span className="w-1 h-1 rounded-full bg-teal-400" />{s}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">Max Sources</label>
                              <input type="number" value={options.maxSources} onChange={(e) => setOptions({ ...options, maxSources: parseInt(e.target.value) || 50 })}
                                className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 focus:outline-none focus:border-teal-500/40" />
                            </div>
                            <div>
                              <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/30 mb-2 block">Mode</label>
                              <select value={options.mode} onChange={(e) => setOptions({ ...options, mode: e.target.value })}
                                className="w-full bg-[#07070e] border border-white/[0.07] rounded-full px-4 py-2.5 text-sm text-white/80 appearance-none focus:outline-none focus:border-teal-500/40 cursor-pointer">
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

            {/* Pipeline preview strip */}
            <div className="mt-8">
              <BezelCard innerClassName="p-5 md:p-6">
                <p className="text-[10px] uppercase tracking-[0.2em] font-semibold text-white/25 mb-5 text-center">5-Stage Research Pipeline</p>
                <div className="flex items-start justify-between relative">
                  <div className="absolute top-[22px] left-[40px] right-[40px] h-px bg-white/[0.06]" />
                  {[{ icon: User, label: 'User Proxy', desc: 'Analysis' }, { icon: Globe, label: 'Researcher', desc: 'Collection' },
                    { icon: Cpu, label: 'Analyst', desc: 'Synthesis' }, { icon: ShieldCheck, label: 'Fact Check', desc: 'Verify' },
                    { icon: FileText, label: 'Generator', desc: 'Report' },
                  ].map(({ icon: Icon, label, desc }) => (
                    <div key={label} className="flex flex-col items-center gap-2 flex-1 relative z-10">
                      <div className="p-2.5 rounded-xl border border-white/[0.07] bg-[#0d0d18] text-white/30"><Icon size={16} strokeWidth={1.5} /></div>
                      <div className="text-center">
                        <p className="text-[9px] font-semibold text-white/40 leading-tight" style={{ fontFamily: 'var(--font-display)' }}>{label}</p>
                        <p className="text-[8px] text-white/20 mt-0.5">{desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </BezelCard>
            </div>
          </div>
        )}

        {/* ─── PROGRESS ─── */}
        {view === 'progress' && (
          <div className="space-y-5">
            {error && (
              <div className="flex items-center gap-3 px-5 py-3.5 bg-rose-500/[0.08] border border-rose-500/25 rounded-2xl text-rose-300 text-sm">
                <AlertCircle size={16} strokeWidth={1.5} />
                <span className="flex-1">{error}</span>
                <button onClick={() => { setError(null); startResearch(); }} className="flex items-center gap-1.5 text-xs font-semibold hover:text-white transition-colors">
                  <RefreshCw size={12} strokeWidth={1.5} /> Retry
                </button>
              </div>
            )}

            <div className="flex items-baseline justify-between">
              <div>
                <Eyebrow><Loader2 size={10} className="animate-spin" /> Processing</Eyebrow>
                <h2 className="text-2xl md:text-3xl font-extrabold mt-3 tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
                  Research in Progress
                </h2>
                <p className="text-sm text-white/35 mt-1 max-w-lg truncate">{currentQuery || options.query}</p>
              </div>
              <span className="text-3xl font-extrabold tabular-nums text-teal-400" style={{ fontFamily: 'var(--font-display)' }}>{progress}%</span>
            </div>

            {/* Progress bar */}
            <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
              <motion.div className="h-full bg-gradient-to-r from-teal-400 via-teal-500 to-teal-600 relative"
                initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 0.8, ease: EASE_OUT }}>
                <motion.div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                  animate={{ x: ['-100%', '200%'] }} transition={{ repeat: Infinity, duration: 1.8, ease: 'linear' }} />
              </motion.div>
            </div>

            {/* Agent pipeline */}
            <BezelCard innerClassName="p-6 md:p-8">
              <div className="flex items-center justify-between mb-8">
                <h3 className="font-bold text-sm text-white/60" style={{ fontFamily: 'var(--font-display)' }}>Agent Pipeline</h3>
                <span className="text-[10px] font-mono text-white/25">{agents.filter((a) => a.status === AgentStatus.COMPLETED).length}/{agents.length} complete</span>
              </div>
              <div className="flex items-start justify-between relative px-2">
                <div className="absolute top-[26px] left-[48px] right-[48px] h-px bg-white/[0.06]" />
                <motion.div className="absolute top-[26px] left-[48px] h-px bg-gradient-to-r from-teal-500 to-emerald-500" style={{ originX: 0 }} initial={{ width: 0 }}
                  animate={{ width: (() => { const c = agents.filter((a) => a.status === AgentStatus.COMPLETED).length; const ip = agents.findIndex((a) => a.status === AgentStatus.IN_PROGRESS); const s = ip >= 0 ? ip : c; return `${(s / Math.max(agents.length - 1, 1)) * (100 - 80 / agents.length)}%`; })() }}
                  transition={{ duration: 0.8, ease: EASE_OUT }} />
                {agents.map((agent) => (
                  <div key={agent.id} className="w-1/5">
                    <AgentCell agent={agent} isActive={agent.status === AgentStatus.IN_PROGRESS} />
                  </div>
                ))}
              </div>
            </BezelCard>

            {/* Live log */}
            <BezelCard innerClassName="overflow-hidden">
              <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between bg-white/[0.02]">
                <div className="flex items-center gap-2.5">
                  <Terminal size={14} strokeWidth={1.5} className="text-teal-400" />
                  <span className="text-xs font-semibold text-white/60" style={{ fontFamily: 'var(--font-display)' }}>Live Activity</span>
                </div>
                <button onClick={() => setLogs([])} className="text-[10px] uppercase tracking-widest font-bold px-3 py-1 bg-white/[0.04] hover:bg-white/[0.08] rounded-full transition-colors text-white/30 hover:text-white/60">Clear</button>
              </div>
              <div className="h-[260px] overflow-y-auto p-4 font-mono text-[11px] space-y-1.5 scrollbar-hide">
                {logs.length === 0 && <p className="text-white/20 text-center mt-8">Awaiting pipeline events…</p>}
                {logs.map((log, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="text-white/20 shrink-0 tabular-nums">{log.timestamp}</span>
                    <span className={`font-bold shrink-0 w-28 ${log.agent === 'Researcher' ? 'text-emerald-400' : log.agent === 'Analyst' ? 'text-amber-400' : log.agent === 'Fact Checker' ? 'text-blue-400' : log.agent === 'Report Generator' ? 'text-purple-400' : log.agent === 'System' ? 'text-cyan-400' : 'text-white/40'}`}>
                      [{log.agent}]
                    </span>
                    <span className={log.type === 'error' ? 'text-rose-400' : log.type === 'success' ? 'text-emerald-400' : log.type === 'warning' ? 'text-amber-400' : 'text-white/60'}>
                      {log.message}
                    </span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            </BezelCard>
          </div>
        )}

        {/* ─── REPORT ─── */}
        {view === 'report' && (
          report ? (
            <ReportPage
              report={report}
              query={currentQuery || options.query}
              onNew={() => setView('landing')}
              onBack={() => setView(history.length > 0 ? 'history' : 'landing')}
            />
          ) : (
            /* No report data — show placeholder */
            <div className="pt-8 text-center space-y-6">
              <Eyebrow><FileText size={10} /> Report</Eyebrow>
              <h2 className="text-3xl font-extrabold tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>No Report Available</h2>
              <p className="text-white/40 max-w-md mx-auto">Research completed but the report couldn't be loaded. Check your History to access previous sessions.</p>
              <div className="flex justify-center gap-3">
                <PillButton variant="ghost" onClick={() => { fetchHistory(); setView('history'); }}>
                  <History size={14} strokeWidth={1.5} /> View History
                </PillButton>
                <PillButton onClick={() => setView('landing')}>
                  <Plus size={14} strokeWidth={2} /> New Research
                </PillButton>
              </div>
            </div>
          )
        )}

        {/* ─── HISTORY ─── */}
        {view === 'history' && (
          <div className="space-y-6">
            <div className="flex items-end justify-between pt-4 mb-8">
              <div>
                <Eyebrow><History size={10} /> Sessions</Eyebrow>
                <h2 className="text-3xl md:text-4xl font-extrabold mt-3 tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>Research History</h2>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={fetchHistory} className="p-2 rounded-full bg-white/[0.05] hover:bg-white/[0.09] transition-colors" title="Refresh">
                  <RefreshCw size={14} strokeWidth={1.5} className={historyLoading ? 'animate-spin text-teal-400' : 'text-white/40'} />
                </button>
                <PillButton variant="ghost" onClick={() => setView('landing')}>
                  <Plus size={14} strokeWidth={2} /> New Research
                </PillButton>
              </div>
            </div>

            {/* Loading state */}
            {historyLoading && (
              <BezelCard innerClassName="py-16 text-center">
                <Loader2 size={28} strokeWidth={1.5} className="mx-auto mb-3 animate-spin text-teal-400" />
                <p className="text-white/35 text-sm">Loading history…</p>
              </BezelCard>
            )}

            {/* Backend offline / error state */}
            {!historyLoading && historyError && (
              <BezelCard innerClassName="py-16 text-center">
                <AlertCircle size={36} strokeWidth={1} className="mx-auto mb-4 text-amber-400/50" />
                <p className="text-white/60 text-base font-semibold mb-1" style={{ fontFamily: 'var(--font-display)' }}>Backend is starting up</p>
                <p className="text-white/30 text-sm mb-5">The Render server may be waking from sleep (30–60s).</p>
                <PillButton variant="ghost" onClick={fetchHistory}>
                  <RefreshCw size={13} strokeWidth={1.5} /> Retry
                </PillButton>
              </BezelCard>
            )}

            {/* Empty state */}
            {!historyLoading && !historyError && history.length === 0 && (
              <BezelCard innerClassName="py-20 text-center">
                <History size={40} strokeWidth={1} className="mx-auto mb-4 text-white/15" />
                <p className="text-white/30 text-lg font-medium" style={{ fontFamily: 'var(--font-display)' }}>No research history yet</p>
                <button onClick={() => setView('landing')} className="mt-4 text-teal-400 text-sm font-semibold hover:text-teal-300 transition-colors">
                  Start your first research →
                </button>
              </BezelCard>
            )}

            {/* History list */}
            {!historyLoading && !historyError && history.length > 0 && (
              <div className="grid gap-3">
                {history.map((item, i) => (
                  <motion.div key={item.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.3 }}>
                    <div
                      className="border border-white/[0.07] rounded-2xl hover:border-teal-500/30 transition-all duration-400 cursor-pointer group bg-[#0a0a12]"
                      onClick={async () => {
                        try {
                          const res = await researchService.getResearchResults(item.id);
                          const r = mapResultsToReport(res as Record<string, unknown>);
                          if (r) {
                            setReport(r);
                            setCurrentQuery(item.query);
                            setOptions(item.options);
                            setView('report');
                          } else {
                            alert('Report not yet available for this session.');
                          }
                        } catch (e) {
                          alert(`Could not load report: ${e}`);
                        }
                      }}
                    >
                      <div className="px-5 py-4 flex items-center justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-sm text-white/80 group-hover:text-white transition-colors truncate" style={{ fontFamily: 'var(--font-display)' }}>
                            {item.query}
                          </h3>
                          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                            <span className="text-[10px] text-white/25">{new Date(item.timestamp).toLocaleString()}</span>
                            <span className="px-2 py-0.5 bg-white/[0.04] rounded-full text-[9px] uppercase tracking-wider text-white/30 border border-white/[0.06]">{item.options.format}</span>
                            <span className="px-2 py-0.5 bg-white/[0.04] rounded-full text-[9px] uppercase tracking-wider text-white/30 border border-white/[0.06]">{item.options.citationStyle}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <span className={`text-[10px] font-bold uppercase tracking-wider ${item.status === 'completed' ? 'text-emerald-400' : item.status === 'failed' ? 'text-rose-400' : 'text-amber-400'}`}>
                            {item.status}
                          </span>
                          <div className="w-7 h-7 rounded-full bg-white/[0.04] group-hover:bg-teal-500/15 flex items-center justify-center transition-colors duration-300">
                            <ArrowUpRight size={13} strokeWidth={1.5} className="text-white/30 group-hover:text-teal-400 transition-colors" />
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ─── ABOUT ─── */}
        {view === 'about' && <AboutPage onStart={() => setView('landing')} />}

      </main>

      {/* Footer */}
      <footer className="py-10 text-center">
        <p className="text-[10px] uppercase tracking-[0.2em] font-semibold text-white/15">
          &copy; {new Date().getFullYear()} Research Assistant — Multi-Agent AI
        </p>
      </footer>
    </div>
  );
}
