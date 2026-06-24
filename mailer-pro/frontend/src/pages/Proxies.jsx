import { useEffect, useState } from "react";
import api from "../lib/api";
import {
  Plus, RefreshCw, Trash2, Activity, Zap, ChevronDown, ChevronUp, Globe,
} from "lucide-react";

const STATUS_BADGE = {
  active:   "bg-green-100 text-green-700",
  failed:   "bg-red-100 text-red-700",
  untested: "bg-gray-100 text-gray-500",
};

const COMMON_GEOS = ["US","GB","FR","DE","CA","AU","NL","ES","IT","BR","PL","TR","IN","JP","SG"];

export default function Proxies() {
  const [providers, setProviders] = useState([]);
  const [proxies, setProxies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [testingId, setTestingId] = useState(null);
  const [testingAll, setTestingAll] = useState(false);
  const [syncingId, setSyncingId] = useState(null);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [showAddProxy, setShowAddProxy] = useState(false);
  const [usageMap, setUsageMap] = useState({});
  const [filterGeo, setFilterGeo] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [syncGeos, setSyncGeos] = useState(COMMON_GEOS.join(","));

  const [providerForm, setProviderForm] = useState({
    name: "webshare", label: "", api_key: "",
    api_user: "", api_pass: "",
    proxy_host: "", proxy_port: "", proxy_username: "", proxy_password: "",
  });
  const [proxyForm, setProxyForm] = useState({
    host: "", port: "", username: "", password: "", geo: "US", proxy_type: "http", is_rotating: false,
  });

  const load = async () => {
    setLoading(true);
    const [prov, prox] = await Promise.all([
      api.get("/proxy-providers"),
      api.get("/proxies?page_size=500"),
    ]);
    setProviders(prov.data);
    setProxies(prox.data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const fetchUsage = async (id) => {
    try {
      const { data } = await api.get(`/proxy-providers/${id}/usage`);
      setUsageMap(prev => ({ ...prev, [id]: data }));
    } catch {
      setUsageMap(prev => ({ ...prev, [id]: { error: "Failed" } }));
    }
  };

  const syncProvider = async (id) => {
    setSyncingId(id);
    const geos = syncGeos.split(",").map(g => g.trim()).filter(Boolean);
    try {
      await api.post(`/proxy-providers/${id}/sync`, { geos });
      await load();
    } finally {
      setSyncingId(null);
    }
  };

  const deleteProvider = async (id) => {
    if (!confirm("Delete provider and all its proxies?")) return;
    await api.delete(`/proxy-providers/${id}`);
    load();
  };

  const testProxy = async (id) => {
    setTestingId(id);
    const { data } = await api.post(`/proxies/${id}/test`);
    setTestingId(null);
    setProxies(prev => prev.map(p =>
      p.id === id ? { ...p, status: data.working ? "active" : "failed", exit_ip: data.exit_ip } : p
    ));
  };

  const testAll = async () => {
    setTestingAll(true);
    await api.post("/proxies/test-all");
    await load();
    setTestingAll(false);
  };

  const deleteProxy = async (id) => {
    if (!confirm("Delete proxy?")) return;
    await api.delete(`/proxies/${id}`);
    setProxies(prev => prev.filter(p => p.id !== id));
  };

  const handleAddProvider = async (e) => {
    e.preventDefault();
    await api.post("/proxy-providers", {
      ...providerForm,
      proxy_port: parseInt(providerForm.proxy_port) || null,
    });
    setShowAddProvider(false);
    setProviderForm({ name: "webshare", label: "", api_key: "", api_user: "", api_pass: "", proxy_host: "", proxy_port: "", proxy_username: "", proxy_password: "" });
    load();
  };

  const handleAddProxy = async (e) => {
    e.preventDefault();
    await api.post("/proxies", { ...proxyForm, port: parseInt(proxyForm.port) });
    setShowAddProxy(false);
    setProxyForm({ host: "", port: "", username: "", password: "", geo: "US", proxy_type: "http", is_rotating: false });
    load();
  };

  const filtered = proxies.filter(p => {
    if (filterGeo && p.geo !== filterGeo) return false;
    if (filterStatus && p.status !== filterStatus) return false;
    return true;
  });

  const stats = {
    total: proxies.length,
    active: proxies.filter(p => p.status === "active").length,
    failed: proxies.filter(p => p.status === "failed").length,
    untested: proxies.filter(p => p.status === "untested").length,
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Proxy Manager</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage Webshare & DataImpulse proxy pools</p>
        </div>
        <div className="flex gap-2">
          <button onClick={testAll} disabled={testingAll} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors">
            <Activity size={14} className={testingAll ? "animate-pulse" : ""} />
            {testingAll ? "Testing…" : "Test All"}
          </button>
          <button onClick={() => setShowAddProxy(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors">
            <Plus size={14} /> Add Proxy
          </button>
          <button onClick={() => setShowAddProvider(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
            <Zap size={14} /> Add Provider
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total Proxies", value: stats.total, color: "text-gray-900" },
          { label: "Active", value: stats.active, color: "text-green-600" },
          { label: "Failed", value: stats.failed, color: "text-red-600" },
          { label: "Untested", value: stats.untested, color: "text-gray-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Providers */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Providers</h2>
        {loading ? (
          <div className="text-sm text-gray-400">Loading…</div>
        ) : providers.length === 0 ? (
          <div className="bg-white border border-dashed border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
            No providers yet — add Webshare or DataImpulse
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {providers.map(prov => (
              <div key={prov.id} className="bg-white border border-gray-200 rounded-xl p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium mb-1 ${
                      prov.name === "webshare" ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700"
                    }`}>{prov.name}</span>
                    <div className="font-medium text-gray-900">{prov.label}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{prov.proxy_count} proxies in pool</div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => fetchUsage(prov.id)}
                      title="Check usage"
                      className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors"
                    >
                      <Activity size={14} />
                    </button>
                    <button
                      onClick={() => syncProvider(prov.id)}
                      disabled={syncingId === prov.id}
                      title="Sync proxies from provider API"
                      className="p-1.5 text-gray-400 hover:text-green-600 transition-colors"
                    >
                      <RefreshCw size={14} className={syncingId === prov.id ? "animate-spin" : ""} />
                    </button>
                    <button onClick={() => deleteProvider(prov.id)} title="Delete" className="p-1.5 text-gray-400 hover:text-red-500 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Usage info */}
                {usageMap[prov.id] && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    {usageMap[prov.id].error ? (
                      <div className="text-xs text-red-500">{usageMap[prov.id].error}</div>
                    ) : (
                      <div className="flex gap-4 text-xs text-gray-500">
                        <span>Used: <strong className="text-gray-800">{usageMap[prov.id].used_gb} GB</strong></span>
                        <span>Limit: <strong className="text-gray-800">{usageMap[prov.id].total_gb} GB</strong></span>
                        {usageMap[prov.id].proxy_count != null && (
                          <span>Proxies: <strong className="text-gray-800">{usageMap[prov.id].proxy_count}</strong></span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* DataImpulse geo sync config */}
                {prov.name === "dataimpulse" && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <label className="block text-xs text-gray-400 mb-1">Geos to sync (comma-separated)</label>
                    <input
                      value={syncGeos}
                      onChange={e => setSyncGeos(e.target.value)}
                      className="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-400"
                      placeholder="US,FR,DE,GB"
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Proxy Pool */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-700">Proxy Pool</h2>
          <div className="flex gap-2">
            <select value={filterGeo} onChange={e => setFilterGeo(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400 bg-white">
              <option value="">All Geos</option>
              {[...new Set(proxies.map(p => p.geo).filter(Boolean))].sort().map(g => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-blue-400 bg-white">
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="failed">Failed</option>
              <option value="untested">Untested</option>
            </select>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">
              No proxies found. Add a provider and click Sync.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["Host:Port", "Geo", "Type", "Rotating", "Status", "Exit IP", "Last Tested", ""].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map(p => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-700">{p.host}:{p.port}</td>
                    <td className="px-4 py-3 text-xs font-medium text-gray-700">{p.geo || "—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{p.proxy_type}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{p.is_rotating ? "Yes" : "No"}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[p.status] || "bg-gray-100 text-gray-500"}`}>
                        {p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">{p.exit_ip || "—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {p.last_tested ? new Date(p.last_tested).toLocaleTimeString() : "never"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button onClick={() => testProxy(p.id)} disabled={testingId === p.id} title="Test" className="p-1 hover:text-blue-600 transition-colors">
                          <RefreshCw size={13} className={testingId === p.id ? "animate-spin" : ""} />
                        </button>
                        <button onClick={() => deleteProxy(p.id)} title="Delete" className="p-1 hover:text-red-600 transition-colors">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Add Provider Modal */}
      {showAddProvider && (
        <Modal title="Add Proxy Provider" onClose={() => setShowAddProvider(false)}>
          <form onSubmit={handleAddProvider} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Provider</label>
                <select value={providerForm.name} onChange={e => setProviderForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white">
                  <option value="webshare">Webshare</option>
                  <option value="dataimpulse">DataImpulse</option>
                </select>
              </div>
              <Field label="Label / Display Name" value={providerForm.label} onChange={v => setProviderForm(f => ({ ...f, label: v }))} required />
            </div>

            <div className="border-t border-gray-100 pt-3">
              <div className="text-xs font-medium text-gray-600 mb-2">API Credentials</div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="API Key" type="password" value={providerForm.api_key} onChange={v => setProviderForm(f => ({ ...f, api_key: v }))} />
                <Field label="API Username" value={providerForm.api_user} onChange={v => setProviderForm(f => ({ ...f, api_user: v }))} />
                <Field label="API Password" type="password" value={providerForm.api_pass} onChange={v => setProviderForm(f => ({ ...f, api_pass: v }))} />
              </div>
            </div>

            {providerForm.name === "dataimpulse" && (
              <div className="border-t border-gray-100 pt-3">
                <div className="text-xs font-medium text-gray-600 mb-2">Proxy Gateway (DataImpulse)</div>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Proxy Host" value={providerForm.proxy_host} onChange={v => setProviderForm(f => ({ ...f, proxy_host: v }))} placeholder="gw.dataimpulse.com" />
                  <Field label="Proxy Port" type="number" value={providerForm.proxy_port} onChange={v => setProviderForm(f => ({ ...f, proxy_port: v }))} placeholder="823" />
                  <Field label="Proxy Username" value={providerForm.proxy_username} onChange={v => setProviderForm(f => ({ ...f, proxy_username: v }))} />
                  <Field label="Proxy Password" type="password" value={providerForm.proxy_password} onChange={v => setProviderForm(f => ({ ...f, proxy_password: v }))} />
                </div>
                <p className="text-xs text-gray-400 mt-2">Username geo format: <span className="font-mono">username-cc-US</span> (auto-generated on sync)</p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowAddProvider(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Save Provider</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Add Proxy Modal */}
      {showAddProxy && (
        <Modal title="Add Proxy Manually" onClose={() => setShowAddProxy(false)}>
          <form onSubmit={handleAddProxy} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Host" value={proxyForm.host} onChange={v => setProxyForm(f => ({ ...f, host: v }))} required />
              <Field label="Port" type="number" value={proxyForm.port} onChange={v => setProxyForm(f => ({ ...f, port: v }))} required />
              <Field label="Username" value={proxyForm.username} onChange={v => setProxyForm(f => ({ ...f, username: v }))} />
              <Field label="Password" type="password" value={proxyForm.password} onChange={v => setProxyForm(f => ({ ...f, password: v }))} />
              <div>
                <label className="block text-xs text-gray-500 mb-1">Geo</label>
                <select value={proxyForm.geo} onChange={e => setProxyForm(f => ({ ...f, geo: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white">
                  {COMMON_GEOS.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Type</label>
                <select value={proxyForm.proxy_type} onChange={e => setProxyForm(f => ({ ...f, proxy_type: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white">
                  <option value="http">HTTP</option>
                  <option value="socks5">SOCKS5</option>
                </select>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input type="checkbox" checked={proxyForm.is_rotating} onChange={e => setProxyForm(f => ({ ...f, is_rotating: e.target.checked }))} />
              Rotating proxy
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowAddProxy(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Save</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, type = "text", value, onChange, required, placeholder }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input type={type} required={required} value={value} placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400"
      />
    </div>
  );
}
