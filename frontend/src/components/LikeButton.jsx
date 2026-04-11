import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Heart } from "lucide-react";

export default function LikeButton({ articleId }) {
  const [liked, setLiked] = useState(false);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showPop, setShowPop] = useState(false);

  // Check initial state on mount
  useEffect(() => {
    if (!articleId) return;

    // Check localStorage first (instant)
    const stored = localStorage.getItem(`kbi_like_${articleId}`);
    if (stored === "true") setLiked(true);

    // Then verify with server
    fetch(`/api/like?article_id=${articleId}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setLiked(data.liked);
          setCount(data.count);
          localStorage.setItem(`kbi_like_${articleId}`, data.liked ? "true" : "false");
        }
      })
      .catch(() => {});
  }, [articleId]);

  const handleLike = async () => {
    if (loading || !articleId) return;
    setLoading(true);

    // Optimistic update
    const newLiked = !liked;
    setLiked(newLiked);
    setCount((c) => c + (newLiked ? 1 : -1));
    if (newLiked) {
      setShowPop(true);
      setTimeout(() => setShowPop(false), 600);
    }

    try {
      const res = await fetch("/api/like", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ article_id: articleId }),
      });
      if (res.ok) {
        const data = await res.json();
        setLiked(data.liked);
        setCount(data.count);
        localStorage.setItem(`kbi_like_${articleId}`, data.liked ? "true" : "false");
      }
    } catch {
      // Revert on error
      setLiked(!newLiked);
      setCount((c) => c + (newLiked ? -1 : 1));
    }
    setLoading(false);
  };

  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        handleLike();
      }}
      className="relative flex items-center gap-1.5 group"
      aria-label={liked ? "Unlike" : "Like"}
    >
      {/* Pop animation */}
      <AnimatePresence>
        {showPop && (
          <motion.div
            initial={{ scale: 0, opacity: 1 }}
            animate={{ scale: 2.5, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
          >
            <Heart size={14} className="text-red-400 fill-red-400" />
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        whileTap={{ scale: 0.8 }}
        transition={{ type: "spring", stiffness: 400 }}
      >
        <Heart
          size={15}
          className={`transition-colors duration-200 ${
            liked
              ? "text-red-500 fill-red-500"
              : "text-neutral-300 group-hover:text-red-400"
          }`}
        />
      </motion.div>

      {count > 0 && (
        <span className={`text-xs transition-colors ${liked ? "text-red-500 font-medium" : "text-neutral-400"}`}>
          {count}
        </span>
      )}
    </button>
  );
}
