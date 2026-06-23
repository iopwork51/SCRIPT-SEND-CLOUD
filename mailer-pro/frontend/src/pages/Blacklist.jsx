import { useEffect, useState } from "react";
import api from "../lib/api";
import { Plus, Trash2 } from "lucide-react";

export default function Blacklist() {
  const [entries, setEntries] = useState([]);
  const [tab, setTab] = useState("blacklist"); // blacklist | suppression
  const [suppression, setSuppression] = useState([]);
  const [offers, setOffers] = useState([]);
  const [filterOffer, setFilterOffer] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ email: "", domain: "", reason: "", source: "manual" });
  const [bulkText, setBulkText] = useState("");
  const [showBulk, setShowBulk] = useState(false);

  const loadBlacklist = () => api.get("/blacklist").then(r => setEntries(r.data));
  const loadSuppression = (offerId = "") => {
    const params = offerId ? `?offer_id=${offerId}` : "";
    api.get(`/suppression${params}`).then(r => setSuppression(r.data));
  };

  useEffect(() => {
    loadBlacklist();
    api.get("/offers").then(r => setOffers(r.data));
  }, []);

  useEffect(() => { if (tab === "suppression") loadSuppression(filterOffer); }, [tab, filterOffer]);

  const handleAdd = async (e) => {
    e.preventDefault();
    await api.post("/blacklist", form);
    setShowAdd(false); setForm({ email: "", domain: "", reason: "", source: "manual" });
    loadBlacklist();
  };

  const handleBulk = async () => {
    const entries = bulkText.split("\n").map(s => s.trim()).filter(Boolean);
    await api.post("/blacklist/import", { entries, source: "import" });
    setShowBulk(false); setBulkText(""); loadBlacklist();
  };

  const handleDelete = async (id) => {
    await api.delete(`/blacklist/${id}`);
    loadBlacklist();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Blacklist & Suppression</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowBulk(true)} className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg">Bulk Import</button>
          <button onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">
            <Plus size={14} /> Add Entry
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-4">
        {["blacklist", "suppression"].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize transition-colors ${tab === t ? "border-b-2 border-blue-600 text-blue-600 font-medium" : "text-gray-500 hover:text-gray-700"}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "blacklist" && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["Email", "Domain", "Reason", "Source", "Added", ""].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {entries.map(e => (
                <tr key={e.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-xs text-gray-700">{e.email || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-700">{e.domain || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">{e.reason || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{e.source}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{new Date(e.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleDelete(e.id)} className="p-1 hover:text-red-500 transition-colors"><Trash2 size={13} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "suppression" && (
        <div>
          <div className="mb-3">
            <select value={filterOffer} onChange={e => setFilterOffer(e.target.value)}
              className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:border-blue-400">
              <option value="">All offers</option>
              {offers.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["Email", "Offer", "Imported"].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {suppression.map(s => (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-xs text-gray-700">{s.email}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{offers.find(o => o.id === s.offer_id)?.name || s.offer_id}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{new Date(s.imported_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-4">Add to Blacklist</h2>
            <form onSubmit={handleAdd} className="space-y-3">
              <div><label className="text-xs text-gray-500 block mb-1">Email</label><input value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))} className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" /></div>
              <div><label className="text-xs text-gray-500 block mb-1">Domain</label><input value={form.domain} onChange={e => setForm(f => ({...f, domain: e.target.value}))} placeholder="example.com" className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" /></div>
              <div><label className="text-xs text-gray-500 block mb-1">Reason</label><input value={form.reason} onChange={e => setForm(f => ({...f, reason: e.target.value}))} className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" /></div>
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
                <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Save</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showBulk && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowBulk(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-2">Bulk Import Blacklist</h2>
            <p className="text-xs text-gray-500 mb-3">One email or domain per line</p>
            <textarea rows={8} value={bulkText} onChange={e => setBulkText(e.target.value)} placeholder="spam@example.com&#10;badomain.com" className="w-full border border-gray-200 rounded-lg p-2 text-xs focus:outline-none focus:border-blue-400 font-mono" />
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowBulk(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleBulk} className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Import</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
