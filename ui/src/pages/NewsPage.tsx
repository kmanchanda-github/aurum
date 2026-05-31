import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { newsApi } from "@/lib/api";
import { ExternalLink, Newspaper, RefreshCw } from "lucide-react";

const TOPICS = [
  "financial markets investing", "stock market today", "Federal Reserve interest rates",
  "ETF index funds", "retirement planning", "cryptocurrency bitcoin",
];

export default function NewsPage() {
  const [query, setQuery] = useState("financial markets investing");
  const [inputVal, setInputVal] = useState("");

  const { data: news, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["news", query],
    queryFn: () => newsApi.get(query, 12).then(r => r.data),
    refetchInterval: 300_000, // 5 min
  });

  const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : "";

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">Financial News</h1>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            {lastUpdated && <span>Updated {lastUpdated}</span>}
            <button onClick={() => refetch()} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Search */}
        <form onSubmit={e => { e.preventDefault(); setQuery(inputVal || "financial markets"); }} className="flex gap-2 mb-4">
          <input
            value={inputVal}
            onChange={e => setInputVal(e.target.value)}
            placeholder="Search news topics..."
            className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
          <button type="submit" className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-lg text-sm font-medium">Search</button>
        </form>

        {/* Topic pills */}
        <div className="flex flex-wrap gap-2 mb-6">
          {TOPICS.map(t => (
            <button
              key={t}
              onClick={() => { setQuery(t); setInputVal(""); }}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${query === t ? "bg-amber-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
            >
              {t}
            </button>
          ))}
        </div>

        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({length: 6}).map((_, i) => (
              <div key={i} className="bg-gray-100 rounded-xl h-32 animate-pulse" />
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(news || []).map((item: any, i: number) => (
            <a key={i} href={item.url} target="_blank" rel="noreferrer"
              className="block bg-white border rounded-xl p-4 hover:border-amber-400 hover:shadow-sm transition-all group">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm leading-snug mb-1 group-hover:text-amber-700 transition-colors line-clamp-2">
                    {item.title}
                  </p>
                  {item.summary && (
                    <p className="text-xs text-gray-500 line-clamp-2 mb-2">{item.summary}</p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <Newspaper size={12} />
                    <span>{item.source}</span>
                    <span>·</span>
                    <span>{new Date(item.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
                  </div>
                </div>
                <ExternalLink size={14} className="text-gray-300 group-hover:text-amber-500 shrink-0 mt-0.5 transition-colors" />
              </div>
            </a>
          ))}
        </div>

        {news?.length === 0 && !isLoading && (
          <div className="text-center py-16 text-gray-400">
            <Newspaper size={40} className="mx-auto mb-3 opacity-30" />
            <p>No news found for "{query}"</p>
          </div>
        )}
      </div>
    </div>
  );
}
