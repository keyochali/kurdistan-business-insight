/**
 * API layer — reads from static data.json for production (Vercel),
 * or from the FastAPI backend in development.
 */

let _cachedData = null;

async function loadData() {
  if (_cachedData) return _cachedData;

  try {
    const res = await fetch("/data.json");
    if (res.ok) {
      _cachedData = await res.json();
      return _cachedData;
    }
  } catch (e) {
    // data.json not available — fall back to API
  }

  // Fallback: local FastAPI backend
  const API = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const res = await fetch(`${API}/api/articles/`);
  const d = await res.json();
  return { articles: d.items, sources: [], profiles: [], companies: [] };
}

function matchSources(article, sources) {
  if (!article.author_attribution || !sources.length) return [];
  const attr = article.author_attribution.toLowerCase();
  return sources.filter((s) => s.name && attr.includes(s.name.toLowerCase()));
}

export async function fetchArticles({
  page = 1,
  pageSize = 20,
  category = null,
  search = null,
} = {}) {
  const data = await loadData();
  let items = data.articles.filter((a) => a.is_published);

  if (category) items = items.filter((a) => a.category === category);
  if (search) {
    const q = search.toLowerCase();
    items = items.filter(
      (a) =>
        a.headline.toLowerCase().includes(q) ||
        (a.summary && a.summary.toLowerCase().includes(q))
    );
  }

  // Attach sources
  items = items.map((a) => ({ ...a, sources: matchSources(a, data.sources) }));

  const total = items.length;
  const start = (page - 1) * pageSize;
  const paged = items.slice(start, start + pageSize);

  return {
    items: paged,
    total,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(total / pageSize),
  };
}

export async function fetchTodaysArticles() {
  const data = await loadData();
  const today = new Date().toISOString().split("T")[0];
  return data.articles
    .filter((a) => a.is_published && a.publish_date === today)
    .map((a) => ({ ...a, sources: matchSources(a, data.sources) }));
}

export async function fetchArticlesByDate(date) {
  const data = await loadData();
  return data.articles
    .filter((a) => a.is_published && a.publish_date === date)
    .map((a) => ({ ...a, sources: matchSources(a, data.sources) }));
}

export async function fetchArticle(slug) {
  const data = await loadData();
  const article = data.articles.find((a) => a.slug === slug && a.is_published);
  if (!article) throw { response: { status: 404 } };
  return { ...article, sources: matchSources(article, data.sources) };
}

export async function fetchCategories() {
  const data = await loadData();
  const counts = {};
  data.articles
    .filter((a) => a.is_published)
    .forEach((a) => {
      const cat = a.category || "Uncategorized";
      counts[cat] = (counts[cat] || 0) + 1;
    });

  return Object.entries(counts)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count);
}

export async function fetchAvailableDates() {
  const data = await loadData();
  const counts = {};
  data.articles
    .filter((a) => a.is_published)
    .forEach((a) => {
      counts[a.publish_date] = (counts[a.publish_date] || 0) + 1;
    });

  return Object.entries(counts)
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

// Admin data access
export async function fetchProfiles() {
  const data = await loadData();
  return data.profiles || [];
}

export async function fetchCompanies() {
  const data = await loadData();
  return data.companies || [];
}
