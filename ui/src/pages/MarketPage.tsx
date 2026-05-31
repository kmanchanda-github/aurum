import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { marketApi } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Search } from "lucide-react";

const INDEX_LABELS: Record<string, string> = {
  "^GSPC": "S&P 500",
  "^NDX": "Nasdaq 100",
  "^DJI": "Dow Jones",
  "^VIX": "VIX",
};

export default function MarketPage() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [period, setPeriod] = useState("1mo");

  const { data: indices } = useQuery({
    queryKey: ["indices"],
    queryFn: () => marketApi.indices().then((r) => r.data),
    refetchInterval: 60_000,
  });

  const { data: history } = useQuery({
    queryKey: ["history", selectedSymbol, period],
    queryFn: () => marketApi.history(selectedSymbol!, period).then((r) => r.data),
    enabled: !!selectedSymbol,
  });

  const { data: searchResults } = useQuery({
    queryKey: ["search", searchQ],
    queryFn: () => marketApi.search(searchQ).then((r) => r.data),
    enabled: searchQ.length >= 2,
    staleTime: 5_000,
  });

  const chartData = (history || []).map((b: any) => ({
    date: new Date(b.ts).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    close: b.close,
  }));

  const firstClose = chartData[0]?.close;
  const lastClose = chartData[chartData.length - 1]?.close;
  const chartColor = lastClose >= firstClose ? "#10b981" : "#ef4444";

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Market Overview</h1>

        {/* Indices strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {(indices || []).map((q: any) => {
            const up = q.change >= 0;
            return (
              <button
                key={q.symbol}
                onClick={() => setSelectedSymbol(q.symbol)}
                className={`bg-white border rounded-xl p-4 text-left hover:border-amber-400 transition-colors ${selectedSymbol === q.symbol ? "border-amber-500 ring-2 ring-amber-200" : ""}`}
              >
                <p className="text-xs text-gray-500 mb-1">{INDEX_LABELS[q.symbol] || q.symbol}</p>
                <p className="text-lg font-bold">{q.price?.toLocaleString("en-US", { minimumFractionDigits: 2 })}</p>
                <p className={`text-sm font-medium ${up ? "text-green-600" : "text-red-600"}`}>
                  {up ? "+" : ""}{q.change?.toFixed(2)} ({up ? "+" : ""}{q.change_pct?.toFixed(2)}%)
                </p>
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="bg-white border rounded-xl p-4 mb-6">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-3 text-gray-400" />
            <input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder="Search symbols (e.g. AAPL, TSLA, MSFT)..."
              className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>
          {searchResults?.length > 0 && searchQ.length >= 2 && (
            <div className="mt-2 border rounded-lg overflow-hidden divide-y">
              {searchResults.slice(0, 6).map((r: any) => (
                <button
                  key={r.symbol}
                  onClick={() => { setSelectedSymbol(r.symbol); setSearchQ(""); }}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-gray-50 text-left"
                >
                  <span className="font-medium">{r.symbol}</span>
                  <span className="text-gray-500 text-xs">{r.name} · {r.exchange}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Price chart */}
        {selectedSymbol && (
          <div className="bg-white border rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">{selectedSymbol} Price History</h3>
              <div className="flex gap-1">
                {["1wk", "1mo", "3mo", "6mo", "1y", "5y"].map((p) => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${period === p ? "bg-amber-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={chartData}>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} domain={["auto", "auto"]}
                  tickFormatter={(v) => `$${v.toLocaleString()}`} />
                <Tooltip formatter={(v: number) => [`$${v.toFixed(2)}`, "Close"]} />
                <Line type="monotone" dataKey="close" stroke={chartColor} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
