/**
 * API layer — reads directly from Supabase. No static files.
 */

const SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co";
const SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI4MzE4NjMsImV4cCI6MjA4ODQwNzg2M30.5UuGFW-8EC7Neu9uOwakCdzfDQ5o3mZaAQjpYs6WEfk";

const headers = {
  apikey: SUPABASE_ANON,
  Authorization: `Bearer ${SUPABASE_ANON}`,
};

async function supa(table, params = "") {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${params}`, { headers });
  if (!res.ok) throw new Error(`Supabase ${table}: ${res.status}`);
  return res.json();
}

let _sourcesCache = null;

async function getSources() {
  if (_sourcesCache) return _sourcesCache;
  _sourcesCache = await supa("source_profiles", "limit=200");
  return _sourcesCache;
}

function matchSources(article, sources) {
  if (!article.author_attribution || !sources.length) return [];
  const attr = article.author_attribution.toLowerCase();
  return sources.filter((s) => s.name && attr.includes(s.name.toLowerCase()));
}

async function enrichArticles(articles) {
  const sources = await getSources();
  return articles.map((a) => ({ ...a, sources: matchSources(a, sources) }));
}

export async function fetchArticles({ page = 1, pageSize = 20, category = null, search = null } = {}) {
  let params = "is_published=eq.true&order=rank.asc,publish_date.desc&limit=200";
  if (category) params += `&category=eq.${encodeURIComponent(category)}`;

  let items = await supa("articles", params);

  if (search) {
    const q = search.toLowerCase();
    items = items.filter(
      (a) => a.headline.toLowerCase().includes(q) || (a.summary && a.summary.toLowerCase().includes(q))
    );
  }

  items = await enrichArticles(items);
  const total = items.length;
  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    total,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(total / pageSize),
  };
}

export async function fetchArticle(slug) {
  const rows = await supa("articles", `slug=eq.${slug}&is_published=eq.true&limit=1`);
  if (!rows.length) throw { response: { status: 404 } };
  const article = rows[0];
  const [sources, images] = await Promise.all([
    getSources(),
    supa("article_images", `article_id=eq.${article.id}&limit=50`),
  ]);
  return { ...article, sources: matchSources(article, sources), images };
}

export async function fetchTodaysArticles() {
  const today = new Date().toISOString().split("T")[0];
  const items = await supa("articles", `publish_date=eq.${today}&is_published=eq.true&order=rank.asc`);
  return enrichArticles(items);
}

export async function fetchArticlesByDate(date) {
  const items = await supa("articles", `publish_date=eq.${date}&is_published=eq.true&order=rank.asc`);
  return enrichArticles(items);
}

export async function fetchCategories() {
  const items = await supa("articles", "is_published=eq.true&select=category&limit=500");
  const counts = {};
  items.forEach((a) => {
    const cat = a.category || "Uncategorized";
    counts[cat] = (counts[cat] || 0) + 1;
  });
  return Object.entries(counts)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count);
}

export async function fetchAvailableDates() {
  const items = await supa("articles", "is_published=eq.true&select=publish_date&limit=500");
  const counts = {};
  items.forEach((a) => {
    if (a.publish_date) counts[a.publish_date] = (counts[a.publish_date] || 0) + 1;
  });
  return Object.entries(counts)
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

export async function fetchProfiles() {
  return supa("linkedin_profiles", "order=name.asc&limit=200");
}

export async function fetchCompanies() {
  return supa("linkedin_companies", "order=name.asc&limit=200");
}
