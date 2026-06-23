import { useEffect, useState } from "react";
import api from "../lib/api";
import { Plus, Download, Trash2, Edit2, RefreshCw } from "lucide-react";

const defaultImportForm = () => ({
  network_id: "", get_all: false, offer_ids: "", max_creatives: 1, get_all_creatives: false,
});

export default function Offers() {
  const [offers, setOffers] = useState([]);
  const [networks, setNetworks] = useState([]);
  const [mode, setMode] = useState("API"); // API | Manual
  const [importForm, setImportForm] = useState(defaultImportForm());
  const [showImport, setShowImport] = useState(false);
  const [showDataFields, setShowDataFields] = useState(null);
  const [dataFields, setDataFields] = useState([]);
  const [newField, setNewField] = useState({ field_key: "", field_value: "", data_type: "text" });
  const [importing, setImporting] = useState(false);

  const load = () => api.get("/offers").then(r => setOffers(r.data));
  const loadNetworks = () => api.get("/affiliates").then(r => setNetworks(r.data.filter(n => n.status === "activated")));
  useEffect(() => { load(); loadNetworks(); }, []);

  const handleImport = async () => {
    setImporting(true);
    try {
      const payload = {
        network_id: parseInt(importForm.network_id),
        get_all: importForm.get_all,
        offer_ids: importForm.offer_ids ? importForm.offer_ids.split("\n").map(s => s.trim()).filter(Boolean) : [],
        max_creatives: parseInt(importForm.max_creatives) || 1,
        get_all_creatives: importForm.get_all_creatives,
      };
      await api.post("/offers/import", payload);
      setShowImport(false); setImportForm(defaultImportForm()); load();
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Deactivate offer?")) return;
    await api.delete(`/offers/${id}`);
    load();
  };

  const openDataFields = async (offer) => {
    setShowDataFields(offer);
    const { data } = await api.get(`/offers/${offer.id}/data`);
    setDataFields(data);
  };

  const addDataField = async () => {
    if (!newField.field_key) return;
    await api.post(`/offers/${showDataFields.id}/data`, newField);
    setNewField({ field_key: "", field_value: "", data_type: "text" });
    const { data } = await api.get(`/offers/${showDataFields.id}/data`);
    setDataFields(data);
  };

  const deleteDataField = async (offerId, fieldId) => {
    await api.delete(`/offers/${offerId}/data/${fieldId}`);
    setDataFields(prev => prev.filter(f => f.id !== fieldId));
  };

  const syncSuppression = async (id) => {
    const { data } = await api.post(`/offers/${id}/sync-suppression`);
    alert(`Synced ${data.synced} suppression emails`);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Offers</h1>
        <div className="flex items-center gap-2">
          <div className="flex border border-gray-200 rounded-lg overflow-hidden text-sm">
            {["API", "Manual"].map(m => (
              <button key={m} onClick={() => setMode(m)}
                className={`px-3 py-1.5 transition-colors ${mode === m ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}>
                {m}
              </button>
            ))}
          </div>
          <button onClick={() => setShowImport(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">
            {mode === "API" ? <Download size={14} /> : <Plus size={14} />}
            {mode === "API" ? "Import Offers" : "Add Offer"}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              {["Name", "Network", "Payout", "Tracking URL", "Status", "Actions"].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {offers.map(o => (
              <tr key={o.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{o.name}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{networks.find(n => n.id === o.network_id)?.name || "—"}</td>
                <td className="px-4 py-3 text-green-700 text-xs">{o.payout ? `$${o.payout}` : "—"}</td>
                <td className="px-4 py-3 text-xs text-blue-600 truncate max-w-40">{o.tracking_url || "—"}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${o.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>{o.is_active ? "active" : "inactive"}</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button onClick={() => openDataFields(o)} className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded transition-colors">Fields</button>
                    <button onClick={() => syncSuppression(o.id)} title="Sync suppression" className="p-1 hover:text-blue-600 transition-colors"><RefreshCw size={13} /></button>
                    <button onClick={() => handleDelete(o.id)} className="p-1 hover:text-red-500 transition-colors"><Trash2 size={13} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Import Modal */}
      {showImport && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowImport(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-4">Import Offers from API</h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Affiliate Network</label>
                <select value={importForm.network_id} onChange={e => setImportForm(f => ({...f, network_id: e.target.value}))}
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white">
                  <option value="">Select network…</option>
                  {networks.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={importForm.get_all} onChange={e => setImportForm(f => ({...f, get_all: e.target.checked}))} />
                <span>Get All Offers</span>
              </label>
              {!importForm.get_all && (
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Offer Production IDs (one per line)</label>
                  <textarea rows={4} value={importForm.offer_ids} onChange={e => setImportForm(f => ({...f, offer_ids: e.target.value}))}
                    placeholder="12345&#10;67890" className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 font-mono" />
                </div>
              )}
              <div>
                <label className="text-xs text-gray-500 block mb-1">Max Number of Creatives</label>
                <input type="number" min="1" value={importForm.max_creatives} onChange={e => setImportForm(f => ({...f, max_creatives: e.target.value}))}
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={importForm.get_all_creatives} onChange={e => setImportForm(f => ({...f, get_all_creatives: e.target.checked}))} />
                <span>Get All Creatives</span>
              </label>
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <button onClick={() => setShowImport(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleImport} disabled={importing} className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg disabled:opacity-50">
                {importing ? "Importing…" : "Get Offers"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Data Fields Modal */}
      {showDataFields && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowDataFields(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-4">Data Fields — {showDataFields.name}</h2>
            <table className="w-full text-xs mb-4">
              <thead className="bg-gray-50">
                <tr>
                  {["Key", "Value", "Type", ""].map(h => <th key={h} className="text-left px-3 py-2 font-medium text-gray-500">{h}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {dataFields.map(f => (
                  <tr key={f.id}>
                    <td className="px-3 py-2 font-mono text-blue-700">{f.field_key}</td>
                    <td className="px-3 py-2 text-gray-600 truncate max-w-32">{f.field_value}</td>
                    <td className="px-3 py-2 text-gray-400">{f.data_type}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => deleteDataField(showDataFields.id, f.id)} className="text-red-400 hover:text-red-600"><Trash2 size={12} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex gap-2">
              <input placeholder="key" value={newField.field_key} onChange={e => setNewField(f => ({...f, field_key: e.target.value}))}
                className="border border-gray-200 rounded px-2 py-1 text-xs flex-1 focus:outline-none focus:border-blue-400" />
              <input placeholder="value" value={newField.field_value} onChange={e => setNewField(f => ({...f, field_value: e.target.value}))}
                className="border border-gray-200 rounded px-2 py-1 text-xs flex-1 focus:outline-none focus:border-blue-400" />
              <select value={newField.data_type} onChange={e => setNewField(f => ({...f, data_type: e.target.value}))}
                className="border border-gray-200 rounded px-2 py-1 text-xs bg-white focus:outline-none">
                {["text","url","number","html"].map(t => <option key={t}>{t}</option>)}
              </select>
              <button onClick={addDataField} className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Add</button>
            </div>
            <div className="flex justify-end mt-4">
              <button onClick={() => setShowDataFields(null)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
