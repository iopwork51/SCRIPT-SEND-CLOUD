import { useEffect, useState } from "react";
import api from "../lib/api";
import { ChevronRight, ChevronLeft, Copy, ExternalLink, CheckCircle, Send as SendIcon } from "lucide-react";

const STEPS = ["Groups", "Lists", "Offer", "Compose", "Config", "Review", "Test", "Launch"];

export default function Send() {
  const [step, setStep] = useState(0);
  const [groups, setGroups] = useState([]);
  const [lists, setLists] = useState([]);
  const [offers, setOffers] = useState([]);
  const [networks, setNetworks] = useState([]);

  // Selections
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [selectedLists, setSelectedLists] = useState([]);
  const [selectedOffer, setSelectedOffer] = useState(null);
  const [compose, setCompose] = useState({
    name: "Campaign " + new Date().toLocaleDateString(),
    header_template: "From: {an_10} <info_{an_12}@[al_12].com>\nSubject: [an_13] - Important Update",
    body_html: "<p>Hello [first_name],</p>\n<p>Click here: <a href=\"{{offer.tracking_url}}\">Claim Now</a></p>\n<div style=\"color:white;font-size:1px\">[negative]</div>",
    negative_content: "",
    links: "",
  });
  const [config, setConfig] = useState({ batch_size: 1, sleep_between: 3, max_workers: 5, send_mode: "mx_direct" });
  const [testEmail, setTestEmail] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [script, setScript] = useState(null);
  const [scriptMeta, setScriptMeta] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [campaignId, setCampaignId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("/groups"),
      api.get("/recipients/lists"),
      api.get("/offers"),
      api.get("/affiliates"),
    ]).then(([g, l, o, n]) => {
      setGroups(g.data);
      setLists(l.data);
      setOffers(o.data);
      setNetworks(n.data);
    });
  }, []);

  const toggle = (arr, setArr, id) => setArr(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const buildReview = async () => {
    // Quick pre-check
    const totalRecipients = lists.filter(l => selectedLists.includes(l.id)).reduce((s, l) => s + l.total_count, 0);
    const activeAccounts = groups.filter(g => selectedGroups.includes(g.id)).reduce((s, g) => s + g.active_accounts, 0);
    setReviewData({ totalRecipients, activeAccounts, offer: selectedOffer });
  };

  const saveCampaign = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/campaigns", {
        name: compose.name,
        header_template: compose.header_template,
        body_html: compose.body_html,
        negative_content: compose.negative_content,
        links: compose.links ? compose.links.split("\n").filter(Boolean) : [],
        offer_id: selectedOffer?.id || null,
        group_ids: selectedGroups,
        list_ids: selectedLists,
        ...config,
      });
      setCampaignId(data.id);
      return data.id;
    } finally {
      setLoading(false);
    }
  };

  const sendTest = async () => {
    setLoading(true);
    try {
      let cid = campaignId;
      if (!cid) cid = await saveCampaign();
      const { data } = await api.post(`/campaigns/${cid}/preview`, { to_email: testEmail });
      setTestResult(data);
    } finally {
      setLoading(false);
    }
  };

  const generateScript = async () => {
    setLoading(true);
    try {
      let cid = campaignId;
      if (!cid) cid = await saveCampaign();
      const { data } = await api.post(`/campaigns/${cid}/generate-script`);
      setScript(data.script);
      setScriptMeta(data);
      setCampaignId(cid);
    } finally {
      setLoading(false);
    }
  };

  const copyScript = () => {
    navigator.clipboard.writeText(script);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const next = async () => {
    if (step === 4) await buildReview();
    setStep(s => Math.min(s + 1, STEPS.length - 1));
  };

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-900 mb-6">New Campaign</h1>

      {/* Step indicator */}
      <div className="flex items-center gap-1 mb-8 overflow-x-auto pb-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-1 shrink-0">
            <button onClick={() => setStep(i)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${i === step ? "bg-blue-600 text-white" : i < step ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
              {i < step ? "✓ " : `${i + 1}. `}{s}
            </button>
            {i < STEPS.length - 1 && <ChevronRight size={12} className="text-gray-300" />}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 min-h-64">

        {/* Step 0: Groups */}
        {step === 0 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-4">Select Sender Account Groups</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {groups.map(g => (
                <label key={g.id} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedGroups.includes(g.id) ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="checkbox" checked={selectedGroups.includes(g.id)} onChange={() => toggle(selectedGroups, setSelectedGroups, g.id)} className="mt-0.5" />
                  <div>
                    <div className="font-medium text-sm text-gray-900">{g.name}</div>
                    <div className="text-xs text-gray-500">{g.total_accounts} accounts ({g.active_accounts} active)</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Step 1: Lists */}
        {step === 1 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-4">Select Recipient Lists</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {lists.map(l => (
                <label key={l.id} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedLists.includes(l.id) ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="checkbox" checked={selectedLists.includes(l.id)} onChange={() => toggle(selectedLists, setSelectedLists, l.id)} className="mt-0.5" />
                  <div>
                    <div className="font-medium text-sm text-gray-900">{l.name}</div>
                    <div className="text-xs text-gray-500">{l.total_count.toLocaleString()} total</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Offer */}
        {step === 2 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-4">Select Offer</h2>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {offers.map(o => (
                <label key={o.id} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedOffer?.id === o.id ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="radio" name="offer" checked={selectedOffer?.id === o.id} onChange={() => setSelectedOffer(o)} />
                  <div className="flex-1">
                    <div className="font-medium text-sm text-gray-900">{o.name}</div>
                    <div className="text-xs text-gray-500">
                      {networks.find(n => n.id === o.network_id)?.name || "—"} · {o.payout ? `$${o.payout}` : "no payout"} · <span className="font-mono text-xs truncate">{o.tracking_url?.slice(0, 40)}…</span>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Compose */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="font-semibold text-gray-900">Compose Email</h2>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Campaign Name</label>
              <input value={compose.name} onChange={e => setCompose(c => ({...c, name: e.target.value}))} className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Header Template (From, Subject, custom headers)</label>
              <textarea rows={4} value={compose.header_template} onChange={e => setCompose(c => ({...c, header_template: e.target.value}))}
                className="w-full border border-gray-200 rounded-lg px-2.5 py-2 text-xs font-mono focus:outline-none focus:border-blue-400" />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">HTML Body</label>
              <textarea rows={8} value={compose.body_html} onChange={e => setCompose(c => ({...c, body_html: e.target.value}))}
                className="w-full border border-gray-200 rounded-lg px-2.5 py-2 text-xs font-mono focus:outline-none focus:border-blue-400" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Links (one per line, for [LinksPlaceholder])</label>
                <textarea rows={3} value={compose.links} onChange={e => setCompose(c => ({...c, links: e.target.value}))} placeholder="https://example.com/lp1&#10;https://example.com/lp2"
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-2 text-xs font-mono focus:outline-none focus:border-blue-400" />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Negative Content (for [negative] tag)</label>
                <textarea rows={3} value={compose.negative_content} onChange={e => setCompose(c => ({...c, negative_content: e.target.value}))} placeholder="News content for spam filter bypass…"
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-2 text-xs font-mono focus:outline-none focus:border-blue-400" />
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Config */}
        {step === 4 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-4">Send Configuration</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-w-lg">
              {[
                { key: "batch_size", label: "Batch Size", min: 1, max: 100, help: "Recipients per batch" },
                { key: "sleep_between", label: "Sleep Between (sec)", min: 0, help: "Seconds between batches" },
                { key: "max_workers", label: "Max Workers", min: 1, max: 50, help: "Concurrent threads" },
              ].map(({ key, label, min, max, help }) => (
                <div key={key}>
                  <label className="text-xs text-gray-500 block mb-1">{label}</label>
                  <input type="number" min={min} max={max} value={config[key]} onChange={e => setConfig(c => ({...c, [key]: parseInt(e.target.value)}))}
                    className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
                  {help && <p className="text-xs text-gray-400 mt-0.5">{help}</p>}
                </div>
              ))}
              <div>
                <label className="text-xs text-gray-500 block mb-1">Send Mode</label>
                <select value={config.send_mode} onChange={e => setConfig(c => ({...c, send_mode: e.target.value}))}
                  className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400 bg-white">
                  <option value="mx_direct">MX Direct (like snd.py)</option>
                  <option value="smtp">Gmail SMTP</option>
                </select>
                <p className="text-xs text-gray-400 mt-0.5">MX direct bypasses Gmail SMTP limits</p>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Review */}
        {step === 5 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-4">Pre-Send Review</h2>
            {reviewData ? (
              <div className="space-y-3">
                <ReviewRow label="Total recipients" value={reviewData.totalRecipients.toLocaleString()} />
                <ReviewRow label="Active accounts" value={reviewData.activeAccounts} />
                <ReviewRow label="Selected groups" value={selectedGroups.length} />
                <ReviewRow label="Selected lists" value={selectedLists.length} />
                <ReviewRow label="Offer" value={reviewData.offer?.name || "None"} />
                <ReviewRow label="Batch size" value={config.batch_size} />
                <ReviewRow label="Send mode" value={config.send_mode} />
                <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
                  Suppression and blacklist filtering will run at script generation time. Final recipient count will be shown with the script.
                </div>
              </div>
            ) : (
              <div className="text-gray-400 text-sm">Loading review…</div>
            )}
          </div>
        )}

        {/* Step 6: Test */}
        {step === 6 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-4">Send Test Email</h2>
            <div className="flex gap-3 max-w-sm mb-4">
              <input type="email" placeholder="test@example.com" value={testEmail} onChange={e => setTestEmail(e.target.value)}
                className="flex-1 border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
              <button onClick={sendTest} disabled={!testEmail || loading}
                className="px-4 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg disabled:opacity-50">
                {loading ? "Sending…" : "Send Test"}
              </button>
            </div>
            {testResult && (
              <div className={`p-3 rounded-lg text-sm ${testResult.success ? "bg-green-50 text-green-800 border border-green-100" : "bg-red-50 text-red-800 border border-red-100"}`}>
                {testResult.success ? (
                  <span>✓ Test email sent via <code className="font-mono">{testResult.mx}</code></span>
                ) : (
                  <span>✗ Failed: {testResult.error}</span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 7: Launch */}
        {step === 7 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-2">Generate & Launch</h2>
            <p className="text-sm text-gray-500 mb-4">Generate a Python script to run in Google Cloud Shell.</p>

            {!script ? (
              <button onClick={generateScript} disabled={loading}
                className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white hover:bg-blue-700 rounded-lg disabled:opacity-50 text-sm font-medium">
                <SendIcon size={14} /> {loading ? "Generating…" : "Generate Script"}
              </button>
            ) : (
              <div className="space-y-4">
                {scriptMeta && (
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div className="bg-gray-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-gray-900">{scriptMeta.final_count.toLocaleString()}</div>
                      <div className="text-xs text-gray-500 mt-0.5">Clean recipients</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-orange-600">{scriptMeta.filtered_count}</div>
                      <div className="text-xs text-gray-500 mt-0.5">Filtered (suppressed/blacklisted)</div>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-blue-600">{scriptMeta.accounts_count}</div>
                      <div className="text-xs text-gray-500 mt-0.5">Active accounts</div>
                    </div>
                  </div>
                )}

                <div className="relative">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-gray-600">Generated Python Script</span>
                    <button onClick={copyScript} className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg transition-colors ${copied ? "bg-green-100 text-green-700" : "bg-gray-100 hover:bg-gray-200 text-gray-600"}`}>
                      {copied ? <CheckCircle size={11} /> : <Copy size={11} />}
                      {copied ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="bg-gray-900 text-green-400 text-xs rounded-xl p-4 overflow-auto max-h-64 font-mono">{script}</pre>
                </div>

                <div className="flex items-center gap-3">
                  <a href="https://console.cloud.google.com/cloudshelleditor" target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">
                    <ExternalLink size={13} /> Open Cloud Console
                  </a>
                  <span className="text-xs text-gray-400">Copy script → paste into Cloud Shell → run: <code className="font-mono">python3 script.py</code></span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-4">
        <button onClick={() => setStep(s => Math.max(0, s - 1))} disabled={step === 0}
          className="flex items-center gap-1.5 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-30">
          <ChevronLeft size={14} /> Back
        </button>
        {step < STEPS.length - 1 && (
          <button onClick={next}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg">
            Next <ChevronRight size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

function ReviewRow({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}
