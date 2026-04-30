import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ExternalLink } from "lucide-react";

/**
 * Small inline avatars for article sources.
 * Clicking opens a modal with full source details and LinkedIn links.
 */

function AvatarImg({ src, alt, className, fallbackChar }) {
  const [failed, setFailed] = useState(false);
  if (failed || !src) {
    return (
      <div className={className + " bg-neutral-100 flex items-center justify-center"}>
        <span className="text-sm font-semibold text-neutral-400">{fallbackChar}</span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}

function SourceModal({ sources, onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2 }}
        className="bg-white rounded-2xl shadow-2xl max-w-sm w-full mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-100">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-neutral-400">
            Sources
          </h3>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Source list */}
        <div className="p-4 space-y-1 max-h-[60vh] overflow-y-auto">
          {sources.map((source, i) => (
            <a
              key={i}
              href={source.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-4 p-3 rounded-xl hover:bg-neutral-50 transition-colors group"
            >
              {/* Avatar */}
              <div className="flex-shrink-0">
                <AvatarImg
                  src={source.avatar_url}
                  alt={source.name}
                  className="w-12 h-12 rounded-full object-cover ring-2 ring-neutral-100"
                  fallbackChar={source.name?.charAt(0)}
                />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-neutral-900 truncate">
                    {source.name}
                  </p>
                  <ExternalLink
                    size={12}
                    className="flex-shrink-0 text-neutral-300 group-hover:text-accent-400 transition-colors"
                  />
                </div>
                {source.headline && (
                  <p className="text-xs text-neutral-400 truncate mt-0.5">
                    {source.headline}
                  </p>
                )}
                <p className="text-[10px] text-accent-500 uppercase tracking-wider mt-1">
                  {source.type === "company" ? "Company" : "Professional"}
                </p>
              </div>
            </a>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}

/**
 * Inline source avatars — shows small profile pics, clickable to open modal.
 * compact: just avatars stacked. full: avatars + "Sources" label.
 */
export default function SourceBadge({ sources, compact = false }) {
  const [modalOpen, setModalOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <>
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setModalOpen(true);
        }}
        className="flex items-center gap-2 group"
      >
        {/* Stacked avatars */}
        <div className="flex -space-x-2">
          {sources.slice(0, 3).map((source, i) => (
            <div
              key={i}
              className="relative"
              style={{ zIndex: 3 - i }}
            >
              <AvatarImg
                src={source.avatar_url}
                alt={source.name}
                className="w-6 h-6 rounded-full object-cover ring-2 ring-white group-hover:ring-accent-100 transition-all"
                fallbackChar={source.name?.charAt(0)}
              />
            </div>
          ))}
        </div>

        {/* Label */}
        {!compact && (
          <span className="text-xs text-neutral-400 group-hover:text-accent-500 transition-colors whitespace-nowrap">
            {sources.length === 1
              ? sources[0].name
              : `${sources.length} sources`}
          </span>
        )}
      </button>

      <AnimatePresence>
        {modalOpen && (
          <SourceModal
            sources={sources}
            onClose={() => setModalOpen(false)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
