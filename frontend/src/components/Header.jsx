import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, X, Menu } from "lucide-react";

export default function Header() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [scrolled, setScrolled] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/?search=${encodeURIComponent(searchQuery.trim())}`);
      setSearchOpen(false);
      setSearchQuery("");
    }
  };

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-white/80 backdrop-blur-xl border-b border-neutral-200 shadow-sm"
          : "bg-white border-b border-neutral-100"
      }`}
    >
      {/* Top date bar */}
      <div className="border-b border-neutral-100">
        <div className="max-w-6xl mx-auto px-6 py-2 flex items-center justify-between">
          <span className="text-xs tracking-widest uppercase text-neutral-400 font-medium">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </span>
          <span className="hidden sm:block text-xs tracking-widest uppercase text-neutral-400 font-medium">
            Kurdistan Region
          </span>
        </div>
      </div>

      {/* Main header */}
      <div className="max-w-6xl mx-auto px-6 py-5">
        <div className="flex items-center justify-between">
          <Link to="/" className="group">
            <h1 className="text-2xl md:text-3xl font-serif font-bold tracking-tight text-neutral-900">
              Kurdistan
              <span className="text-accent-400"> Business</span>
              {" "}Insight
            </h1>
          </Link>

          <nav className="flex items-center gap-8">
            <Link
              to="/"
              className="hidden md:block text-sm font-medium text-neutral-500 hover:text-neutral-900 transition-colors"
            >
              Articles
            </Link>
            <Link
              to="/archive"
              className="hidden md:block text-sm font-medium text-neutral-500 hover:text-neutral-900 transition-colors"
            >
              Archive
            </Link>
            <button
              onClick={() => setSearchOpen(!searchOpen)}
              className="p-2 text-neutral-400 hover:text-neutral-900 transition-colors"
              aria-label="Search"
            >
              {searchOpen ? <X size={18} /> : <Search size={18} />}
            </button>
          </nav>
        </div>
      </div>

      {/* Search bar */}
      <AnimatePresence>
        {searchOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-neutral-100 overflow-hidden"
          >
            <div className="max-w-6xl mx-auto px-6 py-4">
              <form onSubmit={handleSearch} className="flex gap-3">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search articles..."
                  className="flex-1 px-4 py-2.5 rounded-lg bg-neutral-50 text-neutral-900 placeholder-neutral-400 border border-neutral-200 focus:outline-none focus:border-accent-400 focus:ring-1 focus:ring-accent-400/20 text-sm transition-all"
                  autoFocus
                />
                <button
                  type="submit"
                  className="px-6 py-2.5 bg-neutral-900 hover:bg-neutral-800 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Search
                </button>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
