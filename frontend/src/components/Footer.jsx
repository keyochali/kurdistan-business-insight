import React from "react";
import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="border-t border-neutral-200 mt-24">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
          {/* Brand */}
          <div className="md:col-span-2">
            <h3 className="text-xl font-serif font-bold text-neutral-900 mb-3">
              Kurdistan <span className="text-accent-400">Business</span> Insight
            </h3>
            <p className="text-sm text-neutral-400 leading-relaxed max-w-md">
              Daily business intelligence from Kurdistan Region's most influential
              business leaders and companies.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">
              Navigate
            </h4>
            <ul className="space-y-3">
              <li>
                <Link
                  to="/"
                  className="text-sm text-neutral-500 hover:text-neutral-900 transition-colors"
                >
                  Today's Articles
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-neutral-100 mt-12 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-neutral-400">
            &copy; {new Date().getFullYear()} Kurdistan Business Insight
          </p>
          <p className="text-xs text-neutral-300">
            20 articles daily
          </p>
        </div>
      </div>
    </footer>
  );
}
