import { useEffect, useState } from "react";
import api from "../lib/api";
import { Plus, RefreshCw, Upload, Trash2, Activity, RotateCcw } from "lucide-react";

const STATUS_BADGE = {
  active: "bg-green-100 text-green-700",
  proxy_error: "bg-red-100 text-red-700",
  smtp_blocked: "bg-orange-100 text-orange-700",
  auth_failed: "bg-red-100 text-red-700",
  testing: "bg-blue-100 text-blue-700",
};

export default function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [showBulk, setShowBulk] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [form, setForm] = useState({
    email: "", password: "", account_type: "gmail",
    proxy_host: "", proxy_port: "", proxy_user: "", proxy_pass: "",
    proxy_geo: "US", proxy_type: "webshare_gb", group_id: "", max_per_day: 500,
  });
  const [bulkCsv, setBulkCsv] = useState("");
  const [bulkGroupId, setBulkGroupId] = useState("");

  const load = () => {
    setLoading(true);
    Promise.all([api.get("/accounts?page_size=200"), api.get("/groups")]).then(([a, g]) => {
      setAccounts(a.data);
      setGroups(g.data);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    await api.post("/accounts", { ...form, proxy_port: parseInt(form.proxy_port) || null, group_id: form.group_id || null });
    setShowAdd(false);
    setForm({ email: "", password: "", account_type: "gmail", proxy_host: "", proxy_port: "", proxy_user: "", proxy_pass: "", proxy_geo: "US", proxy_type: "webshare_gb", group_id: "", max_per_day: 500 });
    load();
  };

  const handleBulk = async () => {
    await api.post("/accounts/bulk", { csv_data: bulkCsv, group_id: bulkGroupId || null });
    setShowBulk(false);
    setBulkCsv("");
    load();
  };

  const testAccount = async (id) => {
    setTestingId(id);
    const { data } = await api.post(`/accounts/${id}/test`);
    setTestingId(null);
    setAccounts(prev => prev.map(a => a.id === id ? { ...a, status: data.status } : a));
  };

  const rotateProxy = async (id) => {
    await api.post(`/accounts/${id}/rotate-proxy`);
    load();
  };

  const deleteAccount = async (id) => {
    if (!confirm("Delete this account?")) return;
    await api.delete(`/accounts/${id}`);
    setAccounts(prev => prev.filter(a => a.id !== id));
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Sender Accounts</h1>
        <div className="flex gap-2">
          <button onClick={() => api.post("/accounts/test-all")} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors">
            <Activity size={14} /> Test All
          </button>
          <button onClick={() => setShowBulk(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors">
            <Upload size={14} /> Bulk Import
          </button>
          <button onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
            <Plus size={14} /> Add Account
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["Email", "Type", "Group", "Geo", "Status", "Daily Sent", "Last Check", "Actions"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {accounts.map(a => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900 text-xs">{a.email}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{a.account_type}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{groups.find(g => g.id === a.group_id)?.name || "—"}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{a.proxy_geo || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[a.status] || "bg-gray-100 text-gray-600"}`}>{a.status}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{a.daily_sent}/{a.max_per_day}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{a.last_health_check ? new Date(a.last_health_check).toLocaleTimeString() : "never"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button onClick={() => testAccount(a.id)} disabled={testingId === a.id} title="Test" className="p-1 hover:text-blue-600 transition-colors">
                        <RefreshCw size={13} className={testingId === a.id ? "animate-spin" : ""} />
                      </button>
                      <button onClick={() => rotateProxy(a.id)} title="Rotate proxy" className="p-1 hover:text-green-600 transition-colors">
                        <RotateCcw size={13} />
                      </button>
                      <button onClick={() => deleteAccount(a.id)} title="Delete" className="p-1 hover:text-red-600 transition-colors">
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

      {/* Add Account Modal */}
      {showAdd && (
        <Modal title="Add Account" onClose={() => setShowAdd(false)}>
          <form onSubmit={handleAdd} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Email" type="email" value={form.email} onChange={v => setForm(f => ({...f, email: v}))} required />
              <Field label="App Password" type="password" value={form.password} onChange={v => setForm(f => ({...f, password: v}))} required />
              <Field label="Proxy Host" value={form.proxy_host} onChange={v => setForm(f => ({...f, proxy_host: v}))} />
              <Field label="Proxy Port" type="number" value={form.proxy_port} onChange={v => setForm(f => ({...f, proxy_port: v}))} />
              <Field label="Proxy User" value={form.proxy_user} onChange={v => setForm(f => ({...f, proxy_user: v}))} />
              <Field label="Proxy Pass" type="password" value={form.proxy_pass} onChange={v => setForm(f => ({...f, proxy_pass: v}))} />
              <SelectField label="Geo" value={form.proxy_geo} onChange={v => setForm(f => ({...f, proxy_geo: v}))}
                options={["US","FR","GB","CA","DE","AU","NL","ES","IT","BR"]} />
              <SelectField label="Group" value={form.group_id} onChange={v => setForm(f => ({...f, group_id: v}))}
                options={groups.map(g => ({ value: g.id, label: g.name }))} placeholder="No group" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Save</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Bulk Import Modal */}
      {showBulk && (
        <Modal title="Bulk Import (CSV)" onClose={() => setShowBulk(false)}>
          <p className="text-xs text-gray-500 mb-2 font-mono bg-gray-50 p-2 rounded">email:password:proxy_host:port:proxy_user:proxy_pass:geo:type</p>
          <textarea
            rows={8} value={bulkCsv} onChange={e => setBulkCsv(e.target.value)}
            placeholder="john@gmail.com:AppPass1234:rp.webshare.io:5432:user:pass:US:webshare_gb"
            className="w-full text-xs font-mono border border-gray-200 rounded-lg p-2 focus:outline-none focus:border-blue-400"
          />
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowBulk(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
            <button onClick={handleBulk} className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Import</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
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

function SelectField({ label, value, onChange, options, placeholder }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white">
        {placeholder && <option value="">{placeholder}</option>}
        {options.map(opt => typeof opt === "object"
          ? <option key={opt.value} value={opt.value}>{opt.label}</option>
          : <option key={opt} value={opt}>{opt}</option>
        )}
      </select>
    </div>
  );
}
