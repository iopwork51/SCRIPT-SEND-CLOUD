import { useEffect, useState } from "react";
import api from "../lib/api";
import { Plus, Trash2, Users } from "lucide-react";

export default function Groups() {
  const [groups, setGroups] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const load = () => api.get("/groups").then(r => setGroups(r.data));
  useEffect(() => { load(); }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    await api.post("/groups", { name, description });
    setShowAdd(false); setName(""); setDescription("");
    load();
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete group?")) return;
    await api.delete(`/groups/${id}`);
    load();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">Account Groups</h1>
        <button onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors">
          <Plus size={14} /> New Group
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {groups.map(g => (
          <div key={g.id} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">{g.name}</h3>
                {g.description && <p className="text-xs text-gray-500 mt-0.5">{g.description}</p>}
              </div>
              <button onClick={() => handleDelete(g.id)} className="p-1 text-gray-400 hover:text-red-500 transition-colors">
                <Trash2 size={14} />
              </button>
            </div>
            <div className="mt-4 flex items-center gap-2 text-sm text-gray-500">
              <Users size={14} />
              <span>{g.total_accounts} accounts ({g.active_accounts} active)</span>
            </div>
          </div>
        ))}
      </div>

      {showAdd && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h2 className="font-semibold mb-4">New Group</h2>
            <form onSubmit={handleAdd} className="space-y-3">
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
