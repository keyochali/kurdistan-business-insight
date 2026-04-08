import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus, Trash2, RefreshCw, Download, Users, Building2, X,
  Loader2, CheckCircle2, AlertCircle, Circle, Clock, ExternalLink,
} from "lucide-react";

const ADMIN_PASSWORD = "789yesNo789";

// Map GitHub Actions step names to user-friendly labels
const STEP_LABELS = {
  "Set up job": "Preparing environment",
  "Run actions/checkout@v4": "Loading project",
  "Set up Python": "Setting up Python",
  "Install dependencies": "Installing packages",
  "Set up environment": "Configuring environment",
  "Initialize database": "Initializing database",
  "Seed profiles and companies": "Loading profiles & companies",
  "Run pipeline": "Running pipeline (scrape → label → write → publish)",
  "Inject inline images": "Adding images to articles",
  "Fix image paths": "Fixing image paths",
  "Export data.json for frontend": "Exporting articles for website",
  "Generate SEO files": "Generating SEO files",
  "Commit and push updated data": "Publishing to website",
  "Post Run actions/checkout@v4": "Cleaning up",
  "Complete job": "Done",
};

function friendlyStepName(name) {
  return STEP_LABELS[name] || name;
}

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

// ── Progress Tracker Component ──
function PipelineProgress({ status, onClose }) {
  if (!status || status.status === "idle" || status.status === "unknown") return null;

  const isRunning = status.status === "in_progress" || status.status === "queued";
  const isComplete = status.status === "completed";
  const isSuccess = status.conclusion === "success";
  const progress = status.progress || { total: 0, completed: 0, percent: 0, current_step: null };

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`mb-8 border rounded-xl overflow-hidden ${
        isComplete
          ? isSuccess ? "border-green-200 bg-green-50/50" : "border-red-200 bg-red-50/50"
          : "border-accent-200 bg-accent-50/30"
      }`}
    >
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isRunning ? (
            <Loader2 size={18} className="animate-spin text-accent-500" />
          ) : isSuccess ? (
            <CheckCircle2 size={18} className="text-green-500" />
          ) : (
            <AlertCircle size={18} className="text-red-500" />
          )}
          <div>
            <p className="text-sm font-semibold text-neutral-900">
              {isRunning ? "Pipeline Running" : isSuccess ? "Pipeline Complete" : "Pipeline Failed"}
            </p>
            <div className="flex items-center gap-3 text-xs text-neutral-400 mt-0.5">
              <span className="flex items-center gap-1">
                <Clock size={10} />
                {formatElapsed(status.elapsed_seconds || 0)}
              </span>
              {progress.total > 0 && (
                <span>{progress.completed}/{progress.total} steps</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {status.url && (
            <a
              href={status.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-neutral-400 hover:text-neutral-600 flex items-center gap-1 transition-colors"
            >
              Logs <ExternalLink size={10} />
            </a>
          )}
          {isComplete && (
            <button onClick={onClose} className="p-1 text-neutral-400 hover:text-neutral-600 transition-colors">
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {isRunning && progress.total > 0 && (
        <div className="px-5 pb-1">
          <div className="w-full h-1.5 bg-neutral-200 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-accent-400 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progress.percent}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      )}

      {/* Steps list */}
      {status.steps && status.steps.length > 0 && (
        <div className="px-5 py-3 border-t border-neutral-100/50">
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {status.steps
              .filter((s) => s.name !== "Set up job" && s.name !== "Complete job" && !s.name.startsWith("Post "))
              .map((step, i) => {
                const isCurrent = step.status === "in_progress";
                const isDone = step.status === "completed" && step.conclusion === "success";
                const isFailed = step.conclusion === "failure";
                const isWaiting = step.status === "queued";

                return (
                  <div
                    key={i}
                    className={`flex items-center gap-2.5 py-1.5 px-2 rounded-lg text-sm transition-colors ${
                      isCurrent ? "bg-accent-100/50" : ""
                    }`}
                  >
                    {/* Status icon */}
                    {isCurrent ? (
                      <Loader2 size={13} className="animate-spin text-accent-500 flex-shrink-0" />
                    ) : isDone ? (
                      <CheckCircle2 size={13} className="text-green-500 flex-shrink-0" />
                    ) : isFailed ? (
                      <AlertCircle size={13} className="text-red-500 flex-shrink-0" />
                    ) : (
                      <Circle size={13} className="text-neutral-300 flex-shrink-0" />
                    )}

                    {/* Label */}
                    <span
                      className={
                        isCurrent ? "font-medium text-neutral-900" :
                        isDone ? "text-neutral-500" :
                        isFailed ? "text-red-600 font-medium" :
                        "text-neutral-400"
                      }
                    >
                      {friendlyStepName(step.name)}
                    </span>

                    {/* Current indicator */}
                    {isCurrent && (
                      <span className="ml-auto text-[10px] text-accent-500 font-medium tracking-wider uppercase">
                        In progress
                      </span>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Current step highlight for running */}
      {isRunning && progress.current_step && !status.steps?.length && (
        <div className="px-5 pb-4">
          <p className="text-xs text-neutral-500">
            Current: <span className="font-medium text-neutral-700">{friendlyStepName(progress.current_step)}</span>
          </p>
        </div>
      )}

      {/* Completion message */}
      {isComplete && isSuccess && (
        <div className="px-5 pb-4">
          <p className="text-sm text-green-700">
            Articles updated successfully. Refresh the homepage to see them.
          </p>
        </div>
      )}
    </motion.div>
  );
}

// ── Login ──
function AdminLogin({ onLogin, error }) {
  const [key, setKey] = useState("");
  return (
    <div className="max-w-sm mx-auto mt-32 px-6">
      <h2 className="text-2xl font-serif font-bold text-neutral-900 mb-6">Admin Access</h2>
      {error && <p className="text-sm text-red-500 mb-4">{error}</p>}
      <input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Password"
        className="w-full px-4 py-3 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-accent-400 mb-4"
        onKeyDown={(e) => e.key === "Enter" && onLogin(key)} />
      <button onClick={() => onLogin(key)}
        className="w-full py-3 bg-neutral-900 text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors">
        Enter
      </button>
    </div>
  );
}

// ── Entity Table ──
function EntityTable({ title, icon: Icon, items, onAdd, onRemove }) {
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");

  const handleAdd = () => {
    if (name && url) {
      onAdd({ name, linkedin_url: url, id: Date.now(), is_active: true });
      setName(""); setUrl(""); setShowAdd(false);
    }
  };

  return (
    <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-neutral-100">
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-neutral-400" />
          <h3 className="text-sm font-semibold text-neutral-900">{title}</h3>
          <span className="text-xs text-neutral-400">({items.length})</span>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 transition-colors">
          {showAdd ? <X size={12} /> : <Plus size={12} />}
          {showAdd ? "Cancel" : "Add"}
        </button>
      </div>

      {showAdd && (
        <div className="px-4 sm:px-6 py-4 border-b border-neutral-100 bg-neutral-50 flex flex-col sm:flex-row gap-3">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name"
            className="flex-1 px-3 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-accent-400" />
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="LinkedIn URL"
            className="flex-1 px-3 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:border-accent-400" />
          <button onClick={handleAdd}
            className="px-4 py-2 bg-accent-400 text-white text-sm font-medium rounded-lg hover:bg-accent-500 transition-colors">Save</button>
        </div>
      )}

      <div className="max-h-80 overflow-y-auto">
        {items.map((item, i) => (
          <div key={item.id || i}
            className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-neutral-50 last:border-0 hover:bg-neutral-50 transition-colors">
            <div className="min-w-0">
              <p className="text-sm font-medium text-neutral-900">{item.name}</p>
              <p className="text-xs text-neutral-400 truncate">{item.linkedin_url}</p>
            </div>
            <button onClick={() => onRemove(item)} className="p-1.5 ml-2 text-neutral-300 hover:text-red-500 transition-colors flex-shrink-0">
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {items.length === 0 && <p className="px-6 py-6 text-sm text-neutral-400 text-center">No items yet</p>}
      </div>
    </div>
  );
}

// ── Main Admin Page ──
export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [profiles, setProfiles] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [pipelineActive, setPipelineActive] = useState(false);
  const [pipelineData, setPipelineData] = useState(null);
  const [showProgress, setShowProgress] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "info" });

  useEffect(() => {
    if (localStorage.getItem("kbi_admin_authed") === "true") setAuthed(true);
  }, []);

  // Load profiles/companies from Supabase (source of truth)
  useEffect(() => {
    if (!authed) return;
    (async () => {
      try {
        const [p, c] = await Promise.all([fetchProfiles(), fetchCompanies()]);
        setProfiles(p);
        setCompanies(c);
      } catch (e) {
        showMsg("Failed to load from database", "error");
      }
    })();
  }, [authed]);

  // Check if a pipeline is already running on page load
  useEffect(() => {
    if (!authed) return;
    (async () => {
      try {
        const res = await fetch("/api/pipeline-status");
        if (res.ok) {
          const data = await res.json();
          if (data.status === "in_progress" || data.status === "queued") {
            setPipelineActive(true);
            setPipelineData(data);
            setShowProgress(true);
          }
        }
      } catch {}
    })();
  }, [authed]);

  // Poll pipeline status when active
  useEffect(() => {
    if (!pipelineActive) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/pipeline-status");
        if (res.ok) {
          const data = await res.json();
          setPipelineData(data);
          if (data.status === "completed") {
            setPipelineActive(false);
          }
        }
      } catch {}
    }, 5000);
    return () => clearInterval(interval);
  }, [pipelineActive]);

  const showMsg = (text, type = "info") => {
    setMessage({ text, type });
    setTimeout(() => setMessage({ text: "", type: "info" }), 6000);
  };

  const handleLogin = (key) => {
    if (key === ADMIN_PASSWORD) {
      localStorage.setItem("kbi_admin_authed", "true"); setAuthed(true);
    } else { setLoginError("Incorrect password."); }
  };

  // Persist changes to GitHub repo via serverless function
  const [saving, setSaving] = useState(false);

  const dbAction = async (action, table, data = null, id = null) => {
    setSaving(true);
    try {
      const res = await fetch("/api/update-entities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: ADMIN_PASSWORD, action, table, data, id }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Failed");
      return result;
    } catch (e) {
      showMsg(e.message, "error");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleAddProfile = async (data) => {
    const result = await dbAction("add", "linkedin_profiles", { name: data.name, linkedin_url: data.linkedin_url, is_active: true });
    if (result?.success) {
      const added = result.data?.[0] || { ...data, id: Date.now() };
      setProfiles([...profiles, added]);
      showMsg(`Added: ${data.name}`, "success");
    }
  };
  const handleRemoveProfile = async (item) => {
    const result = await dbAction("remove", "linkedin_profiles", null, item.id);
    if (result?.success) {
      setProfiles(profiles.filter((p) => p.id !== item.id));
      showMsg(`Removed: ${item.name}`, "success");
    }
  };
  const handleAddCompany = async (data) => {
    const result = await dbAction("add", "linkedin_companies", { name: data.name, linkedin_url: data.linkedin_url, is_active: true });
    if (result?.success) {
      const added = result.data?.[0] || { ...data, id: Date.now() };
      setCompanies([...companies, added]);
      showMsg(`Added: ${data.name}`, "success");
    }
  };
  const handleRemoveCompany = async (item) => {
    const result = await dbAction("remove", "linkedin_companies", null, item.id);
    if (result?.success) {
      setCompanies(companies.filter((c) => c.id !== item.id));
      showMsg(`Removed: ${item.name}`, "success");
    }
  };

  const triggerPipeline = async (mode) => {
    setPipelineActive(true);
    setShowProgress(true);
    setPipelineData({ status: "queued", steps: [], progress: { total: 0, completed: 0, percent: 0 }, elapsed_seconds: 0 });

    try {
      const res = await fetch("/api/trigger-pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: ADMIN_PASSWORD, mode }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPipelineActive(false);
        showMsg(data.error || "Failed to trigger", "error");
      }
    } catch (e) {
      setPipelineActive(false);
      showMsg(`Error: ${e.message}`, "error");
    }
  };

  if (!authed) return <AdminLogin onLogin={handleLogin} error={loginError} />;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="text-xs font-medium tracking-widest uppercase text-accent-500 mb-2">Admin</p>
            <h2 className="text-2xl sm:text-3xl font-serif font-bold text-neutral-900">Content Manager</h2>
          </div>
          <button onClick={() => { localStorage.removeItem("kbi_admin_authed"); setAuthed(false); }}
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors">Logout</button>
        </div>

        {/* Message */}
        <AnimatePresence>
          {message.text && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className={`mb-6 px-4 py-3 rounded-lg text-sm flex items-center gap-2 ${
                message.type === "success" ? "bg-green-50 border border-green-200 text-green-700" :
                message.type === "error" ? "bg-red-50 border border-red-200 text-red-700" :
                "bg-accent-50 border border-accent-200 text-accent-700"
              }`}>
              {message.type === "success" ? <CheckCircle2 size={14} /> : message.type === "error" ? <AlertCircle size={14} /> : null}
              {message.text}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Pipeline progress tracker */}
        {showProgress && pipelineData && (
          <PipelineProgress status={pipelineData} onClose={() => setShowProgress(false)} />
        )}

        {/* Pipeline actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
          <button
            onClick={() => triggerPipeline("scrape")}
            disabled={pipelineActive}
            className="flex items-center gap-3 px-5 sm:px-6 py-5 bg-neutral-900 text-white rounded-xl hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-left"
          >
            {pipelineActive ? (
              <Loader2 size={20} className="animate-spin flex-shrink-0" />
            ) : (
              <Download size={20} className="flex-shrink-0" />
            )}
            <div>
              <p className="text-sm font-semibold">Scrape & Generate</p>
              <p className="text-xs text-neutral-400">Fetch new posts and create articles</p>
            </div>
          </button>

          <button
            onClick={() => triggerPipeline("regenerate")}
            disabled={pipelineActive}
            className="flex items-center gap-3 px-5 sm:px-6 py-5 bg-white border border-neutral-200 text-neutral-900 rounded-xl hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-left"
          >
            <RefreshCw size={20} className="flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold">Re-generate</p>
              <p className="text-xs text-neutral-400">Rewrite from cached posts</p>
            </div>
          </button>
        </div>

        {/* Saving indicator */}
        {saving && (
          <div className="mb-4 flex items-center gap-2 text-xs text-neutral-400">
            <Loader2 size={12} className="animate-spin" /> Saving to server...
          </div>
        )}

        {/* Entity management */}
        <div className="space-y-6">
          <EntityTable title="Tracked Profiles" icon={Users} items={profiles} onAdd={handleAddProfile} onRemove={handleRemoveProfile} />
          <EntityTable title="Tracked Companies" icon={Building2} items={companies} onAdd={handleAddCompany} onRemove={handleRemoveCompany} />
        </div>
      </motion.div>
    </div>
  );
}
