import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, X, Menu } from "lucide-react";

export default function Header() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [scrolled, setScrolled] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [navigate]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/?search=${encodeURIComponent(searchQuery.trim())}`);
      setSearchOpen(false);
      setMobileMenuOpen(false);
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
      {/* Top date bar — hidden on mobile */}
      <div className="hidden sm:block border-b border-neutral-100">
        <div className="max-w-6xl mx-auto px-6 py-2 flex items-center justify-between">
          <span className="text-xs tracking-widest uppercase text-neutral-400 font-medium">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </span>
          <span className="text-xs tracking-widest uppercase text-neutral-400 font-medium">
            Kurdistan Region
          </span>
        </div>
      </div>

      {/* Main header */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 sm:py-5">
        <div className="flex items-center justify-between">
          <Link to="/" className="group" onClick={() => setMobileMenuOpen(false)}>
            <h1 className="text-xl sm:text-2xl md:text-3xl font-serif font-bold tracking-tight text-neutral-900">
              Kurdistan
              <span className="text-accent-400"> Business</span>
              {" "}Insight
            </h1>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8">
            <Link to="/" className="text-sm font-medium text-neutral-500 hover:text-neutral-900 transition-colors">
              Articles
            </Link>
            <Link to="/archive" className="text-sm font-medium text-neutral-500 hover:text-neutral-900 transition-colors">
              Archive
            </Link>
            <button
              onClick={() => { setSearchOpen(!searchOpen); setMobileMenuOpen(false); }}
              className="p-2 text-neutral-400 hover:text-neutral-900 transition-colors"
              aria-label="Search"
            >
              {searchOpen ? <X size={18} /> : <Search size={18} />}
            </button>
          </nav>

          {/* Mobile controls */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={() => { setSearchOpen(!searchOpen); setMobileMenuOpen(false); }}
              className="p-2 text-neutral-400 hover:text-neutral-900 transition-colors"
              aria-label="Search"
            >
              {searchOpen ? <X size={18} /> : <Search size={18} />}
            </button>
            <button
              onClick={() => { setMobileMenuOpen(!mobileMenuOpen); setSearchOpen(false); }}
              className="p-2 text-neutral-400 hover:text-neutral-900 transition-colors"
              aria-label="Menu"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
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
            <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
              <form onSubmit={handleSearch} className="flex gap-2 sm:gap-3">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search articles..."
                  className="flex-1 px-3 sm:px-4 py-2.5 rounded-lg bg-neutral-50 text-neutral-900 placeholder-neutral-400 border border-neutral-200 focus:outline-none focus:border-accent-400 focus:ring-1 focus:ring-accent-400/20 text-sm transition-all"
                  autoFocus
                />
                <button
                  type="submit"
                  className="px-4 sm:px-6 py-2.5 bg-neutral-900 hover:bg-neutral-800 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Search
                </button>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden border-t border-neutral-100 overflow-hidden bg-white"
          >
            <nav className="max-w-6xl mx-auto px-4 py-4 space-y-1">
              <Link
                to="/"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-4 py-3 text-sm font-medium text-neutral-700 hover:bg-neutral-50 rounded-lg transition-colors"
              >
                Articles
              </Link>
              <Link
                to="/archive"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-4 py-3 text-sm font-medium text-neutral-700 hover:bg-neutral-50 rounded-lg transition-colors"
              >
                Archive
              </Link>
              <div className="pt-2 px-4 text-xs text-neutral-400">
                {new Date().toLocaleDateString("en-US", {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
