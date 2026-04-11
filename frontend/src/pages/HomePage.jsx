import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { motion } from "framer-motion";
import { Newspaper, TrendingUp, Users } from "lucide-react";
import ArticleList from "../components/ArticleList";
import CategoryFilter from "../components/CategoryFilter";
import { fetchArticles, fetchCategories } from "../utils/api";

export default function HomePage() {
  const [searchParams] = useSearchParams();
  const [articles, setArticles] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const search = searchParams.get("search");

  useEffect(() => {
    setPage(1);
  }, [selectedCategory, search]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [articlesData, catsData] = await Promise.all([
          fetchArticles({
            page,
            category: selectedCategory,
            search,
          }),
          fetchCategories(),
        ]);
        setArticles(articlesData.items);
        setTotalPages(articlesData.total_pages);
        setCategories(catsData);
      } catch (err) {
        console.error("Failed to load articles:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [page, selectedCategory, search]);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
      <Helmet>
        <title>Kurdistan Business Insight — Daily Business News</title>
        <meta name="description" content="Daily curated business news from Kurdistan Region's most influential leaders and companies." />
        <link rel="canonical" href="https://frontend-eight-azure-29.vercel.app" />
      </Helmet>
      {/* Hero */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="mb-8 sm:mb-14"
      >
        {search ? (
          <div>
            <p className="text-xs font-medium tracking-widest uppercase text-neutral-400 mb-2">
              Search Results
            </p>
            <h2 className="text-3xl md:text-4xl font-serif font-bold text-neutral-900">
              "{search}"
            </h2>
          </div>
        ) : (
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
            <div>
              <p className="text-xs font-medium tracking-widest uppercase text-accent-500 mb-3">
                Daily Intelligence
              </p>
              <h2 className="text-3xl sm:text-4xl md:text-5xl font-serif font-bold text-neutral-900 leading-tight">
                Today's Business
                <br />
                <span className="text-neutral-400">Briefing</span>
              </h2>
            </div>

          </div>
        )}
      </motion.section>

      {/* Divider */}
      <div className="border-t border-neutral-200 mb-10" />

      {/* Category filter */}
      {categories.length > 0 && (
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="mb-10"
        >
          <CategoryFilter
            categories={categories}
            selected={selectedCategory}
            onSelect={setSelectedCategory}
          />
        </motion.section>
      )}

      {/* Articles */}
      <ArticleList articles={articles} loading={loading} />

      {/* Pagination */}
      {totalPages > 1 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex justify-center gap-2 mt-16"
        >
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-5 py-2.5 rounded-lg bg-white border border-neutral-200 text-sm text-neutral-600 hover:border-neutral-300 hover:bg-neutral-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            Previous
          </button>
          <span className="px-4 py-2.5 text-sm text-neutral-400">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-5 py-2.5 rounded-lg bg-white border border-neutral-200 text-sm text-neutral-600 hover:border-neutral-300 hover:bg-neutral-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            Next
          </button>
        </motion.div>
      )}
    </div>
  );
}
