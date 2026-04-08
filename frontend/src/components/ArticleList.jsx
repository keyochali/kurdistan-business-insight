import React from "react";
import { motion } from "framer-motion";
import ArticleCard from "./ArticleCard";

function LoadingSkeleton() {
  return (
    <div className="space-y-10">
      {/* Featured skeleton */}
      <div className="bg-white rounded-2xl overflow-hidden border border-neutral-100 md:flex animate-pulse">
        <div className="md:w-1/2 aspect-[1.91/1] md:aspect-auto md:h-80 bg-neutral-100" />
        <div className="md:w-1/2 p-10 space-y-4">
          <div className="h-3 bg-neutral-100 rounded-full w-20" />
          <div className="h-7 bg-neutral-100 rounded w-full" />
          <div className="h-7 bg-neutral-100 rounded w-3/4" />
          <div className="h-4 bg-neutral-100 rounded w-full" />
          <div className="h-4 bg-neutral-100 rounded w-2/3" />
        </div>
      </div>

      {/* Grid skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-white rounded-xl overflow-hidden border border-neutral-100 animate-pulse">
            <div className="aspect-[1.91/1] bg-neutral-100" />
            <div className="p-5 space-y-3">
              <div className="h-5 bg-neutral-100 rounded w-full" />
              <div className="h-5 bg-neutral-100 rounded w-3/4" />
              <div className="h-3 bg-neutral-100 rounded w-full" />
              <div className="h-3 bg-neutral-100 rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ArticleList({ articles, loading }) {
  if (loading) return <LoadingSkeleton />;

  if (!articles || articles.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-center py-24"
      >
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-neutral-100 flex items-center justify-center">
          <span className="text-2xl text-neutral-300 font-serif font-bold">K</span>
        </div>
        <h3 className="text-lg font-medium text-neutral-600 mb-2">No articles yet</h3>
        <p className="text-sm text-neutral-400">
          Check back soon for today's articles.
        </p>
      </motion.div>
    );
  }

  const [featured, ...rest] = articles;

  return (
    <div className="space-y-10">
      {/* Featured article */}
      {featured && <ArticleCard article={featured} featured />}

      {/* Grid */}
      {rest.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {rest.map((article, i) => (
            <ArticleCard key={article.slug} article={article} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
