import { useEffect, useRef, useState } from "react";
import api from "../lib/api";
import { Plus, Upload, Trash2, List } from "lucide-react";

export default function Recipients() {
  const [lists, setLists] = useState([]);
  const [selectedList, setSelectedList] = useState(null);
  const [recipients, setRecipients] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const fileRef = useRef();

  const load = () => api.get("/recipients/lists").then(r => setLists(r.data));
  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    await api.post("/recipients/lists", { name, description });
    setShowAdd(false); setName(""); setDescription(""); load();
  };

  const handleUpload = async (e, listId) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    await api.post(`/recipients/lists/${listId}/upload`, form, { headers: { "Content-Type": "multipart/form-data" } });
    load();
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete list and all recipients?")) return;
    await api.delete(`/recipients/lists/${id}`);
    load();
  };

  const loadRecipients = async (list) => {
    setSelectedList(list);
    const { data } = await api.get(`/recipients/lists/${list.id}/items`);
    setRecipients(data);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Recipient Lists</h1>
        <button onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors">
          <Plus size={14} /> New List
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          {lists.map(l => (
            <div key={l.id} className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center justify-between">
                <div className="cursor-pointer" onClick={() => loadRecipients(l)}>
                  <h3 className="font-semibold text-gray-900 hover:text-blue-600">{l.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">{l.total_count.toLocaleString()} total · {l.active_count.toLocaleString()} active</p>
                </div>
                <div className="flex items-center gap-2">
                  <label className="cursor-pointer p-1.5 text-gray-400 hover:text-blue-600 transition-colors">
                    <Upload size={14} />
                    <input ref={fileRef} type="file" accept=".txt,.csv" className="hidden" onChange={e => handleUpload(e, l.id)} />
                  </label>
                  <button onClick={() => handleDelete(l.id)} className="p-1.5 text-gray-400 hover:text-red-500 transition-colors">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {selectedList && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
              <List size={14} className="text-gray-400" />
              <span className="font-medium text-sm text-gray-900">{selectedList.name}</span>
            </div>
            <div className="overflow-y-auto max-h-96">
              <table className="w-full text-xs">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    {["Email", "Name", "Status"].map(h => (
                      <th key={h} className="text-left px-4 py-2 font-medium text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {recipients.map(r => (
                    <tr key={r.id}>
                      <td className="px-4 py-2 text-gray-700">{r.email}</td>
                      <td className="px-4 py-2 text-gray-500">{r.name || "—"}</td>
                      <td className="px-4 py-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs ${r.status === "active" ? "bg-green-50 text-green-700" : "bg-gray-50 text-gray-500"}`}>{r.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {showAdd && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-4">New Recipient List</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Name</label>
                <input required value={name} onChange={e => setName(e.target.value)} className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Description</label>
                <input value={description} onChange={e => setDescription(e.target.value)} className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
                <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
