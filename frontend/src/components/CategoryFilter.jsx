import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Check } from "lucide-react";

export function getCategoryColor(category) {
  return "bg-neutral-900 text-white";
}

export function getCategoryBadgeStyle(category, minimal = false) {
  if (minimal) return "bg-neutral-100 text-neutral-600";
  return "bg-accent-400/10 text-accent-700 border border-accent-400/20";
}

export default function CategoryFilter({ categories, selected, onSelect }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on click outside
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectedLabel = selected
    ? categories.find((c) => c.category === selected)?.category || selected
    : "All Categories";

  const selectedCount = selected
    ? categories.find((c) => c.category === selected)?.count
    : categories.reduce((sum, c) => sum + c.count, 0);

  return (
    <div ref={ref} className="relative inline-block w-full sm:w-auto">
      {/* Trigger button */}
      <button
        onClick={() => setOpen(!open)}
        className={`w-full sm:w-auto flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl border text-sm font-medium transition-all duration-200 ${
          open
            ? "border-neutral-300 bg-white shadow-lg shadow-neutral-200/50"
            : "border-neutral-200 bg-white hover:border-neutral-300"
        }`}
      >
        <div className="flex items-center gap-2.5">
          {selected && (
            <span className="w-2 h-2 rounded-full bg-accent-400" />
          )}
          <span className="text-neutral-900">{selectedLabel}</span>
          <span className="text-neutral-300 text-xs">{selectedCount}</span>
        </div>
        <ChevronDown
          size={14}
          className={`text-neutral-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute z-40 mt-2 left-0 right-0 sm:right-auto sm:min-w-[260px] bg-white border border-neutral-200 rounded-xl shadow-xl shadow-neutral-200/50 overflow-hidden"
          >
            <div className="max-h-[50vh] overflow-y-auto py-1">
              {/* All option */}
              <button
                onClick={() => { onSelect(null); setOpen(false); }}
                className="w-full flex items-center justify-between px-4 py-2.5 text-sm hover:bg-neutral-50 transition-colors"
              >
                <span className={!selected ? "font-semibold text-neutral-900" : "text-neutral-600"}>
                  All Categories
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-neutral-300">
                    {categories.reduce((sum, c) => sum + c.count, 0)}
                  </span>
                  {!selected && <Check size={14} className="text-accent-500" />}
                </div>
              </button>

              <div className="mx-3 border-t border-neutral-100 my-1" />

              {/* Category options */}
              {categories.map((cat) => (
                <button
                  key={cat.category}
                  onClick={() => { onSelect(cat.category); setOpen(false); }}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-sm hover:bg-neutral-50 transition-colors group"
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`w-1.5 h-1.5 rounded-full transition-colors ${
                        selected === cat.category ? "bg-accent-400" : "bg-neutral-200 group-hover:bg-neutral-400"
                      }`}
                    />
                    <span
                      className={
                        selected === cat.category
                          ? "font-semibold text-neutral-900"
                          : "text-neutral-600"
                      }
                    >
                      {cat.category}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-neutral-300">{cat.count}</span>
                    {selected === cat.category && <Check size={14} className="text-accent-500" />}
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
