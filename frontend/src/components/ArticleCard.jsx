import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Clock, ArrowUpRight } from "lucide-react";
import { getCategoryBadgeStyle } from "./CategoryFilter";
import SourceBadge from "./SourceBadge";

export default function ArticleCard({ article, featured = false, index = 0 }) {
  const {
    slug,
    headline,
    subheadline,
    summary,
    category,
    featured_image_url,
    featured_image_local,
    author_attribution,
    publish_date,
    reading_time_minutes,
  } = article;

  const imageUrl = featured_image_url || null;

  if (featured) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <Link to={`/article/${slug}`} className="block group">
          <article className="bg-white rounded-2xl overflow-hidden border border-neutral-100 hover:border-neutral-200 transition-all duration-500 hover:shadow-lg">
            <div className="md:flex">
              {/* Image */}
              <div className="md:w-1/2 relative overflow-hidden">
                {imageUrl ? (
                  <img
                    src={imageUrl}
                    alt={headline}
                    className="w-full aspect-[1.91/1] md:aspect-auto md:h-full object-cover transition-transform duration-700 group-hover:scale-[1.03]"
                  />
                ) : (
                  <div className="w-full aspect-[1.91/1] md:aspect-auto md:h-full bg-neutral-100 flex items-center justify-center">
                    <span className="text-6xl text-neutral-200 font-serif font-bold">KBI</span>
                  </div>
                )}
              </div>

              {/* Content */}
              <div className="md:w-1/2 p-5 sm:p-8 md:p-10 flex flex-col justify-center">
                <div className="flex items-center gap-3 mb-4">
                  {category && (
                    <span className={`px-3 py-1 text-[10px] font-semibold uppercase tracking-widest rounded-full ${getCategoryBadgeStyle(category)}`}>
                      {category}
                    </span>
                  )}
                  <span className="text-xs text-neutral-300">
                    {new Date(publish_date).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>

                <h2 className="text-2xl md:text-3xl font-serif font-bold text-neutral-900 leading-tight mb-3 group-hover:text-accent-500 transition-colors duration-300">
                  {headline}
                </h2>

                {summary && (
                  <p className="text-sm text-neutral-400 leading-relaxed mb-6 line-clamp-3">
                    {summary}
                  </p>
                )}

                <div className="flex items-center justify-between mt-auto pt-4 border-t border-neutral-100">
                  <div className="flex items-center gap-4 text-xs text-neutral-400">
                    <span className="flex items-center gap-1.5">
                      <Clock size={12} />
                      {reading_time_minutes} min read
                    </span>
                    {article.sources && article.sources.length > 0 ? (
                      <SourceBadge sources={article.sources} compact />
                    ) : author_attribution ? (
                      <span className="truncate max-w-[200px]">{author_attribution}</span>
                    ) : null}
                  </div>
                  <ArrowUpRight
                    size={16}
                    className="text-neutral-300 group-hover:text-accent-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all duration-300"
                  />
                </div>
              </div>
            </div>
          </article>
        </Link>
      </motion.div>
    );
  }

  // ── Regular card ──
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.5,
        delay: index * 0.06,
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      <Link to={`/article/${slug}`} className="block group h-full">
        <article className="bg-white rounded-xl overflow-hidden border border-neutral-100 hover:border-neutral-200 transition-all duration-500 hover:shadow-md h-full flex flex-col">
          {/* Image */}
          <div className="relative overflow-hidden">
            {imageUrl ? (
              <img
                src={imageUrl}
                alt={headline}
                className="w-full aspect-[1.91/1] object-cover transition-transform duration-700 group-hover:scale-[1.03]"
              />
            ) : (
              <div className="w-full aspect-[1.91/1] bg-neutral-50 flex items-center justify-center">
                <span className="text-4xl text-neutral-200 font-serif font-bold">KBI</span>
              </div>
            )}
            {/* Floating category on image */}
            {category && (
              <span className="absolute top-3 left-3 px-2.5 py-0.5 text-[9px] font-semibold uppercase tracking-widest rounded-full bg-white/90 backdrop-blur-sm text-neutral-700 shadow-sm">
                {category}
              </span>
            )}
          </div>

          {/* Content */}
          <div className="p-5 flex flex-col flex-1">
            <h3 className="text-base font-serif font-bold text-neutral-900 leading-snug mb-2 group-hover:text-accent-500 transition-colors duration-300 line-clamp-2">
              {headline}
            </h3>

            {summary && (
              <p className="text-[13px] text-neutral-400 leading-relaxed mb-4 line-clamp-2 flex-1">
                {summary}
              </p>
            )}

            <div className="flex items-center justify-between mt-auto pt-3 border-t border-neutral-100">
              <div className="flex items-center gap-3 text-xs text-neutral-400">
                {article.sources && article.sources.length > 0 ? (
                  <SourceBadge sources={article.sources} compact />
                ) : (
                  <>
                    <span className="flex items-center gap-1">
                      <Clock size={11} />
                      {reading_time_minutes} min
                    </span>
                    <span>
                      {new Date(publish_date).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </>
                )}
              </div>
              <ArrowUpRight
                size={14}
                className="text-neutral-300 group-hover:text-accent-400 transition-colors duration-300"
              />
            </div>
          </div>
        </article>
      </Link>
    </motion.div>
  );
}
