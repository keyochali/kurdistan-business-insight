import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Plus, Trash2, RefreshCw, Download, Users, Building2, Newspaper, X } from "lucide-react";
import { fetchProfiles, fetchCompanies } from "../utils/api";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

function AdminLogin({ onLogin }) {
  const [key, setKey] = useState("");
  return (
    <div className="max-w-sm mx-auto mt-32 px-6">
      <h2 className="text-2xl font-serif font-bold text-neutral-900 mb-6">Admin Access</h2>
      <input
        type="password"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder="Admin key"
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
      onAdd({ name, linkedin_url: url });
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
        <div className="px-6 py-4 border-b border-neutral-100 bg-neutral-50 flex gap-3">
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
          <button
            onClick={handleAdd}
            className="px-4 py-2 bg-accent-400 text-white text-sm font-medium rounded-lg hover:bg-accent-500 transition-colors"
          >
            Save
          </button>
        </div>
      )}

      <div className="max-h-80 overflow-y-auto">
        {items.map((item, i) => (
          <div
            key={item.id || i}
            className="flex items-center justify-between px-6 py-3 border-b border-neutral-50 last:border-0 hover:bg-neutral-50 transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-neutral-900">{item.name}</p>
              <p className="text-xs text-neutral-400 truncate max-w-xs">
                {item.linkedin_url}
              </p>
            </div>
            <button
              onClick={() => onRemove(item)}
              className="p-1.5 text-neutral-300 hover:text-red-500 transition-colors"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [adminKey, setAdminKey] = useState("");
  const [profiles, setProfiles] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const saved = localStorage.getItem("kbi_admin_key");
    if (saved) {
      setAdminKey(saved);
      setAuthed(true);
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    async function load() {
      const [p, c] = await Promise.all([fetchProfiles(), fetchCompanies()]);
      setProfiles(p);
      setCompanies(c);
    }
    load();
  }, [authed]);

  const handleLogin = (key) => {
    localStorage.setItem("kbi_admin_key", key);
    setAdminKey(key);
    setAuthed(true);
  };

  const showMsg = (msg) => {
    setMessage(msg);
    setTimeout(() => setMessage(""), 4000);
  };

  const adminFetch = async (path, opts = {}) => {
    try {
      const res = await fetch(`${API}${path}`, {
        ...opts,
        headers: { "X-Admin-Key": adminKey, "Content-Type": "application/json", ...opts.headers },
      });
      return res;
    } catch (e) {
      showMsg("Backend not reachable. Make sure the local server is running.");
      return null;
    }
  };

  const handleAddProfile = async (data) => {
    const res = await adminFetch("/api/admin/profiles", {
      method: "POST",
      body: JSON.stringify(data),
    });
    if (res?.ok) {
      setProfiles([...profiles, { ...data, id: Date.now() }]);
      showMsg(`Added profile: ${data.name}`);
    } else {
      showMsg("Failed — is the backend running?");
    }
  };

  const handleRemoveProfile = async (item) => {
    const res = await adminFetch(`/api/admin/profiles/${item.id}`, { method: "DELETE" });
    if (res?.ok) {
      setProfiles(profiles.filter((p) => p.id !== item.id));
      showMsg(`Removed: ${item.name}`);
    }
  };

  const handleAddCompany = async (data) => {
    const res = await adminFetch("/api/admin/companies", {
      method: "POST",
      body: JSON.stringify(data),
    });
    if (res?.ok) {
      setCompanies([...companies, { ...data, id: Date.now() }]);
      showMsg(`Added company: ${data.name}`);
    } else {
      showMsg("Failed — is the backend running?");
    }
  };

  const handleRemoveCompany = async (item) => {
    const res = await adminFetch(`/api/admin/companies/${item.id}`, { method: "DELETE" });
    if (res?.ok) {
      setCompanies(companies.filter((c) => c.id !== item.id));
      showMsg(`Removed: ${item.name}`);
    }
  };

  const handleScrape = async () => {
    setPipelineStatus("scraping");
    showMsg("Scraping started...");
    const res = await adminFetch("/api/admin/pipeline/run", { method: "POST" });
    if (res?.ok) {
      showMsg("Pipeline triggered! Check logs for progress.");
    } else {
      showMsg("Failed to trigger pipeline. Is the backend running?");
    }
    setPipelineStatus(null);
  };

  const handleRegenerate = async () => {
    setPipelineStatus("regenerating");
    showMsg("Regenerating articles...");
    const res = await adminFetch("/api/admin/pipeline/run?regenerate=true", { method: "POST" });
    if (res?.ok) {
      showMsg("Regeneration triggered! Check logs for progress.");
    } else {
      showMsg("Failed. Is the backend running?");
    }
    setPipelineStatus(null);
  };

  if (!authed) return <AdminLogin onLogin={handleLogin} />;

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="text-xs font-medium tracking-widest uppercase text-accent-500 mb-2">
              Admin
            </p>
            <h2 className="text-3xl font-serif font-bold text-neutral-900">
              Content Manager
            </h2>
          </div>
          <button
            onClick={() => {
              localStorage.removeItem("kbi_admin_key");
              setAuthed(false);
            }}
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
          >
            Logout
          </button>
        </div>

        {/* Status message */}
        {message && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 px-4 py-3 bg-accent-50 border border-accent-200 rounded-lg text-sm text-accent-700"
          >
            {message}
          </motion.div>
        )}

        {/* Pipeline actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
          <button
            onClick={handleScrape}
            disabled={pipelineStatus !== null}
            className="flex items-center justify-center gap-3 px-6 py-4 bg-neutral-900 text-white rounded-xl hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <Download size={18} className={pipelineStatus === "scraping" ? "animate-bounce" : ""} />
            <div className="text-left">
              <p className="text-sm font-semibold">Scrape & Generate</p>
              <p className="text-xs text-neutral-400">Fetch new posts and create articles</p>
            </div>
          </button>

          <button
            onClick={handleRegenerate}
            disabled={pipelineStatus !== null}
            className="flex items-center justify-center gap-3 px-6 py-4 bg-white border border-neutral-200 text-neutral-900 rounded-xl hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            <RefreshCw size={18} className={pipelineStatus === "regenerating" ? "animate-spin" : ""} />
            <div className="text-left">
              <p className="text-sm font-semibold">Re-generate</p>
              <p className="text-xs text-neutral-400">Rewrite today's articles from cached posts</p>
            </div>
          </button>
        </div>

        {/* Entity management */}
        <div className="space-y-6">
          <EntityTable
            title="Tracked Profiles"
            icon={Users}
            items={profiles}
            onAdd={handleAddProfile}
            onRemove={handleRemoveProfile}
          />
          <EntityTable
            title="Tracked Companies"
            icon={Building2}
            items={companies}
            onAdd={handleAddCompany}
            onRemove={handleRemoveCompany}
          />
        </div>
      </motion.div>
    </div>
  );
}
