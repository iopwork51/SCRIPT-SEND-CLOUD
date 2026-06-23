import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../lib/api";

export default function Stats() {
  const [searchParams] = useSearchParams();
  const [campaigns, setCampaigns] = useState([]);
  const [selectedId, setSelectedId] = useState(searchParams.get("campaign") || "");
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [logPage, setLogPage] = useState(1);

  useEffect(() => { api.get("/campaigns").then(r => setCampaigns(r.data)); }, []);

  useEffect(() => {
    if (!selectedId) return;
    api.get(`/campaigns/${selectedId}/stats`).then(r => setStats(r.data));
    api.get(`/campaigns/${selectedId}/logs?page=${logPage}&page_size=50`).then(r => setLogs(r.data));
  }, [selectedId, logPage]);

  const totalSent = stats?.total_sent || 0;
  const totalFailed = stats?.total_failed || 0;
  const successRate = totalSent + totalFailed > 0 ? ((totalSent / (totalSent + totalFailed)) * 100).toFixed(1) : 0;

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-900 mb-6">Campaign Stats</h1>

      <div className="mb-4">
        <select value={selectedId} onChange={e => setSelectedId(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-blue-400">
          <option value="">Select a campaign…</option>
          {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {stats && (
        <>
          {/* Stats cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: "Total Sent", value: stats.total_sent.toLocaleString(), color: "text-green-600" },
              { label: "Failed", value: stats.total_failed, color: "text-red-500" },
              { label: "Filtered", value: stats.total_filtered, color: "text-orange-500" },
              { label: "Success Rate", value: `${successRate}%`, color: "text-blue-600" },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="text-xs text-gray-500 mb-1">{label}</div>
                <div className={`text-2xl font-bold ${color}`}>{value}</div>
              </div>
            ))}
          </div>

          {/* Top domains */}
          {stats.top_domains?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
              <h2 className="font-semibold text-gray-900 mb-3 text-sm">Top Domains (by sent)</h2>
              <div className="space-y-2">
                {stats.top_domains.map(({ domain, count }) => {
                  const pct = totalSent > 0 ? ((count / totalSent) * 100).toFixed(1) : 0;
                  return (
                    <div key={domain} className="flex items-center gap-3">
                      <span className="text-xs text-gray-600 w-40 shrink-0">{domain}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-2">
                        <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-gray-500 w-12 text-right">{count.toLocaleString()}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Send logs */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900 text-sm">Send Logs</h2>
            </div>
            <table className="w-full text-xs">
              <thead className="bg-gray-50">
                <tr>
                  {["Email", "Status", "MX Server", "Proxy", "Error", "Sent At"].map(h => (
                    <th key={h} className="text-left px-4 py-2 font-medium text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {logs.map(l => (
                  <tr key={l.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-700">{l.recipient_email}</td>
                    <td className="px-4 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${l.status === "sent" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{l.status}</span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 font-mono">{l.mx_server || "—"}</td>
                    <td className="px-4 py-2 text-gray-400">{l.proxy_host || "—"}</td>
                    <td className="px-4 py-2 text-red-400 max-w-40 truncate">{l.error_message || "—"}</td>
                    <td className="px-4 py-2 text-gray-400">{l.sent_at ? new Date(l.sent_at).toLocaleTimeString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
              <button onClick={() => setLogPage(p => Math.max(1, p - 1))} disabled={logPage === 1} className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded disabled:opacity-40">Prev</button>
              <span className="text-xs text-gray-400">Page {logPage}</span>
              <button onClick={() => setLogPage(p => p + 1)} disabled={logs.length < 50} className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded disabled:opacity-40">Next</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
