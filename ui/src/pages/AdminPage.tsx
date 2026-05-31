import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import {
  BarChart2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Users,
  MessageSquare,
  Coins,
  DollarSign,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { adminApi } from "@/lib/api";
import { useAdminAuth } from "@/hooks/useAdminAuth";

// ─── Types ───────────────────────────────────────────────────────────────────

interface AgentMetric {
  agent: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
}

interface ChatTrace {
  intent: string | null;
  routing_reason: string | null;
  supervisor_confidence: number | null;
  selected_agents: string[];
  rag_categories: string[];
  retrieved_docs: { source_title: string; category: string; content_preview: string }[];
  agent_metrics: AgentMetric[];
  total_input_tokens: number;
  total_output_tokens: number;
  total_latency_ms: number;
}

interface ConvSummary {
  id: string;
  title: string;
  user_email: string;
  message_count: number;
  agents_used: string[];
  total_input_tokens: number;
  total_output_tokens: number;
  estimated_cost_usd: number;
  created_at: string;
}

const AGENT_COLORS: Record<string, string> = {
  qa: "bg-blue-500",
  portfolio: "bg-green-500",
  market: "bg-yellow-500",
  goals: "bg-purple-500",
  news: "bg-pink-500",
  tax: "bg-orange-500",
  synthesizer: "bg-gray-500",
  supervisor_route: "bg-cyan-500",
  supervisor: "bg-cyan-500",
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon: Icon,
  sub,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  sub?: string;
}) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 rounded-lg bg-yellow-500/10 flex items-center justify-center">
          <Icon size={18} className="text-yellow-400" />
        </div>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const color =
    pct >= 80 ? "bg-green-500/20 text-green-400" :
    pct >= 60 ? "bg-yellow-500/20 text-yellow-400" :
                "bg-red-500/20 text-red-400";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      {pct}% confidence
    </span>
  );
}

function AgentTimeline({ metrics }: { metrics: AgentMetric[] }) {
  const maxLatency = Math.max(...metrics.map((m) => m.latency_ms), 1);
  return (
    <div className="space-y-2">
      {metrics.map((m, i) => (
        <div key={i} className="flex items-center gap-3 text-sm">
          <span
            className={`w-24 text-xs text-white px-2 py-0.5 rounded text-center truncate ${
              AGENT_COLORS[m.agent] || "bg-gray-600"
            }`}
          >
            {m.agent}
          </span>
          <div className="flex-1 relative h-5 bg-gray-700 rounded overflow-hidden">
            <div
              className="absolute left-0 top-0 h-full bg-yellow-500/40 rounded"
              style={{ width: `${(m.latency_ms / maxLatency) * 100}%` }}
            />
            <span className="absolute inset-0 flex items-center justify-center text-xs text-gray-200">
              {m.latency_ms}ms
            </span>
          </div>
          <span className="text-xs text-blue-400 w-20 text-right">
            ↑{m.input_tokens}
          </span>
          <span className="text-xs text-green-400 w-20 text-right">
            ↓{m.output_tokens}
          </span>
        </div>
      ))}
    </div>
  );
}

