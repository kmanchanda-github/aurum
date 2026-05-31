import { useQuery, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/lib/api";
import { CheckCircle, XCircle, Loader } from "lucide-react";

export default function SettingsPage() {
  const qc = useQueryClient();

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => settingsApi.get().then(r => r.data),
  });

  const { data: adapterHealth, isLoading: loadingHealth } = useQuery({
    queryKey: ["adapterHealth"],
    queryFn: () => settingsApi.adapterHealth().then(r => r.data),
    refetchInterval: 60_000,
  });

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Settings</h1>

        {/* Data Sources */}
        <div className="bg-white border rounded-xl mb-6 overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-sm">Data Source Adapters</h2>
            <p className="text-xs text-gray-500 mt-0.5">Active market data providers</p>
          </div>
          <div className="divide-y">
            {loadingHealth && (
              <div className="p-4 text-center">
                <Loader size={20} className="animate-spin mx-auto text-gray-300" />
              </div>
            )}
            {(adapterHealth || []).map((a: any) => (
              <div key={a.name} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium capitalize">{a.name.replace(/_/g, " ")}</p>
                  {a.latency_ms && <p className="text-xs text-gray-400">{a.latency_ms.toFixed(0)}ms</p>}
                  {a.last_error && <p className="text-xs text-red-400">{a.last_error.slice(0, 60)}</p>}
                </div>
                <div className="flex items-center gap-2">
                  {a.healthy ? (
                    <span className="flex items-center gap-1 text-green-600 text-xs font-medium">
                      <CheckCircle size={14} /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-500 text-xs font-medium">
                      <XCircle size={14} /> Error
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Watchlist */}
        <div className="bg-white border rounded-xl mb-6 overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-sm">Watchlist</h2>
          </div>
          <div className="p-4">
            <p className="text-sm text-gray-500">Symbols: {settings?.watchlist?.join(", ") || "None"}</p>
          </div>
        </div>

        {/* About */}
        <div className="bg-white border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-sm">About Aurum</h2>
          </div>
          <div className="p-4 space-y-2 text-sm text-gray-600">
            <p><span className="font-medium">Version:</span> 0.1.0</p>
            <p><span className="font-medium">Stack:</span> LangGraph · FastAPI · React · ChromaDB · yfinance</p>
            <p><span className="font-medium">Currency:</span> {settings?.preferred_currency || "USD"}</p>
            <p className="text-xs text-gray-400 pt-2 border-t">
              Aurum provides educational financial information only. Nothing here constitutes personalized investment advice.
              Always consult a licensed financial advisor before making investment decisions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
