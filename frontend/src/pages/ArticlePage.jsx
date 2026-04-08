import React, { useState, useEffect, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Clock, Calendar, X, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { fetchArticle } from "../utils/api";
import { getCategoryBadgeStyle } from "../components/CategoryFilter";
import SourceBadge from "../components/SourceBadge";

const SITE_URL = "https://frontend-eight-azure-29.vercel.app";

const API_URL = process.env.REACT_APP_API_URL || "";
const MAX_GALLERY_IMAGES = 8;

function resolveImageUrl(img) {
  if (img.image_url) return img.image_url;
  return null;
}

function ImageLightbox({ images, startIndex, onClose }) {
  const [index, setIndex] = useState(startIndex);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") setIndex((i) => Math.min(images.length - 1, i + 1));
      if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [images.length, onClose]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-6 right-6 text-white/60 hover:text-white transition-colors"
      >
        <X size={24} />
      </button>

      <div className="absolute top-6 left-1/2 -translate-x-1/2 text-white/40 text-xs tracking-widest">
        {index + 1} / {images.length}
      </div>

      {index > 0 && (
        <button
          onClick={(e) => { e.stopPropagation(); setIndex((i) => i - 1); }}
          className="absolute left-4 md:left-8 text-white/40 hover:text-white transition-colors"
        >
          <ChevronLeft size={32} />
        </button>
      )}

      {index < images.length - 1 && (
        <button
          onClick={(e) => { e.stopPropagation(); setIndex((i) => i + 1); }}
          className="absolute right-4 md:right-8 text-white/40 hover:text-white transition-colors"
        >
          <ChevronRight size={32} />
        </button>
      )}

      <motion.img
        key={index}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2 }}
        src={images[index]}
        alt=""
        className="max-w-[90vw] max-h-[85vh] object-contain rounded-lg"
        onClick={(e) => e.stopPropagation()}
      />
    </motion.div>
  );
}

