import { useEffect, useState } from "react";
import api from "../lib/api";
import { Send as SendIcon, Copy, CheckCircle, ExternalLink, RefreshCw } from "lucide-react";

// ── tiny helpers ──────────────────────────────────────────────────────────────
const Toggle = ({ value, onChange, label }) => (
  <button
    type="button"
    onClick={() => onChange(!value)}
    className={`px-3 py-0.5 rounded text-xs font-bold border transition-colors ${
      value ? "bg-green-500 text-white border-green-500" : "bg-gray-100 text-gray-500 border-gray-200"
    }`}
  >
    {value ? "ON" : "OFF"}
  </button>
);

const SectionLabel = ({ children }) => (
  <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">{children}</div>
);

const Field = ({ label, children }) => (
  <div>
    <SectionLabel>{label}</SectionLabel>
    {children}
  </div>
);

const sel =
  "w-full border border-gray-300 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:border-blue-400";
const inp =
  "w-full border border-gray-300 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-400";
const ta =
  "w-full border border-gray-300 rounded px-2 py-1 text-xs font-mono resize-none focus:outline-none focus:border-blue-400";

// ── component ─────────────────────────────────────────────────────────────────
export default function Send() {
  // -- data
  const [groups, setGroups]     = useState([]);
  const [lists, setLists]       = useState([]);
  const [offers, setOffers]     = useState([]);
  const [networks, setNetworks] = useState([]);

  // -- selections
  const [selGroups, setSelGroups] = useState([]);
  const [selLists, setSelLists]   = useState([]);

  // -- config fields
  const [cfg, setCfg] = useState({
    send_mode:       "mx_direct",     // mx_direct (basic, no account) | smtp | mx_proxy
    content_type:    "text/html",
    charset:         "UTF-8",
    transfer_enc:    "7bit",
    process_type:    "batch",         // batch | xdelay
    batch:           1000,
    xdelay_ms:       1000,
    max_workers:     5,
    link_type:       "routing",       // routing | direct
    track_opens:     true,
    headers_rot:     1,
    body_rot:        1,
    return_path:     "return@[domain]",
    static_domain:   "[domain]",
    from_names:      "",              // one per line
    subjects:        "",              // one per line
    header_tpl:      `MIME-Version: 1.0\nMessage-Id: <[a_7][n_6][n_3][a_3]@[domain]>\nFrom: [a_5] <[a_7]@[domain]>\nSubject: [p|server] [an_5]\nReply-To: reply_to@[domain]\nTo: [email]\nContent-Transfer-Encoding: [content_transfer_encoding]\nContent-Type: [content_type]; charset=[charset]\nDate: [mail_date]`,
    body_html:       `<p>Hello [first_name],</p>\n<p>Click here: <a href="{{offer.tracking_url}}">Claim Now</a></p>\n<div style="color:white;font-size:1px">[negative]</div>`,
    negative_content:"",
    offer_id:        "",
    network_id:      "",
    rcpt_rotation:   1,
    combination:     false,
    placeholders:    "",              // one per line
    direct_recipients: "",            // paste emails
    // filters
    filter_fresh:    false,
    filter_clean:    false,
    filter_openers:  false,
    filter_clickers: false,
    filter_leaders:  false,
    filter_unsubs:   false,
    filter_optouts:  false,
    filter_seeds:    false,
    random_dots:     false,
    nbre_dots:       2,
    test_after:      1000,
    test_email:      "",
  });

  // -- state
  const [script, setScript]       = useState(null);
  const [scriptMeta, setScriptMeta] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [launching, setLaunching] = useState(false);
  const [testing, setTesting]     = useState(false);
  const [generating, setGenerating] = useState(false);
  const [campaignId, setCampaignId] = useState(null);
  const [copied, setCopied]       = useState(false);

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

  const set = (k) => (v) => setCfg((c) => ({ ...c, [k]: v }));
  const setE = (k) => (e) => setCfg((c) => ({ ...c, [k]: e.target.value }));
  const toggleGroup = (id) => setSelGroups((p) => p.includes(id) ? p.filter((x) => x !== id) : [...p, id]);
  const toggleList  = (id) => setSelLists((p)  => p.includes(id) ? p.filter((x) => x !== id) : [...p, id]);

  const buildPayload = () => ({
    name: `Campaign ${new Date().toLocaleString()}`,
    header_template: cfg.header_tpl,
    body_html: cfg.body_html,
    negative_content: cfg.negative_content,
    links: [],
    offer_id: cfg.offer_id ? parseInt(cfg.offer_id) : null,
    group_ids: selGroups,
    list_ids: selLists,
    batch_size: parseInt(cfg.batch) || 1,
    sleep_between: Math.round((cfg.xdelay_ms || 0) / 1000),
    max_workers: parseInt(cfg.max_workers) || 5,
    send_mode: cfg.send_mode,
  });

  const saveCampaign = async () => {
    const { data } = await api.post("/campaigns", buildPayload());
    setCampaignId(data.id);
    return data.id;
  };

  const handleTest = async () => {
    if (!cfg.test_email) return;
    setTesting(true);
    try {
      let cid = campaignId;
      if (!cid) cid = await saveCampaign();
      const { data } = await api.post(`/campaigns/${cid}/preview`, { to_email: cfg.test_email });
      setTestResult(data);
    } catch (e) {
      setTestResult({ success: false, error: e.response?.data?.detail || "Error" });
    } finally {
      setTesting(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      let cid = campaignId;
      if (!cid) cid = await saveCampaign();
      const direct = cfg.direct_recipients
        ? cfg.direct_recipients.split("\n").map((s) => s.trim()).filter(Boolean)
        : [];
      const { data } = await api.post(`/campaigns/${cid}/generate-script`, { direct_recipients: direct });
      setScript(data.script);
      setScriptMeta(data);
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally {
      setGenerating(false);
    }
  };

  const handleLaunch = async () => {
    if (!confirm("Launch campaign now?")) return;
    setLaunching(true);
    try {
      let cid = campaignId;
      if (!cid) cid = await saveCampaign();
      await api.post(`/campaigns/${cid}/start`);
      alert("Campaign launched!");
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally {
      setLaunching(false);
    }
  };

  const copyScript = () => {
    navigator.clipboard.writeText(script);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-4 bg-gray-100 min-h-screen">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">Production Send Page</span>
        </div>
        <div className="flex items-center gap-2">
          <select value={cfg.send_mode} onChange={setE("send_mode")}
            className="border border-gray-300 rounded px-2 py-1 text-xs bg-white font-bold focus:outline-none">
            <option value="mx_direct">MX Direct (basic — no account)</option>
            <option value="smtp">SMTP (Gmail + proxy)</option>
            <option value="mx_proxy">MX via Proxy</option>
          </select>
          <button onClick={handleGenerate} disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gray-700 text-white rounded hover:bg-gray-800 disabled:opacity-50">
            <RefreshCw size={11} className={generating ? "animate-spin" : ""} />
            {generating ? "Generating…" : "Generate Script"}
          </button>
          <button onClick={handleLaunch} disabled={launching}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 font-bold">
            <SendIcon size={11} />
            {launching ? "Launching…" : "LAUNCH"}
          </button>
        </div>
      </div>

      {/* ── Row 1: Servers | Lists | Filter ── */}
      <div className="grid grid-cols-3 gap-2 mb-2">
        <Panel title={`Servers (${selGroups.length} Selected)`}>
          <div className="space-y-0.5 max-h-28 overflow-y-auto">
            {groups.length === 0 && <div className="text-xs text-gray-400 py-2 text-center">No groups</div>}
            {groups.map((g) => (
              <label key={g.id} className="flex items-center gap-1.5 cursor-pointer hover:bg-gray-50 px-1 py-0.5 rounded">
                <input type="checkbox" checked={selGroups.includes(g.id)} onChange={() => toggleGroup(g.id)} className="w-3 h-3" />
                <span className="text-xs text-gray-700">{g.name}</span>
                <span className="ml-auto text-[10px] text-gray-400">{g.active_accounts ?? 0}</span>
              </label>
            ))}
          </div>
        </Panel>

        <Panel title={`Email Lists (${selLists.length} Selected)`}>
          <div className="space-y-0.5 max-h-28 overflow-y-auto">
            {lists.length === 0 && <div className="text-xs text-gray-400 py-2 text-center">No lists</div>}
            {lists.map((l) => (
              <label key={l.id} className="flex items-center gap-1.5 cursor-pointer hover:bg-gray-50 px-1 py-0.5 rounded">
                <input type="checkbox" checked={selLists.includes(l.id)} onChange={() => toggleList(l.id)} className="w-3 h-3" />
                <span className="text-xs text-gray-700">{l.name}</span>
                <span className="ml-auto text-[10px] text-gray-400">{l.total_count?.toLocaleString()}</span>
              </label>
            ))}
          </div>
        </Panel>

        <Panel title="Filter Select">
          <div className="space-y-1.5">
            <Field label="Affiliate Network">
              <select value={cfg.network_id} onChange={setE("network_id")} className={sel}>
                <option value="">Select Affiliate Network…</option>
                {networks.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
              </select>
            </Field>
            <Field label="Offer">
              <select value={cfg.offer_id} onChange={setE("offer_id")} className={sel}>
                <option value="">Select Offer…</option>
                {offers.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </Field>
          </div>
        </Panel>
      </div>

      {/* ── Row 2: Content settings ── */}
      <div className="grid grid-cols-6 gap-2 mb-2">
        <SmallPanel>
          <Field label="Content Type">
            <select value={cfg.content_type} onChange={setE("content_type")} className={sel}>
              <option value="text/html">text/html</option>
              <option value="text/plain">text/plain</option>
            </select>
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Charset">
            <select value={cfg.charset} onChange={setE("charset")} className={sel}>
              <option>UTF-8</option>
              <option>ISO-8859-1</option>
              <option>Windows-1252</option>
            </select>
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Transfer Enc">
            <select value={cfg.transfer_enc} onChange={setE("transfer_enc")} className={sel}>
              <option value="7bit">7bit</option>
              <option value="quoted-printable">quoted-printable</option>
              <option value="base64">base64</option>
            </select>
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Process Type">
            <select value={cfg.process_type} onChange={setE("process_type")} className={sel}>
              <option value="batch">Batch</option>
              <option value="xdelay">Batch / X-Delay</option>
            </select>
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Link Type">
            <select value={cfg.link_type} onChange={setE("link_type")} className={sel}>
              <option value="routing">Routing</option>
              <option value="direct">Direct</option>
            </select>
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Track Opens">
            <div className="flex gap-1 items-center pt-0.5">
              <Toggle value={cfg.track_opens} onChange={set("track_opens")} />
            </div>
          </Field>
        </SmallPanel>
      </div>

      {/* ── Row 3: Numeric config ── */}
      <div className="grid grid-cols-7 gap-2 mb-2">
        <SmallPanel>
          <Field label="Batch">
            <input type="number" value={cfg.batch} onChange={setE("batch")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="X-Delay (Ms)">
            <input type="number" value={cfg.xdelay_ms} onChange={setE("xdelay_ms")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Max Workers">
            <input type="number" value={cfg.max_workers} onChange={setE("max_workers")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Test After">
            <input type="number" value={cfg.test_after} onChange={setE("test_after")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Headers Rotation">
            <input type="number" value={cfg.headers_rot} onChange={setE("headers_rot")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Body Rotation">
            <input type="number" value={cfg.body_rot} onChange={setE("body_rot")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Rcpt Rotation">
            <input type="number" value={cfg.rcpt_rotation} onChange={setE("rcpt_rotation")} className={inp} />
          </Field>
        </SmallPanel>
      </div>

      {/* ── Row 4: Return path + domain + combination ── */}
      <div className="grid grid-cols-4 gap-2 mb-2">
        <SmallPanel>
          <Field label="Return Path">
            <input value={cfg.return_path} onChange={setE("return_path")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Static Domain">
            <input value={cfg.static_domain} onChange={setE("static_domain")} className={inp} />
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Combination">
            <div className="flex gap-1 items-center pt-0.5">
              <Toggle value={cfg.combination} onChange={set("combination")} />
            </div>
          </Field>
        </SmallPanel>
        <SmallPanel>
          <Field label="Random Dots">
            <div className="flex items-center gap-2 pt-0.5">
              <Toggle value={cfg.random_dots} onChange={set("random_dots")} />
              <input type="number" value={cfg.nbre_dots} onChange={setE("nbre_dots")} className={`${inp} w-14`} placeholder="2" />
              <span className="text-[10px] text-gray-400">dots</span>
            </div>
          </Field>
        </SmallPanel>
      </div>

      {/* ── Row 5: FromNames | Subjects ── */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <Panel title="FromNames (one per line)">
          <textarea rows={3} value={cfg.from_names} onChange={setE("from_names")}
            placeholder={"John Smith\nJane Doe\nSupport Team"} className={ta} />
        </Panel>
        <Panel title="Subjects (one per line)">
          <textarea rows={3} value={cfg.subjects} onChange={setE("subjects")}
            placeholder={"Important: [first_name], check this\nRe: Your request [an_5]\nUrgent update for you"} className={ta} />
        </Panel>
      </div>

      {/* ── Row 6: Header Template | HTML Body ── */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <Panel title="Email Header Template">
          <textarea rows={9} value={cfg.header_tpl} onChange={setE("header_tpl")} className={ta} />
        </Panel>
        <Panel title="HTML Body">
          <textarea rows={9} value={cfg.body_html} onChange={setE("body_html")} className={ta} />
        </Panel>
      </div>

      {/* ── Row 7: Placeholders | Direct Recipients | Negative ── */}
      <div className="grid grid-cols-3 gap-2 mb-2">
        <Panel title="Placeholders (one per line)">
          <textarea rows={5} value={cfg.placeholders} onChange={setE("placeholders")}
            placeholder={"value1\nvalue2\nvalue3"} className={ta} />
        </Panel>
        <Panel title="Direct Recipients (paste emails)">
          <textarea rows={5} value={cfg.direct_recipients} onChange={setE("direct_recipients")}
            placeholder={"user@example.com\nother@domain.com"} className={ta} />
          <div className="text-[10px] text-gray-400 mt-1">
            {cfg.direct_recipients ? cfg.direct_recipients.split("\n").filter(Boolean).length : 0} lines
          </div>
        </Panel>
        <Panel title="Negative Content (spam bypass)">
          <textarea rows={5} value={cfg.negative_content} onChange={setE("negative_content")}
            placeholder="Hidden news text for spam filter bypass…" className={ta} />
        </Panel>
      </div>

      {/* ── Row 8: Email List Filters ── */}
      <Panel title="Email List Filters" className="mb-2">
        <div className="flex flex-wrap gap-4 py-1">
          {[
            ["fresh",    "Fresh"],
            ["clean",    "Clean"],
            ["openers",  "Openers"],
            ["clickers", "Clickers"],
            ["leaders",  "Leaders"],
            ["unsubs",   "Unsubs"],
            ["optouts",  "OptOuts"],
            ["seeds",    "Seeds"],
          ].map(([key, label]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="text-xs text-gray-600 w-16">{label}</span>
              <Toggle value={cfg[`filter_${key}`]} onChange={set(`filter_${key}`)} />
            </div>
          ))}
        </div>
      </Panel>

      {/* ── Row 9: Test + Statistics ── */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <Panel title="Test Email">
          <div className="flex gap-2 mb-2">
            <input type="email" value={cfg.test_email} onChange={setE("test_email")}
              placeholder="test@example.com"
              className={`${inp} flex-1`} />
            <button onClick={handleTest} disabled={!cfg.test_email || testing}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap">
              {testing ? "Sending…" : "Send Test"}
            </button>
          </div>
          {testResult && (
            <div className={`p-2 rounded text-xs ${testResult.success ? "bg-green-50 text-green-800 border border-green-100" : "bg-red-50 text-red-800 border border-red-100"}`}>
              {testResult.success ? `✓ Sent via ${testResult.mx}` : `✗ ${testResult.error}`}
            </div>
          )}
        </Panel>

        <Panel title="Send Statistics">
          {scriptMeta ? (
            <div className="grid grid-cols-3 gap-2">
              <Stat label="Clean Recipients" value={scriptMeta.final_count?.toLocaleString()} color="text-gray-900" />
              <Stat label="Filtered" value={scriptMeta.filtered_count} color="text-orange-600" />
              <Stat label="Active Accounts" value={scriptMeta.accounts_count} color="text-blue-600" />
            </div>
          ) : (
            <div className="text-xs text-gray-400 py-4 text-center">Generate script to see statistics</div>
          )}
        </Panel>
      </div>

      {/* ── Script Output ── */}
      {script && (
        <Panel title="Generated Python Script">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <button onClick={copyScript}
                className={`flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors ${copied ? "bg-green-100 text-green-700" : "bg-gray-100 hover:bg-gray-200 text-gray-600"}`}>
                {copied ? <CheckCircle size={11} /> : <Copy size={11} />}
                {copied ? "Copied!" : "Copy Script"}
              </button>
              <a href="https://console.cloud.google.com/cloudshelleditor" target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 text-blue-700 hover:bg-blue-100 rounded border border-blue-200">
                <ExternalLink size={11} /> Open Cloud Console
              </a>
            </div>
            <span className="text-[10px] text-gray-400">Paste into Cloud Shell → <code className="font-mono">python3 script.py</code></span>
          </div>
          <pre className="bg-gray-900 text-green-400 text-xs rounded p-3 overflow-auto max-h-72 font-mono">{script}</pre>
        </Panel>
      )}
    </div>
  );
}

// ── sub-components ────────────────────────────────────────────────────────────
function Panel({ title, children, className = "" }) {
  return (
    <div className={`bg-white border border-gray-200 rounded p-2 ${className}`}>
      {title && (
        <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-100 pb-1 mb-2">
          {title}
        </div>
      )}
      {children}
    </div>
  );
}

function SmallPanel({ children }) {
  return <div className="bg-white border border-gray-200 rounded p-2">{children}</div>;
}

function Stat({ label, value, color }) {
  return (
    <div className="text-center py-2">
      <div className={`text-xl font-bold ${color}`}>{value ?? "—"}</div>
      <div className="text-[10px] text-gray-400 mt-0.5">{label}</div>
    </div>
  );
}
