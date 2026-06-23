import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { Users, Mail, TrendingUp, AlertCircle } from "lucide-react";

function StatCard({ label, value, sub, icon: Icon, color }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-500">{label}</span>
        <Icon size={18} className={color} />
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [accounts, setAccounts] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/accounts?page_size=200"),
      api.get("/campaigns?page_size=10"),
    ]).then(([acc, camp]) => {
      setAccounts(acc.data);
      setCampaigns(camp.data);
    }).finally(() => setLoading(false));
  }, []);

  const activeAccounts = accounts.filter(a => a.status === "active").length;
  const blockedAccounts = accounts.filter(a => ["smtp_blocked", "auth_failed"].includes(a.status)).length;
  const runningCampaigns = campaigns.filter(c => c.status === "running").length;

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Accounts" value={accounts.length} sub={`${activeAccounts} active`} icon={Users} color="text-blue-500" />
        <StatCard label="Active Accounts" value={activeAccounts} sub="Ready to send" icon={Mail} color="text-green-500" />
        <StatCard label="Blocked Accounts" value={blockedAccounts} sub="Need attention" icon={AlertCircle} color="text-red-500" />
        <StatCard label="Running Campaigns" value={runningCampaigns} sub="In progress" icon={TrendingUp} color="text-purple-500" />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Recent Campaigns</h2>
          <Link to="/campaigns" className="text-sm text-blue-600 hover:underline">View all</Link>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : campaigns.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">No campaigns yet. <Link to="/send" className="text-blue-600 hover:underline">Start one</Link></div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["Name", "Status", "Sent", "Failed", "Created"].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {campaigns.map(c => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium text-gray-900">{c.name}</td>
                  <td className="px-5 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-5 py-3 text-gray-600">{c.total_sent}</td>
                  <td className="px-5 py-3 text-red-500">{c.total_failed}</td>
                  <td className="px-5 py-3 text-gray-400">{new Date(c.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    draft: "bg-gray-100 text-gray-600",
    running: "bg-blue-100 text-blue-700",
    paused: "bg-yellow-100 text-yellow-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}