export default function ArticlePage() {
  const { slug } = useParams();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lightboxIndex, setLightboxIndex] = useState(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchArticle(slug);
        setArticle(data);
      } catch (err) {
        setError(
          err.response?.status === 404
            ? "Article not found"
            : "Failed to load article"
        );
      } finally {
        setLoading(false);
      }
    }
    load();
    window.scrollTo(0, 0);
  }, [slug]);

  // Collect URLs already shown inline in body_html so we can skip them in the gallery
  const inlineUrls = useMemo(() => {
    if (!article?.body_html) return new Set();
    const matches = article.body_html.match(/article-inline-image[^>]*>[\s\S]*?src="([^"]+)"/g) || [];
    return new Set(matches.map((m) => {
      const srcMatch = m.match(/src="([^"]+)"/);
      return srcMatch ? srcMatch[1] : null;
    }).filter(Boolean));
  }, [article]);

  // Build the full image list: featured first, then extras (deduplicated, capped)
  const allImages = useMemo(() => {
    if (!article) return [];

    const featured = article.featured_image_url || null;

    const seen = new Set();
    const images = [];

    if (featured) {
      images.push(featured);
      seen.add(featured);
    }

    // Skip images already shown inline in the article body
    for (const u of inlineUrls) {
      seen.add(u);
      // Also match the full URL version of a relative path
      if (u.startsWith("/static/")) seen.add(`${API_URL}${u}`);
    }

    const extras = (article.images || [])
      .filter((img) => !img.is_featured)
      .slice(0, MAX_GALLERY_IMAGES + 3); // fetch a few extra to compensate for skips

    for (const img of extras) {
      const url = resolveImageUrl(img);
      if (url && !seen.has(url)) {
        images.push(url);
        seen.add(url);
      }
      if (images.length >= MAX_GALLERY_IMAGES + 1) break; // +1 for featured
    }

    return images;
  }, [article, inlineUrls]);

  const galleryImages = allImages.slice(1); // everything except featured

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-16 animate-pulse">
        <div className="h-3 bg-neutral-100 rounded-full w-24 mb-8" />
        <div className="h-4 bg-neutral-100 rounded-full w-20 mb-6" />
        <div className="h-10 bg-neutral-100 rounded w-full mb-3" />
        <div className="h-10 bg-neutral-100 rounded w-3/4 mb-8" />
        <div className="h-5 bg-neutral-100 rounded w-48 mb-10" />
        <div className="aspect-[1.91/1] bg-neutral-100 rounded-xl mb-10" />
        <div className="space-y-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-4 bg-neutral-100 rounded w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-24 text-center">
        <h2 className="text-2xl font-serif font-bold text-neutral-900 mb-3">
          {error}
        </h2>
        <Link
          to="/"
          className="text-sm text-neutral-500 hover:text-neutral-900 transition-colors"
        >
          Back to Home
        </Link>
      </div>
    );
  }

  if (!article) return null;

  const featuredUrl = allImages[0] || null;

  const articleUrl = `${SITE_URL}/article/${slug}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: article.headline,
    description: article.summary || article.subheadline || "",
    image: article.featured_image_url || undefined,
    datePublished: article.publish_date,
    author: {
      "@type": "Organization",
      name: "Kurdistan Business Insight",
    },
    publisher: {
      "@type": "Organization",
      name: "Kurdistan Business Insight",
    },
    mainEntityOfPage: articleUrl,
  };

  return (
    <>
      <Helmet>
        <title>{article.headline} — Kurdistan Business Insight</title>
        <meta name="description" content={(article.summary || article.subheadline || "").slice(0, 160)} />
        <link rel="canonical" href={articleUrl} />
        <meta property="og:title" content={article.headline} />
        <meta property="og:description" content={(article.summary || "").slice(0, 200)} />
        <meta property="og:type" content="article" />
        <meta property="og:url" content={articleUrl} />
        {article.featured_image_url && <meta property="og:image" content={article.featured_image_url} />}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={article.headline} />
        <meta name="twitter:description" content={(article.summary || "").slice(0, 200)} />
        {article.featured_image_url && <meta name="twitter:image" content={article.featured_image_url} />}
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      </Helmet>
      <motion.article
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-12"
      >
        {/* Back link */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-neutral-400 hover:text-neutral-900 transition-colors mb-10 group"
        >
          <ArrowLeft
            size={14}
            className="group-hover:-translate-x-1 transition-transform duration-200"
          />
          All articles
        </Link>

        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mb-10"
        >
          {article.category && (
            <span
              className={`inline-block px-3 py-1 text-[10px] font-semibold uppercase tracking-widest rounded-full mb-5 ${getCategoryBadgeStyle(article.category)}`}
            >
              {article.category}
            </span>
          )}

          <h1 className="text-3xl md:text-5xl font-serif font-bold text-neutral-900 leading-tight mb-5">
            {article.headline}
          </h1>

          {article.subheadline && (
            <p className="text-xl text-neutral-400 leading-relaxed mb-6">
              {article.subheadline}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-5 text-sm text-neutral-400 pb-8 border-b border-neutral-200">
            <span className="flex items-center gap-1.5">
              <Calendar size={13} />
              {new Date(article.publish_date).toLocaleDateString("en-US", {
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock size={13} />
              {article.reading_time_minutes} min read
            </span>
            {article.sources && article.sources.length > 0 && (
              <SourceBadge sources={article.sources} />
            )}
          </div>
        </motion.header>

        {/* Source profiles card */}
        {article.sources && article.sources.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="mb-10 flex flex-wrap gap-3"
          >
            {article.sources.map((source, i) => (
              <a
                key={i}
                href={source.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 pl-1 pr-4 py-1 rounded-full border border-neutral-200 hover:border-accent-300 hover:bg-accent-50/50 transition-all group"
              >
                {source.avatar_url ? (
                  <img
                    src={source.avatar_url}
                    alt={source.name}
                    className="w-8 h-8 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center">
                    <span className="text-xs font-bold text-neutral-400">{source.name?.charAt(0)}</span>
                  </div>
                )}
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-neutral-700 group-hover:text-neutral-900 transition-colors">
                    {source.name}
                  </span>
                  <ExternalLink size={11} className="text-neutral-300 group-hover:text-accent-400 transition-colors" />
                </div>
              </a>
            ))}
          </motion.div>
        )}

        {/* Summary */}
        {article.summary && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="bg-neutral-50 border-l-2 border-accent-400 px-6 py-5 rounded-r-lg mb-10"
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-accent-600 mb-2">
              Key Takeaway
            </p>
            <p className="text-neutral-600 leading-relaxed">{article.summary}</p>
          </motion.div>
        )}

        {/* Featured image */}
        {featuredUrl && (
          <motion.figure
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mb-10 cursor-pointer"
            onClick={() => setLightboxIndex(0)}
          >
            <img
              src={featuredUrl}
              alt={article.headline}
              className="w-full rounded-xl object-cover aspect-[1.91/1] hover:brightness-95 transition-all duration-300"
            />
            {allImages.length > 1 && (
              <p className="text-xs text-neutral-400 mt-2 text-right">
                {allImages.length} photos &middot; click to view
              </p>
            )}
          </motion.figure>
        )}

        {/* Article body */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="article-body"
          dangerouslySetInnerHTML={{ __html: article.body_html }}
        />

        {/* Image gallery */}
        {galleryImages.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="mt-12 pt-8 border-t border-neutral-200"
          >
            <h4 className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-5">
              More from this story
            </h4>
            <div
              className={`grid gap-3 ${
                galleryImages.length === 1
                  ? "grid-cols-1"
                  : galleryImages.length === 2
                  ? "grid-cols-2"
                  : "grid-cols-2 md:grid-cols-3"
              }`}
            >
              {galleryImages.map((url, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.5 + i * 0.05 }}
                  className="cursor-pointer group"
                  onClick={() => setLightboxIndex(i + 1)}
                >
                  <img
                    src={url}
                    alt=""
                    className="w-full aspect-[1.91/1] object-cover rounded-lg group-hover:brightness-90 transition-all duration-300"
                  />
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Tags */}
        {article.tags && article.tags.length > 0 && (
          <div className="mt-14 pt-8 border-t border-neutral-200">
            <h4 className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">
              Topics
            </h4>
            <div className="flex flex-wrap gap-2">
              {article.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-3 py-1 bg-neutral-100 text-neutral-500 text-xs rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Bottom nav */}
        <div className="mt-14 pt-8 border-t border-neutral-200">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-neutral-400 hover:text-neutral-900 transition-colors group"
          >
            <ArrowLeft
              size={14}
              className="group-hover:-translate-x-1 transition-transform duration-200"
            />
            Back to all articles
          </Link>
        </div>
      </motion.article>

      {/* Lightbox */}
      <AnimatePresence>
        {lightboxIndex !== null && (
          <ImageLightbox
            images={allImages}
            startIndex={lightboxIndex}
            onClose={() => setLightboxIndex(null)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
