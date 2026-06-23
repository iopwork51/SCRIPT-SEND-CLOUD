import { useEffect, useState } from "react";
import api from "../lib/api";
import { Plus, Trash2, Edit2, CheckSquare, Square } from "lucide-react";

const PLATFORMS = ["none", "everflow", "cake", "hitpath", "custom"];
const SUB_VALUES = ["Mailer Id", "Process Id", "ISP Id", "List Id", "Email Id", "Vmta Id"];
const GEO_OPTIONS = ["US", "FR", "GB", "CA", "DE", "AU"];

const defaultForm = () => ({
  affiliate_id: "", name: "", status: "activated", website_url: "",
  username: "", password: "", api_platform: "none",
  network_id: "", company_name: "", api_key: "", api_username: "", api_password: "",
  sub_config: { sub1: [], sub2: [], sub3: [] },
});

export default function Affiliates() {
  const [networks, setNetworks] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(defaultForm());
  const [testResult, setTestResult] = useState(null);

  const load = () => api.get("/affiliates").then(r => setNetworks(r.data));
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (editId) {
      await api.put(`/affiliates/${editId}`, form);
    } else {
      await api.post("/affiliates", form);
    }
    setShowForm(false); setEditId(null); setForm(defaultForm()); load();
  };

  const handleEdit = (n) => {
    setForm({ ...n, sub_config: n.sub_config || { sub1: [], sub2: [], sub3: [] } });
    setEditId(n.id); setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete network?")) return;
    await api.delete(`/affiliates/${id}`);
    load();
  };

  const handleTest = async (id) => {
    const { data } = await api.post(`/affiliates/${id}/test`);
    setTestResult({ id, ...data });
  };

  const toggleSub = (sub, value) => {
    setForm(f => {
      const current = f.sub_config[sub] || [];
      const updated = current.includes(value) ? current.filter(v => v !== value) : [...current, value];
      return { ...f, sub_config: { ...f.sub_config, [sub]: updated } };
    });
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Affiliate Networks</h1>
        <button onClick={() => { setForm(defaultForm()); setEditId(null); setShowForm(true); }}
          className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors">
          <Plus size={14} /> Add Network
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              {["Name", "Platform", "Status", "Website", "Actions"].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {networks.map(n => (
              <tr key={n.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{n.name}</td>
                <td className="px-4 py-3 text-gray-500 text-xs capitalize">{n.api_platform}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${n.status === "activated" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>{n.status}</span>
                </td>
                <td className="px-4 py-3 text-xs text-blue-600 truncate max-w-48">{n.website_url || "—"}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button onClick={() => handleTest(n.id)} className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded transition-colors">Test API</button>
                    <button onClick={() => handleEdit(n)} className="p-1 hover:text-blue-600 transition-colors"><Edit2 size={13} /></button>
                    <button onClick={() => handleDelete(n.id)} className="p-1 hover:text-red-500 transition-colors"><Trash2 size={13} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {testResult && (
        <div className={`fixed bottom-4 right-4 px-4 py-2 rounded-lg text-sm shadow-lg ${testResult.success ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
          {testResult.success ? `✓ Connected — ${testResult.offer_count} offers` : `✗ ${testResult.error}`}
          <button onClick={() => setTestResult(null)} className="ml-3 opacity-50 hover:opacity-100">&times;</button>
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4 overflow-y-auto" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 my-4" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-4">{editId ? "Edit" : "Add"} Affiliate Network</h2>
            <form onSubmit={handleSubmit}>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <F label="Affiliate Id" value={form.affiliate_id} set={v => setForm(f => ({...f, affiliate_id: v}))} />
                <F label="Network Name *" value={form.name} set={v => setForm(f => ({...f, name: v}))} required />
                <SF label="Status" value={form.status} set={v => setForm(f => ({...f, status: v}))} opts={["activated","deactivated"]} />
                <F label="Website URL" value={form.website_url} set={v => setForm(f => ({...f, website_url: v}))} />
                <F label="Username" value={form.username} set={v => setForm(f => ({...f, username: v}))} />
                <F label="Password" type="password" value={form.password} set={v => setForm(f => ({...f, password: v}))} />
                <SF label="API Platform" value={form.api_platform} set={v => setForm(f => ({...f, api_platform: v}))} opts={PLATFORMS} />
                <F label="Network Id" value={form.network_id} set={v => setForm(f => ({...f, network_id: v}))} />
                <F label="Company Name" value={form.company_name} set={v => setForm(f => ({...f, company_name: v}))} />
                <F label="API Key" value={form.api_key} set={v => setForm(f => ({...f, api_key: v}))} />
                <F label="API Username" value={form.api_username} set={v => setForm(f => ({...f, api_username: v}))} />
                <F label="API Password" type="password" value={form.api_password} set={v => setForm(f => ({...f, api_password: v}))} />
              </div>

              {/* Sub parameter config */}
              <div className="border border-gray-100 rounded-lg p-3 mb-4">
                <p className="text-xs font-medium text-gray-600 mb-2">Sub Parameters (Tracking)</p>
                {["sub1", "sub2", "sub3"].map(sub => (
                  <div key={sub} className="mb-2">
                    <p className="text-xs text-gray-500 mb-1 capitalize">{sub}:</p>
                    <div className="flex flex-wrap gap-2">
                      {SUB_VALUES.map(val => {
                        const checked = (form.sub_config[sub] || []).includes(val);
                        return (
                          <button key={val} type="button" onClick={() => toggleSub(sub, val)}
                            className={`flex items-center gap-1 px-2 py-1 rounded text-xs border transition-colors ${checked ? "border-blue-500 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-500 hover:border-gray-300"}`}>
                            {checked ? <CheckSquare size={10} /> : <Square size={10} />}
                            {val}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
                <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Save</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

const F = ({ label, value, set, type = "text", required }) => (
  <div>
    <label className="block text-xs text-gray-500 mb-1">{label}</label>
    <input type={type} required={required} value={value || ""} onChange={e => set(e.target.value)}
      className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
  </div>
);

const SF = ({ label, value, set, opts }) => (
  <div>
    <label className="block text-xs text-gray-500 mb-1">{label}</label>
    <select value={value || ""} onChange={e => set(e.target.value)}
      className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white">
      {opts.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  </div>
);
