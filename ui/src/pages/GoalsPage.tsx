import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { goalsApi } from "@/lib/api";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { Plus, Target, Trash2 } from "lucide-react";

const RISK_COLORS = { conservative: "#3b82f6", moderate: "#f59e0b", aggressive: "#ef4444" };

export default function GoalsPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "", goal_type: "custom", target_amount: "", current_amount: "0",
    monthly_contribution: "", target_date: "", risk_tolerance: "moderate", priority: "1", notes: "",
  });

  const { data: goals } = useQuery({ queryKey: ["goals"], queryFn: () => goalsApi.list().then(r => r.data) });

  const { data: projection } = useQuery({
    queryKey: ["projection", selectedGoalId],
    queryFn: () => goalsApi.projection(selectedGoalId!, 20).then(r => r.data),
    enabled: !!selectedGoalId,
  });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await goalsApi.create({ ...form, target_amount: parseFloat(form.target_amount), current_amount: parseFloat(form.current_amount || "0"), monthly_contribution: parseFloat(form.monthly_contribution || "0"), priority: parseInt(form.priority) });
    qc.invalidateQueries({ queryKey: ["goals"] });
    setShowForm(false);
    setForm({ name: "", goal_type: "custom", target_amount: "", current_amount: "0", monthly_contribution: "", target_date: "", risk_tolerance: "moderate", priority: "1", notes: "" });
  };

  const deleteGoal = async (id: string) => {
    await goalsApi.delete(id);
    qc.invalidateQueries({ queryKey: ["goals"] });
    if (selectedGoalId === id) setSelectedGoalId(null);
  };

  const chartData = projection?.projection?.map((p: any) => ({
    year: `Year ${p.year}`, p10: p.p10, p50: p.p50, p90: p.p90,
  }));

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Financial Goals</h1>
          <button onClick={() => setShowForm(true)} className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
            <Plus size={16} /> New Goal
          </button>
        </div>

        {/* Goals list */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {(goals || []).map((g: any) => {
            const progress = (parseFloat(g.current_amount) / parseFloat(g.target_amount)) * 100;
            const rColor = RISK_COLORS[g.risk_tolerance as keyof typeof RISK_COLORS] || "#f59e0b";
            return (
              <div
                key={g.id}
                onClick={() => setSelectedGoalId(g.id === selectedGoalId ? null : g.id)}
                className={`bg-white border rounded-xl p-4 cursor-pointer hover:border-amber-400 transition-colors ${selectedGoalId === g.id ? "border-amber-500 ring-2 ring-amber-200" : ""}`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Target size={18} className="text-amber-500" />
                    <span className="font-semibold text-sm">{g.name}</span>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); deleteGoal(g.id); }} className="text-gray-300 hover:text-red-500 transition-colors">
                    <Trash2 size={14} />
                  </button>
                </div>
                <p className="text-2xl font-bold mb-1">${parseFloat(g.target_amount).toLocaleString()}</p>
                <p className="text-xs text-gray-500 mb-3">
                  {g.target_date ? `By ${g.target_date}` : "No deadline"} · ${parseFloat(g.monthly_contribution).toLocaleString()}/mo
                </p>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(progress, 100)}%`, background: rColor }} />
                </div>
                <p className="text-xs text-gray-500 mt-1">{progress.toFixed(0)}% funded · Risk: {g.risk_tolerance}</p>
              </div>
            );
          })}
          {!goals?.length && (
            <div className="col-span-2 text-center py-16 text-gray-400">
              <Target size={40} className="mx-auto mb-3 opacity-30" />
              <p>No goals yet. Create your first financial goal.</p>
            </div>
          )}
        </div>

        {/* Projection chart */}
        {projection && (
          <div className="bg-white border rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">20-Year Projection (Monte Carlo)</h3>
              <span className={`text-sm font-medium ${projection.probability_of_success >= 0.7 ? "text-green-600" : "text-orange-500"}`}>
                {(projection.probability_of_success * 100).toFixed(0)}% chance of success
              </span>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData}>
                <XAxis dataKey="year" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip formatter={(v: number) => `$${v.toLocaleString("en-US", { minimumFractionDigits: 0 })}`} />
                <Area type="monotone" dataKey="p90" stroke="#10b981" fill="#d1fae5" strokeWidth={1} name="Optimistic (90th)" />
                <Area type="monotone" dataKey="p50" stroke="#f59e0b" fill="#fef3c7" strokeWidth={2} name="Median (50th)" />
                <Area type="monotone" dataKey="p10" stroke="#ef4444" fill="#fee2e2" strokeWidth={1} name="Conservative (10th)" />
                <ReferenceLine y={projection.target_amount} stroke="#6b7280" strokeDasharray="4 4" label={{ value: "Target", position: "right", fontSize: 11 }} />
              </AreaChart>
            </ResponsiveContainer>
            <p className="text-xs text-gray-400 mt-2">Based on 1,000 simulated scenarios. For educational purposes only.</p>
          </div>
        )}
      </div>

      {/* New Goal Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-4">Create Financial Goal</h2>
            <form onSubmit={submit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="block text-sm font-medium mb-1">Goal Name</label>
                  <input required value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} placeholder="Retirement Fund" className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Type</label>
                  <select value={form.goal_type} onChange={e => setForm(f => ({...f, goal_type: e.target.value}))} className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500">
                    {["retirement","house","education","emergency","custom"].map(v => <option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Risk Tolerance</label>
                  <select value={form.risk_tolerance} onChange={e => setForm(f => ({...f, risk_tolerance: e.target.value}))} className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500">
                    {["conservative","moderate","aggressive"].map(v => <option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Target Amount ($)</label>
                  <input required type="number" step="any" value={form.target_amount} onChange={e => setForm(f => ({...f, target_amount: e.target.value}))} placeholder="500000" className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Already Saved ($)</label>
                  <input type="number" step="any" value={form.current_amount} onChange={e => setForm(f => ({...f, current_amount: e.target.value}))} placeholder="0" className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Monthly Contribution ($)</label>
                  <input type="number" step="any" value={form.monthly_contribution} onChange={e => setForm(f => ({...f, monthly_contribution: e.target.value}))} placeholder="500" className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Target Date</label>
                  <input type="date" value={form.target_date} onChange={e => setForm(f => ({...f, target_date: e.target.value}))} className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500" />
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="flex-1 border rounded-lg py-2 text-sm hover:bg-gray-50">Cancel</button>
                <button type="submit" className="flex-1 bg-amber-500 hover:bg-amber-600 text-white rounded-lg py-2 text-sm font-medium">Create Goal</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
