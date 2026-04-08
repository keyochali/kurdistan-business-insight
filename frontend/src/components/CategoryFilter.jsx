import React from "react";
import { motion } from "framer-motion";

const CATEGORY_COLORS = {
  Technology: "bg-neutral-900 text-white",
  Finance: "bg-neutral-900 text-white",
  Entrepreneurship: "bg-neutral-900 text-white",
  Marketing: "bg-neutral-900 text-white",
  "HR & Talent": "bg-neutral-900 text-white",
  Investment: "bg-neutral-900 text-white",
  "Real Estate": "bg-neutral-900 text-white",
  Education: "bg-neutral-900 text-white",
  Healthcare: "bg-neutral-900 text-white",
  Telecom: "bg-neutral-900 text-white",
  "E-commerce": "bg-neutral-900 text-white",
  Infrastructure: "bg-neutral-900 text-white",
  "Product Launch": "bg-neutral-900 text-white",
  "Company Update": "bg-neutral-900 text-white",
  "Opinion & Thought Leadership": "bg-neutral-900 text-white",
  Events: "bg-neutral-900 text-white",
  Partnerships: "bg-neutral-900 text-white",
};

export function getCategoryColor(category) {
  return CATEGORY_COLORS[category] || "bg-neutral-900 text-white";
}

export function getCategoryBadgeStyle(category, minimal = false) {
  if (minimal) {
    return "bg-neutral-100 text-neutral-600";
  }
  return "bg-accent-400/10 text-accent-700 border border-accent-400/20";
}

export default function CategoryFilter({ categories, selected, onSelect }) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onSelect(null)}
        className={`px-4 py-1.5 text-xs font-medium rounded-full transition-all duration-200 ${
          !selected
            ? "bg-neutral-900 text-white"
            : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200 hover:text-neutral-700"
        }`}
      >
        All
      </button>
      {categories.map((cat, i) => (
        <motion.button
          key={cat.category}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.03 }}
          onClick={() => onSelect(cat.category)}
          className={`px-4 py-1.5 text-xs font-medium rounded-full transition-all duration-200 ${
            selected === cat.category
              ? "bg-neutral-900 text-white"
              : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200 hover:text-neutral-700"
          }`}
        >
          {cat.category}
          <span className="ml-1.5 text-[10px] opacity-50">{cat.count}</span>
        </motion.button>
      ))}
    </div>
  );
}
