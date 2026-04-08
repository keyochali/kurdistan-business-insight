import React, { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Plus, Trash2, RefreshCw, Download, Users, Building2, X,
  Loader2, CheckCircle2, AlertCircle, Play,
} from "lucide-react";

const ADMIN_PASSWORD = "789yesNo789";
const GITHUB_REPO = "keyochali/kurdistan-business-insight";
const GITHUB_WORKFLOW = "pipeline.yml";

function AdminLogin({ onLogin, error }) {
  const [key, setKey] = useState("");
  return (
    <div className="max-w-sm mx-auto mt-32 px-6">
      <h2 className="text-2xl font-serif font-bold text-neutral-900 mb-6">Admin Access</h2>
      {error && <p className="text-sm text-red-500 mb-4">{error}</p>}
      <input
        type="password"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder="Password"
        className="w-full px-4 py-3 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-accent-400 mb-4"
        onKeyDown={(e) => e.key === "Enter" && onLogin(key)}
      />
      <button
        onClick={() => onLogin(key)}
        className="w-full py-3 bg-neutral-900 text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
      >
        Enter
      </button>
    </div>
  );
}

function EntityTable({ title, icon: Icon, items, onAdd, onRemove }) {
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");

  const handleAdd = () => {
    if (name && url) {
      onAdd({ name, linkedin_url: url, id: Date.now(), is_active: true });
      setName("");
      setUrl("");
      setShowAdd(false);
    }
  };

  return (
    <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-100">
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-neutral-400" />
          <h3 className="text-sm font-semibold text-neutral-900">{title}</h3>
          <span className="text-xs text-neutral-400">({items.length})</span>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 transition-colors"
        >
          {showAdd ? <X size={12} /> : <Plus size={12} />}
          {showAdd ? "Cancel" : "Add"}
        </button>
      </div>

      {showAdd && (
        <div className="px-6 py-4 border-b border-neutral-100 bg-neutral-50 flex flex-col sm:flex-row gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name"
            className="flex-1 px-3 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-accent-400"
          />
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="LinkedIn URL"
            className="flex-1 px-3 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-accent-400"
          />
          <button onClick={handleAdd} className="px-4 py-2 bg-accent-400 text-white text-sm font-medium rounded-lg hover:bg-accent-500 transition-colors">
            Save
          </button>
        </div>
      )}

      <div className="max-h-80 overflow-y-auto">
        {items.map((item, i) => (
          <div key={item.id || i} className="flex items-center justify-between px-6 py-3 border-b border-neutral-50 last:border-0 hover:bg-neutral-50 transition-colors">
            <div>
              <p className="text-sm font-medium text-neutral-900">{item.name}</p>
              <p className="text-xs text-neutral-400 truncate max-w-xs">{item.linkedin_url}</p>
            </div>
            <button onClick={() => onRemove(item)} className="p-1.5 text-neutral-300 hover:text-red-500 transition-colors">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {items.length === 0 && <p className="px-6 py-6 text-sm text-neutral-400 text-center">No items yet</p>}
      </div>
    </div>
  );
}

// GitHub token input component
function GitHubTokenInput({ token, setToken }) {
  const [editing, setEditing] = useState(!token);
  const [val, setVal] = useState(token);

  const save = () => {
    localStorage.setItem("kbi_gh_token", val);
    setToken(val);
    setEditing(false);
  };

  if (!editing && token) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-green-600 font-medium">Token saved</span>
        <button onClick={() => setEditing(true)} className="text-xs text-neutral-400 hover:text-neutral-600">Change</button>
      </div>
    );
  }

  return (
    <div className="flex gap-2 mt-2">
      <input
        value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder="ghp_xxxxxxxxxxxx"
        type="password"
        className="flex-1 px-3 py-2 border border-neutral-200 rounded-lg text-xs font-mono focus:outline-none focus:border-accent-400"
      />
      <button onClick={save} className="px-3 py-2 bg-neutral-900 text-white text-xs rounded-lg hover:bg-neutral-800 transition-colors">
        Save
      </button>
    </div>
  );
}

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [ghToken, setGhToken] = useState(() => localStorage.getItem("kbi_gh_token") || "");
  const [profiles, setProfiles] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [pipelineStatus, setPipelineStatus] = useState(null); // null | 'triggering' | 'running' | 'completed' | 'failed'
  const [message, setMessage] = useState({ text: "", type: "info" });

  useEffect(() => {
    if (localStorage.getItem("kbi_admin_authed") === "true") setAuthed(true);
  }, []);

  // Load profiles/companies from data.json + localStorage overrides
  useEffect(() => {
    if (!authed) return;
    async function load() {
      try {
        const res = await fetch("/data.json");
        if (res.ok) {
          const data = await res.json();
          const localProfiles = JSON.parse(localStorage.getItem("kbi_local_profiles") || "[]");
          const localCompanies = JSON.parse(localStorage.getItem("kbi_local_companies") || "[]");
          const removedP = new Set(JSON.parse(localStorage.getItem("kbi_removed_profiles") || "[]"));
          const removedC = new Set(JSON.parse(localStorage.getItem("kbi_removed_companies") || "[]"));
          setProfiles([
            ...(data.profiles || []).filter((p) => !removedP.has(p.linkedin_url)),
            ...localProfiles,
          ]);
          setCompanies([
            ...(data.companies || []).filter((c) => !removedC.has(c.linkedin_url)),
            ...localCompanies,
          ]);
        }
      } catch {}
    }
    load();
  }, [authed]);

  const showMsg = (text, type = "info") => {
    setMessage({ text, type });
    setTimeout(() => setMessage({ text: "", type: "info" }), 6000);
  };

  const handleLogin = (key) => {
    if (key === ADMIN_PASSWORD) {
      localStorage.setItem("kbi_admin_authed", "true");
      setAuthed(true);
    } else {
      setLoginError("Incorrect password.");
    }
  };

  // Profile/Company CRUD via localStorage
  const handleAddProfile = (data) => {
    const local = JSON.parse(localStorage.getItem("kbi_local_profiles") || "[]");
    local.push(data);
    localStorage.setItem("kbi_local_profiles", JSON.stringify(local));
    setProfiles([...profiles, data]);
    showMsg(`Added: ${data.name}. Will be included in the next pipeline run.`, "success");
  };

  const handleRemoveProfile = (item) => {
    const local = JSON.parse(localStorage.getItem("kbi_local_profiles") || "[]");
    localStorage.setItem("kbi_local_profiles", JSON.stringify(local.filter((p) => p.linkedin_url !== item.linkedin_url)));
    const removed = JSON.parse(localStorage.getItem("kbi_removed_profiles") || "[]");
    if (!removed.includes(item.linkedin_url)) {
      removed.push(item.linkedin_url);
      localStorage.setItem("kbi_removed_profiles", JSON.stringify(removed));
    }
    setProfiles(profiles.filter((p) => p.linkedin_url !== item.linkedin_url));
    showMsg(`Removed: ${item.name}`, "success");
  };

  const handleAddCompany = (data) => {
    const local = JSON.parse(localStorage.getItem("kbi_local_companies") || "[]");
    local.push(data);
    localStorage.setItem("kbi_local_companies", JSON.stringify(local));
    setCompanies([...companies, data]);
    showMsg(`Added: ${data.name}. Will be included in the next pipeline run.`, "success");
  };

  const handleRemoveCompany = (item) => {
    const local = JSON.parse(localStorage.getItem("kbi_local_companies") || "[]");
    localStorage.setItem("kbi_local_companies", JSON.stringify(local.filter((c) => c.linkedin_url !== item.linkedin_url)));
    const removed = JSON.parse(localStorage.getItem("kbi_removed_companies") || "[]");
    if (!removed.includes(item.linkedin_url)) {
      removed.push(item.linkedin_url);
      localStorage.setItem("kbi_removed_companies", JSON.stringify(removed));
    }
    setCompanies(companies.filter((c) => c.linkedin_url !== item.linkedin_url));
    showMsg(`Removed: ${item.name}`, "success");
  };

  // Trigger GitHub Actions pipeline
  const triggerPipeline = async (mode) => {
    if (!ghToken) {
      showMsg("Please add your GitHub token first (needs 'repo' and 'workflow' permissions).", "error");
      return;
    }

    setPipelineStatus("triggering");
    try {
      const res = await fetch(
        `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${GITHUB_WORKFLOW}/dispatches`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${ghToken}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ref: "master",
            inputs: { mode },
          }),
        }
      );

      if (res.status === 204) {
        setPipelineStatus("running");
        showMsg(
          mode === "scrape"
            ? "Pipeline triggered! Scraping and generating articles. This takes ~20 min. The site will auto-update when done."
            : "Re-generation triggered! Rewriting articles from cached data. The site will auto-update when done.",
          "success"
        );
        // Poll for completion
        pollWorkflowStatus();
      } else {
        const err = await res.json().catch(() => ({}));
        setPipelineStatus("failed");
        showMsg(`Failed to trigger: ${err.message || res.statusText}`, "error");
      }
    } catch (e) {
      setPipelineStatus("failed");
      showMsg(`Error: ${e.message}`, "error");
    }
  };

  const pollWorkflowStatus = () => {
    let attempts = 0;
    const maxAttempts = 120; // 10 minutes of polling

    const poll = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(poll);
        setPipelineStatus(null);
        return;
      }

      try {
        const res = await fetch(
          `https://api.github.com/repos/${GITHUB_REPO}/actions/runs?per_page=1`,
          { headers: { Authorization: `Bearer ${ghToken}`, Accept: "application/vnd.github.v3+json" } }
        );
        if (res.ok) {
          const data = await res.json();
          const run = data.workflow_runs?.[0];
          if (run) {
            if (run.status === "completed") {
              clearInterval(poll);
              setPipelineStatus(run.conclusion === "success" ? "completed" : "failed");
              showMsg(
                run.conclusion === "success"
                  ? "Pipeline completed! Refresh the homepage to see new articles."
                  : `Pipeline finished with status: ${run.conclusion}`,
                run.conclusion === "success" ? "success" : "error"
              );
            }
          }
        }
      } catch {}
    }, 5000);
  };

  if (!authed) return <AdminLogin onLogin={handleLogin} error={loginError} />;

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="text-xs font-medium tracking-widest uppercase text-accent-500 mb-2">Admin</p>
            <h2 className="text-3xl font-serif font-bold text-neutral-900">Content Manager</h2>
          </div>
          <button onClick={() => { localStorage.removeItem("kbi_admin_authed"); setAuthed(false); }} className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors">
            Logout
          </button>
        </div>

        {/* Message */}
        {message.text && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mb-6 px-4 py-3 rounded-lg text-sm flex items-center gap-2 ${
              message.type === "success" ? "bg-green-50 border border-green-200 text-green-700" :
              message.type === "error" ? "bg-red-50 border border-red-200 text-red-700" :
              "bg-accent-50 border border-accent-200 text-accent-700"
            }`}
          >
            {message.type === "success" ? <CheckCircle2 size={14} /> : message.type === "error" ? <AlertCircle size={14} /> : null}
            {message.text}
          </motion.div>
        )}

        {/* GitHub token setup */}
        <div className="mb-6 p-4 bg-neutral-50 border border-neutral-200 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-widest text-neutral-400">
              GitHub Connection
            </span>
            <GitHubTokenInput token={ghToken} setToken={setGhToken} />
          </div>
          {!ghToken && (
            <p className="text-xs text-neutral-400 mt-2">
              Create a token at github.com/settings/tokens with <code className="px-1 py-0.5 bg-neutral-200 rounded text-[11px]">repo</code> scope.
            </p>
          )}
        </div>

        {/* Pipeline actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
          <button
            onClick={() => triggerPipeline("scrape")}
            disabled={pipelineStatus === "running" || pipelineStatus === "triggering"}
            className="flex items-center gap-3 px-6 py-5 bg-neutral-900 text-white rounded-xl hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-left"
          >
            {pipelineStatus === "running" || pipelineStatus === "triggering" ? (
              <Loader2 size={20} className="animate-spin flex-shrink-0" />
            ) : pipelineStatus === "completed" ? (
              <CheckCircle2 size={20} className="flex-shrink-0 text-green-400" />
            ) : (
              <Download size={20} className="flex-shrink-0" />
            )}
            <div>
              <p className="text-sm font-semibold">Scrape & Generate</p>
              <p className="text-xs text-neutral-400">
                {pipelineStatus === "running" ? "Running... (~20 min)" :
                 pipelineStatus === "triggering" ? "Triggering..." :
                 pipelineStatus === "completed" ? "Done! Refresh homepage." :
                 "Fetch new posts and create articles"}
              </p>
            </div>
          </button>

          <button
            onClick={() => triggerPipeline("regenerate")}
            disabled={pipelineStatus === "running" || pipelineStatus === "triggering"}
            className="flex items-center gap-3 px-6 py-5 bg-white border border-neutral-200 text-neutral-900 rounded-xl hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-left"
          >
            {pipelineStatus === "running" || pipelineStatus === "triggering" ? (
              <Loader2 size={20} className="animate-spin flex-shrink-0" />
            ) : (
              <RefreshCw size={20} className="flex-shrink-0" />
            )}
            <div>
              <p className="text-sm font-semibold">Re-generate</p>
              <p className="text-xs text-neutral-400">Rewrite articles from cached posts</p>
            </div>
          </button>
        </div>

        {/* Entity management */}
        <div className="space-y-6">
          <EntityTable title="Tracked Profiles" icon={Users} items={profiles} onAdd={handleAddProfile} onRemove={handleRemoveProfile} />
          <EntityTable title="Tracked Companies" icon={Building2} items={companies} onAdd={handleAddCompany} onRemove={handleRemoveCompany} />
        </div>

        <p className="text-xs text-neutral-400 mt-8 text-center">
          Profile/company changes are saved locally. Pipeline runs via GitHub Actions — articles auto-deploy to the site.
        </p>
      </motion.div>
    </div>
  );
}
