import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { portfolioApi } from "@/lib/api";
import { PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Plus, Trash2 } from "lucide-react";

const COLORS = ["#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ef4444", "#f97316"];

export default function PortfolioPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ symbol: "", quantity: "", cost_basis: "", asset_class: "stock" });
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  const { data: portfolios } = useQuery({
    queryKey: ["portfolios"],
    queryFn: () => portfolioApi.list().then((r) => r.data),
  });

  const portfolioId = selectedPortfolioId || portfolios?.[0]?.id;

  const { data: detail } = useQuery({
    queryKey: ["portfolio", portfolioId],
    queryFn: () => portfolioApi.get(portfolioId!).then((r) => r.data),
    enabled: !!portfolioId,
    refetchInterval: 30_000,
  });

  const createPortfolio = async () => {
    await portfolioApi.create("My Portfolio");
    qc.invalidateQueries({ queryKey: ["portfolios"] });
  };

  const addHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!portfolioId) return;
    await portfolioApi.addHolding(portfolioId, {
      symbol: form.symbol.toUpperCase(),
      quantity: parseFloat(form.quantity),
      cost_basis: parseFloat(form.cost_basis),
      asset_class: form.asset_class,
    });
    setForm({ symbol: "", quantity: "", cost_basis: "", asset_class: "stock" });
    setShowAdd(false);
    qc.invalidateQueries({ queryKey: ["portfolio", portfolioId] });
  };

  const removeHolding = async (holdingId: string) => {
    if (!portfolioId) return;
    await portfolioApi.deleteHolding(portfolioId, holdingId);
    qc.invalidateQueries({ queryKey: ["portfolio", portfolioId] });
  };

  const pnl = detail?.unrealized_pnl ?? 0;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Portfolio</h1>
          <div className="flex gap-2">
            {!portfolios?.length && (
              <button onClick={createPortfolio} className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                <Plus size={16} /> Create Portfolio
              </button>
            )}
            {portfolioId && (
              <button onClick={() => setShowAdd(true)} className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                <Plus size={16} /> Add Holding
              </button>
            )}
          </div>
        </div>

        {detail && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: "Total Value", value: `$${detail.total_value?.toLocaleString("en-US", { minimumFractionDigits: 2 })}` },
                { label: "Total Cost", value: `$${detail.total_cost?.toLocaleString("en-US", { minimumFractionDigits: 2 })}` },
                { label: "Unrealized P&L", value: `${pnl >= 0 ? "+" : ""}$${pnl?.toLocaleString("en-US", { minimumFractionDigits: 2 })}`, color: pnl >= 0 ? "text-green-600" : "text-red-600" },
                { label: "Return", value: `${detail.unrealized_pnl_pct >= 0 ? "+" : ""}${detail.unrealized_pnl_pct?.toFixed(2)}%`, color: detail.unrealized_pnl_pct >= 0 ? "text-green-600" : "text-red-600" },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-white rounded-xl border p-4">
                  <p className="text-xs text-gray-500 mb-1">{label}</p>
                  <p className={`text-lg font-bold ${color || ""}`}>{value}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              {/* Allocation pie */}
              {detail.allocation?.length > 0 && (
                <div className="bg-white rounded-xl border p-4">
                  <h3 className="text-sm font-semibold mb-3">Allocation</h3>
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie data={detail.allocation} dataKey="value" nameKey="label" cx="50%" cy="50%" outerRadius={70}>
                        {detail.allocation.map((_: any, i: number) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {detail.allocation.map((a: any, i: number) => (
                      <div key={a.label} className="flex items-center gap-1 text-xs">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                        {a.label} ({(a.weight * 100).toFixed(0)}%)
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Holdings table */}
            <div className="bg-white rounded-xl border overflow-hidden">
              <div className="px-4 py-3 border-b">
                <h3 className="font-semibold text-sm">Holdings</h3>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500">
                  <tr>
                    {["Symbol", "Shares", "Avg Cost", "Current", "Value", "P&L", ""].map((h) => (
                      <th key={h} className="text-left px-4 py-2">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {detail.holdings?.map((h: any) => {
                    const hPnl = h.unrealized_pnl ?? 0;
                    const hPnlPct = h.unrealized_pnl_pct ?? 0;
                    return (
                      <tr key={h.id} className="border-t hover:bg-gray-50">
                        <td className="px-4 py-3 font-semibold">{h.symbol}</td>
                        <td className="px-4 py-3">{parseFloat(h.quantity).toFixed(2)}</td>
                        <td className="px-4 py-3">${parseFloat(h.cost_basis).toFixed(2)}</td>
                        <td className="px-4 py-3">{h.current_price ? `$${h.current_price.toFixed(2)}` : "—"}</td>
                        <td className="px-4 py-3">{h.current_value ? `$${h.current_value.toLocaleString()}` : "—"}</td>
                        <td className={`px-4 py-3 ${hPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {h.unrealized_pnl !== undefined ? `${hPnl >= 0 ? "+" : ""}$${hPnl.toFixed(2)} (${hPnlPct.toFixed(1)}%)` : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <button onClick={() => removeHolding(h.id)} className="text-gray-400 hover:text-red-500 transition-colors">
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {!detail.holdings?.length && (
                <div className="text-center py-10 text-gray-400 text-sm">No holdings yet. Add your first holding above.</div>
              )}
            </div>
          </>
        )}

        {!portfolioId && portfolios !== undefined && (
          <div className="text-center py-20 text-gray-500">
            <p className="mb-4">No portfolio yet.</p>
            <button onClick={createPortfolio} className="bg-amber-500 hover:bg-amber-600 text-white px-6 py-2.5 rounded-lg font-medium">
              Create Portfolio
            </button>
          </div>
        )}
      </div>

      {/* Add Holding Modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-lg font-bold mb-4">Add Holding</h2>
            <form onSubmit={addHolding} className="space-y-3">
              {[
                { label: "Symbol", key: "symbol", placeholder: "AAPL", type: "text" },
                { label: "Quantity (shares)", key: "quantity", placeholder: "10", type: "number" },
                { label: "Cost Basis (per share)", key: "cost_basis", placeholder: "150.00", type: "number" },
              ].map(({ label, key, placeholder, type }) => (
                <div key={key}>
                  <label className="block text-sm font-medium mb-1">{label}</label>
                  <input
                    type={type}
                    step="any"
                    required
                    value={form[key as keyof typeof form]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    placeholder={placeholder}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              ))}
              <div>
                <label className="block text-sm font-medium mb-1">Asset Class</label>
                <select
                  value={form.asset_class}
                  onChange={(e) => setForm((f) => ({ ...f, asset_class: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                >
                  {["stock", "etf", "bond", "cash", "crypto", "other"].map((v) => (
                    <option key={v} value={v}>{v.charAt(0).toUpperCase() + v.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setShowAdd(false)} className="flex-1 border rounded-lg py-2 text-sm hover:bg-gray-50">Cancel</button>
                <button type="submit" className="flex-1 bg-amber-500 hover:bg-amber-600 text-white rounded-lg py-2 text-sm font-medium">Add</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