function RAGDocsAccordion({
  docs,
}: {
  docs: { source_title: string; category: string; content_preview: string }[];
}) {
  const [open, setOpen] = useState<number | null>(null);
  if (!docs.length)
    return <p className="text-xs text-gray-500 italic">No RAG docs retrieved.</p>;
  return (
    <div className="space-y-1">
      {docs.map((d, i) => (
        <div key={i} className="border border-gray-700 rounded-lg overflow-hidden">
          <button
            onClick={() => setOpen(open === i ? null : i)}
            className="w-full flex items-center justify-between px-3 py-2 text-sm text-left hover:bg-gray-700/50 transition-colors"
          >
            <span className="text-gray-200 truncate flex-1">{d.source_title || "Untitled"}</span>
            <span className="text-xs text-gray-500 ml-2 mr-2">{d.category}</span>
            {open === i ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          {open === i && (
            <div className="px-3 pb-3 text-xs text-gray-400 border-t border-gray-700 pt-2">
              {d.content_preview || "—"}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── LangGraph Flow Diagram ───────────────────────────────────────────────────

function FlowArrow() {
  return (
    <div className="flex flex-col items-center">
      <div className="w-px h-4 bg-gray-600" />
      <div style={{ width: 0, height: 0, borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderTop: "6px solid #4b5563" }} />
    </div>
  );
}

function FlowNode({
  icon, title, color = "gray", compact = false, children,
}: {
  icon: string; title: string; color?: string; compact?: boolean; children?: React.ReactNode;
}) {
  const palette: Record<string, { border: string; label: string }> = {
    gray:   { border: "border-gray-600",     label: "text-gray-400" },
    cyan:   { border: "border-cyan-500/50",  label: "text-cyan-400" },
    purple: { border: "border-purple-500/50",label: "text-purple-400" },
    amber:  { border: "border-amber-500/50", label: "text-amber-400" },
    green:  { border: "border-green-500/50", label: "text-green-400" },
  };
  const c = palette[color] ?? palette.gray;
  return (
    <div className={`w-full border rounded-xl px-4 bg-gray-800/60 ${c.border} ${compact ? "py-2" : "py-3"}`}>
      <div className={`text-xs font-semibold ${c.label}`}>{icon} {title}</div>
      {children}
    </div>
  );
}

const AGENT_PALETTE: Record<string, { bg: string; text: string; border: string }> = {
  qa:        { bg: "bg-blue-500/15",   text: "text-blue-400",   border: "border-blue-500/40" },
  portfolio: { bg: "bg-green-500/15",  text: "text-green-400",  border: "border-green-500/40" },
  market:    { bg: "bg-yellow-500/15", text: "text-yellow-400", border: "border-yellow-500/40" },
  goals:     { bg: "bg-purple-500/15", text: "text-purple-400", border: "border-purple-500/40" },
  news:      { bg: "bg-pink-500/15",   text: "text-pink-400",   border: "border-pink-500/40" },
  tax:       { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/40" },
};

function LangGraphFlowDiagram({ trace }: { trace: ChatTrace }) {
  const metricMap = Object.fromEntries(
    trace.agent_metrics
      .filter((m) => !["supervisor_route", "synthesizer"].includes(m.agent))
      .map((m) => [m.agent.replace(/_agent$/, ""), m])
  );
  const synthMetric = trace.agent_metrics.find((m) => m.agent === "synthesizer");
  const displayAgents =
    trace.selected_agents.length > 0 ? trace.selected_agents : Object.keys(metricMap);
  const confidence = trace.supervisor_confidence
    ? Math.round(trace.supervisor_confidence * 100)
    : null;

  return (
    <div className="flex flex-col items-center w-full max-w-xl mx-auto py-2 gap-0">
      {/* User */}
      <FlowNode icon="💬" title="User Input" compact color="gray" />
      <FlowArrow />

      {/* Supervisor */}
      <FlowNode icon="🧭" title="Supervisor" color="cyan">
        <div className="flex flex-wrap gap-1.5 items-center mt-1.5">
          {trace.intent && (
            <span className="text-xs bg-cyan-500/10 text-cyan-300 px-2 py-0.5 rounded-full">
              {trace.intent}
            </span>
          )}
          {confidence !== null && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              confidence >= 80 ? "bg-green-500/15 text-green-400" :
              confidence >= 60 ? "bg-yellow-500/15 text-yellow-400" :
                                 "bg-red-500/15 text-red-400"
            }`}>
              {confidence}% confidence
            </span>
          )}
        </div>
        {trace.routing_reason && (
          <p className="text-xs text-gray-500 mt-1 italic line-clamp-2">{trace.routing_reason}</p>
        )}
      </FlowNode>
      <FlowArrow />

      {/* RAG */}
      {(trace.rag_categories.length > 0 || trace.retrieved_docs.length > 0) && (
        <>
          <FlowNode icon="📚" title="RAG Retrieval" color="purple">
            <div className="flex flex-wrap gap-1 mt-1.5 items-center">
              {trace.rag_categories.map((c) => (
                <span key={c} className="text-xs bg-purple-500/10 text-purple-300 px-2 py-0.5 rounded-full">
                  {c}
                </span>
              ))}
              <span className="text-xs text-gray-500 ml-1">
                {trace.retrieved_docs.length} docs retrieved
              </span>
            </div>
          </FlowNode>
          <FlowArrow />
        </>
      )}

      {/* Parallel agents */}
      {displayAgents.length > 0 && (
        <>
          <div className="w-full border border-dashed border-gray-600 rounded-xl p-3 bg-gray-800/20">
            <div className="text-xs text-gray-500 font-semibold text-center uppercase tracking-wider mb-2">
              {displayAgents.length > 1 ? "⚡ Parallel Execution" : "⚡ Agent"}
            </div>
            <div className="flex gap-2 justify-center flex-wrap">
              {displayAgents.map((agent) => {
                const m = metricMap[agent];
                const c = AGENT_PALETTE[agent] ?? { bg: "bg-gray-500/15", text: "text-gray-400", border: "border-gray-500/40" };
                return (
                  <div key={agent} className={`flex-1 min-w-[90px] max-w-[150px] border rounded-lg p-2.5 ${c.bg} ${c.border}`}>
                    <div className={`text-xs font-semibold capitalize mb-1 ${c.text}`}>{agent}</div>
                    {m ? (
                      <div className="text-xs space-y-0.5">
                        <div>
                          <span className="text-blue-400">↑{m.input_tokens}</span>
                          {" "}<span className="text-green-400">↓{m.output_tokens}</span>
                        </div>
                        <div className="text-gray-500">{m.latency_ms}ms</div>
                      </div>
                    ) : (
                      <div className="text-xs text-gray-600 italic">pending</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          <FlowArrow />
        </>
      )}

      {/* Synthesizer */}
      <FlowNode icon="🔀" title="Synthesizer" color="amber">
        <div className="flex gap-3 mt-1.5 text-xs">
          {synthMetric ? (
            <>
              <span className="text-blue-400">↑{synthMetric.input_tokens} in</span>
              <span className="text-green-400">↓{synthMetric.output_tokens} out</span>
              <span className="text-gray-500">{synthMetric.latency_ms}ms</span>
            </>
          ) : (
            <>
              <span className="text-blue-400">↑{trace.total_input_tokens} total in</span>
              <span className="text-green-400">↓{trace.total_output_tokens} total out</span>
              <span className="text-gray-500">{trace.total_latency_ms}ms</span>
            </>
          )}
        </div>
      </FlowNode>
      <FlowArrow />

      {/* Response */}
      <FlowNode icon="✅" title="Response" compact color="green">
        <span className="text-xs text-gray-500 mt-0.5 block">
          {trace.total_input_tokens + trace.total_output_tokens} total tokens · {trace.total_latency_ms}ms end-to-end
        </span>
      </FlowNode>
    </div>
  );
}

function TracePanel({ convId }: { convId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-trace", convId],
    queryFn: () => adminApi.conversationTrace(convId).then((r) => r.data),
  });

  if (isLoading)
    return <div className="p-4 text-gray-500 text-sm animate-pulse">Loading trace…</div>;

  const assistantMsgs = (data?.messages || []).filter(
    (m: { role: string; trace: ChatTrace | null }) => m.role === "assistant" && m.trace
  );

  if (!assistantMsgs.length)
    return <div className="p-4 text-gray-500 text-sm italic">No trace data available yet.</div>;

  return (
    <div className="p-4 space-y-6 bg-gray-850 border-t border-gray-700">
      {assistantMsgs.map((msg: { message_id: string; trace: ChatTrace; content: string }) => {
        const t = msg.trace;
        return (
          <div key={msg.message_id} className="space-y-4">
            {/* Flow Diagram */}
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Execution Flow
              </div>
              <LangGraphFlowDiagram trace={t} />
            </div>

            {/* Routing */}
            <div className="bg-gray-800 rounded-lg p-4 space-y-2">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Routing Decision
              </div>
              <div className="flex flex-wrap gap-2 items-center">
                {t.intent && (
                  <span className="text-sm text-gray-200 font-medium">"{t.intent}"</span>
                )}
                <ConfidenceBadge confidence={t.supervisor_confidence} />
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {t.selected_agents.map((a) => (
                  <span
                    key={a}
                    className={`text-xs text-white px-2 py-0.5 rounded ${AGENT_COLORS[a] || "bg-gray-600"}`}
                  >
                    {a}
                  </span>
                ))}
              </div>
              {t.routing_reason && (
                <p className="text-xs text-gray-500 mt-1">{t.routing_reason}</p>
              )}
            </div>

            {/* RAG */}
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                RAG Documents ({t.retrieved_docs.length})
              </div>
              <RAGDocsAccordion docs={t.retrieved_docs} />
            </div>

            {/* Agent Timeline */}
            {t.agent_metrics.length > 0 && (
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Agent Timeline — {t.total_input_tokens}↑ {t.total_output_tokens}↓ tokens ·{" "}
                  {t.total_latency_ms}ms total
                </div>
                <div className="text-xs text-gray-500 flex gap-6 mb-2">
                  <span>Agent</span>
                  <span className="ml-auto">↑ In tokens</span>
                  <span>↓ Out tokens</span>
                </div>
                <AgentTimeline metrics={t.agent_metrics} />
              </div>
            )}

            {/* Response preview */}
            <details className="bg-gray-800 rounded-lg overflow-hidden">
              <summary className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-700/50">
                Response Preview
              </summary>
              <p className="px-4 pb-4 text-sm text-gray-300 whitespace-pre-wrap line-clamp-10">
                {msg.content}
              </p>
            </details>
          </div>
        );
      })}
    </div>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

function OverviewTab() {
  const { data: stats } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => adminApi.stats().then((r) => r.data),
    refetchInterval: 30_000,
  });
  const { data: convPage } = useQuery({
    queryKey: ["admin-conversations-chart"],
    queryFn: () => adminApi.conversations({ page: 1, per_page: 100 }).then((r) => r.data),
  });

  // Build daily token chart from conversation list
  const chartData = (() => {
    const byDay: Record<string, { date: string; input: number; output: number }> = {};
    for (const c of convPage?.items || []) {
      const d = c.created_at.slice(0, 10);
      if (!byDay[d]) byDay[d] = { date: d, input: 0, output: 0 };
      byDay[d].input += c.total_input_tokens;
      byDay[d].output += c.total_output_tokens;
    }
    return Object.values(byDay).sort((a, b) => a.date.localeCompare(b.date)).slice(-14);
  })();

  const fmt = (n: number) =>
    n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` :
    n >= 1_000 ? `${(n / 1_000).toFixed(1)}K` : String(n);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Users" value={stats?.total_users ?? "—"} icon={Users} />
        <StatCard
          label="Conversations"
          value={stats?.total_conversations ?? "—"}
          icon={MessageSquare}
          sub={`${stats?.total_messages ?? 0} messages`}
        />
        <StatCard
          label="Total Tokens"
          value={fmt((stats?.total_input_tokens ?? 0) + (stats?.total_output_tokens ?? 0))}
          icon={Coins}
          sub={`↑${fmt(stats?.total_input_tokens ?? 0)} ↓${fmt(stats?.total_output_tokens ?? 0)}`}
        />
        <StatCard
          label="Est. Cost"
          value={`$${(stats?.estimated_cost_usd ?? 0).toFixed(4)}`}
          icon={DollarSign}
          sub={stats ? `${stats.langsmith_enabled ? "LangSmith ON" : "LangSmith OFF"}` : ""}
        />
      </div>

      {stats?.langsmith_enabled && stats.langsmith_url && (
        <a
          href={stats.langsmith_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 text-sm text-green-400 bg-green-500/10 border border-green-500/30 px-3 py-1.5 rounded-lg hover:bg-green-500/20 transition-colors"
        >
          <ExternalLink size={14} /> View full traces in LangSmith →
        </a>
      )}

      {chartData.length > 0 && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
          <div className="text-sm font-semibold text-gray-300 mb-4">Token Usage (last 14 days)</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} tickFormatter={fmt} />
              <Tooltip
                contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
                labelStyle={{ color: "#e5e7eb" }}
                formatter={(v: number) => [fmt(v), ""]}
              />
              <Legend />
              <Line dataKey="input" stroke="#60a5fa" strokeWidth={2} dot={false} name="Input" />
              <Line dataKey="output" stroke="#f59e0b" strokeWidth={2} dot={false} name="Output" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function ConversationsTab() {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-conversations", page],
    queryFn: () => adminApi.conversations({ page, per_page: 20 }).then((r) => r.data),
  });

  const totalPages = data ? Math.ceil(data.total / 20) : 1;

  return (
    <div className="space-y-4">
      {isLoading && <div className="text-gray-500 text-sm animate-pulse">Loading…</div>}
      {data?.items.map((c: ConvSummary) => (
        <div key={c.id} className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
          <button
            onClick={() => setExpanded(expanded === c.id ? null : c.id)}
            className="w-full flex items-start gap-4 px-5 py-4 text-left hover:bg-gray-750 transition-colors"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-white truncate">{c.title}</span>
                <span className="text-xs text-gray-500 shrink-0">{c.user_email}</span>
              </div>
              <div className="flex flex-wrap gap-1 mb-1">
                {c.agents_used.map((a) => (
                  <span
                    key={a}
                    className={`text-xs text-white px-1.5 py-0.5 rounded ${AGENT_COLORS[a] || "bg-gray-600"}`}
                  >
                    {a}
                  </span>
                ))}
              </div>
              <div className="flex gap-4 text-xs text-gray-500">
                <span>{c.message_count} messages</span>
                <span>↑{c.total_input_tokens} ↓{c.total_output_tokens} tokens</span>
                <span>${c.estimated_cost_usd.toFixed(5)}</span>
                <span>{new Date(c.created_at).toLocaleDateString()}</span>
              </div>
            </div>
            {expanded === c.id ? (
              <ChevronDown size={16} className="text-gray-400 mt-1 shrink-0" />
            ) : (
              <ChevronRight size={16} className="text-gray-400 mt-1 shrink-0" />
            )}
          </button>
          {expanded === c.id && <TracePanel convId={c.id} />}
        </div>
      ))}

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <button
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
            className="text-sm text-gray-400 disabled:opacity-40 hover:text-white transition-colors"
          >
            ← Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page === totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="text-sm text-gray-400 disabled:opacity-40 hover:text-white transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

function UsersTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page],
    queryFn: () => adminApi.users({ page, per_page: 20 }).then((r) => r.data),
  });

  const totalPages = data ? Math.ceil(data.total / 20) : 1;

  return (
    <div className="space-y-3">
      {isLoading && <div className="text-gray-500 text-sm animate-pulse">Loading…</div>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 border-b border-gray-700">
              <th className="text-left pb-2 pr-4 font-medium">Email</th>
              <th className="text-left pb-2 pr-4 font-medium">Joined</th>
              <th className="text-right pb-2 pr-4 font-medium">Conversations</th>
              <th className="text-right pb-2 pr-4 font-medium">Messages</th>
              <th className="text-right pb-2 pr-4 font-medium">Tokens (in/out)</th>
              <th className="text-right pb-2 font-medium">Est. Cost</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((u: {
              id: string; email: string; full_name: string | null;
              created_at: string; conversation_count: number; message_count: number;
              total_input_tokens: number; total_output_tokens: number; estimated_cost_usd: number;
            }) => (
              <tr key={u.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="py-3 pr-4">
                  <div className="text-white font-medium">{u.email}</div>
                  {u.full_name && (
                    <div className="text-xs text-gray-500">{u.full_name}</div>
                  )}
                </td>
                <td className="py-3 pr-4 text-gray-400 text-xs">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td className="py-3 pr-4 text-right text-gray-300">{u.conversation_count}</td>
                <td className="py-3 pr-4 text-right text-gray-300">{u.message_count}</td>
                <td className="py-3 pr-4 text-right">
                  <span className="text-blue-400">↑{u.total_input_tokens}</span>
                  {" / "}
                  <span className="text-green-400">↓{u.total_output_tokens}</span>
                </td>
                <td className="py-3 text-right text-yellow-400">
                  ${u.estimated_cost_usd.toFixed(5)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <button
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
            className="text-sm text-gray-400 disabled:opacity-40"
          >
            ← Previous
          </button>
          <span className="text-xs text-gray-500">Page {page} of {totalPages}</span>
          <button
            disabled={page === totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="text-sm text-gray-400 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const TABS = ["Overview", "Conversations", "Users"] as const;
type Tab = (typeof TABS)[number];

export default function AdminPage() {
  const { isAdmin, isLoading } = useAdminAuth();
  const [activeTab, setActiveTab] = useState<Tab>("Overview");

  if (isLoading) return null;
  if (!isAdmin) return <Navigate to="/" replace />;

  return (
    <div className="flex-1 overflow-auto bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <BarChart2 size={22} className="text-yellow-400" />
          <h1 className="text-xl font-bold text-white">Admin Dashboard</h1>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mb-6 border-b border-gray-700">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab
                  ? "border-yellow-400 text-yellow-400"
                  : "border-transparent text-gray-400 hover:text-white"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {activeTab === "Overview" && <OverviewTab />}
        {activeTab === "Conversations" && <ConversationsTab />}
        {activeTab === "Users" && <UsersTab />}
      </div>
    </div>
  );
}
