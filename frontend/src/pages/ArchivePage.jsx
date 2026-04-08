import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Calendar } from "lucide-react";
import ArticleCard from "../components/ArticleCard";
import { fetchAvailableDates, fetchArticlesByDate } from "../utils/api";

export default function ArchivePage() {
  const [dates, setDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const d = await fetchAvailableDates();
      setDates(d);
      if (d.length > 0) {
        setSelectedDate(d[0].date);
      }
      setLoading(false);
    }
    load();
  }, []);

  useEffect(() => {
    if (!selectedDate) return;
    async function load() {
      setLoading(true);
      const arts = await fetchArticlesByDate(selectedDate);
      setArticles(arts);
      setLoading(false);
    }
    load();
  }, [selectedDate]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <p className="text-xs font-medium tracking-widest uppercase text-accent-500 mb-3">
          Archive
        </p>
        <h2 className="text-4xl md:text-5xl font-serif font-bold text-neutral-900 leading-tight mb-8">
          Past <span className="text-neutral-400">Editions</span>
        </h2>
      </motion.div>

      <div className="border-t border-neutral-200 mb-10" />

      {/* Date selector */}
      <div className="flex flex-wrap gap-2 mb-10">
        {dates.map((d) => (
          <button
            key={d.date}
            onClick={() => setSelectedDate(d.date)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all duration-200 ${
              selectedDate === d.date
                ? "bg-neutral-900 text-white"
                : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200"
            }`}
          >
            <Calendar size={13} />
            {new Date(d.date + "T00:00:00").toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
            <span className="text-[10px] opacity-50">({d.count})</span>
          </button>
        ))}
      </div>

      {/* Articles for selected date */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl overflow-hidden border border-neutral-100 animate-pulse">
              <div className="aspect-[1.91/1] bg-neutral-100" />
              <div className="p-5 space-y-3">
                <div className="h-5 bg-neutral-100 rounded w-full" />
                <div className="h-3 bg-neutral-100 rounded w-2/3" />
              </div>
            </div>
          ))}
        </div>
      ) : articles.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {articles.map((article, i) => (
            <ArticleCard key={article.slug} article={article} index={i} />
          ))}
        </div>
      ) : (
        <p className="text-center text-neutral-400 py-16">
          No articles for this date.
        </p>
      )}
    </div>
  );
}
