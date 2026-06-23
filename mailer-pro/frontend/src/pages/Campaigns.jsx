import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Plus, Play, Pause, BarChart2 } from "lucide-react";

const STATUS_BADGE = {
  draft: "bg-gray-100 text-gray-600",
  running: "bg-blue-100 text-blue-700",
  paused: "bg-yellow-100 text-yellow-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get("/campaigns").then(r => setCampaigns(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const toggleStatus = async (c) => {
    if (c.status === "running") {
      await api.post(`/campaigns/${c.id}/pause`);
    } else {
      await api.post(`/campaigns/${c.id}/start`);
    }
    load();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Campaigns</h1>
        <Link to="/send" className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors">
          <Plus size={14} /> New Campaign
        </Link>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["Name", "Status", "Recipients", "Sent", "Failed", "Filtered", "Mode", "Created", "Actions"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {campaigns.map(c => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[c.status] || "bg-gray-100 text-gray-600"}`}>{c.status}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{c.total_recipients.toLocaleString()}</td>
                  <td className="px-4 py-3 text-green-600 text-xs">{c.total_sent.toLocaleString()}</td>
                  <td className="px-4 py-3 text-red-500 text-xs">{c.total_failed}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{c.total_filtered}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{c.send_mode}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{new Date(c.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button onClick={() => toggleStatus(c)} className="p-1 hover:text-blue-600 transition-colors" title={c.status === "running" ? "Pause" : "Start"}>
                        {c.status === "running" ? <Pause size={13} /> : <Play size={13} />}
                      </button>
                      <Link to={`/stats?campaign=${c.id}`} className="p-1 hover:text-purple-600 transition-colors"><BarChart2 size={13} /></Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
