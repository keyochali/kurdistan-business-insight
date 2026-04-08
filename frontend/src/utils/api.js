/**
 * API layer — reads from Supabase REST API first, falls back to static data.json.
 * On production: tries /api/articles (Vercel serverless → Supabase), then data.json.
 * This ensures the site works whether Supabase tables exist or not.
 */

const SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co";
const SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI4MzE4NjMsImV4cCI6MjA4ODQwNzg2M30.5UuGFW-8EC7Neu9uOwakCdzfDQ5o3mZaAQjpYs6WEfk";
const SUPABASE_HEADERS = { apikey: SUPABASE_ANON, Authorization: `Bearer ${SUPABASE_ANON}` };

let _cachedData = null;
let _supabaseAvailable = null; // null = unknown, true/false

// Check if Supabase has our articles table
async function checkSupabase() {
  if (_supabaseAvailable !== null) return _supabaseAvailable;
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/articles?limit=1&is_published=eq.true`,
      { headers: SUPABASE_HEADERS, signal: AbortSignal.timeout(3000) }
    );
    _supabaseAvailable = res.ok && Array.isArray(await res.json());
  } catch {
    _supabaseAvailable = false;
  }
  return _supabaseAvailable;
}

async function supabaseGet(table, params = "") {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/${table}?${params}`,
    { headers: SUPABASE_HEADERS }
  );
  if (!res.ok) throw new Error(`Supabase error: ${res.status}`);
  return res.json();
}

async function loadStaticData() {
  if (_cachedData) return _cachedData;
  const res = await fetch("/data.json");
  if (res.ok) {
    _cachedData = await res.json();
    return _cachedData;
  }
  return { articles: [], sources: [], profiles: [], companies: [] };
}

function matchSources(article, sources) {
  if (!article.author_attribution || !sources.length) return [];
  const attr = article.author_attribution.toLowerCase();
  return sources.filter((s) => s.name && attr.includes(s.name.toLowerCase()));
}

// ── Public API ──

export async function fetchArticles({ page = 1, pageSize = 20, category = null, search = null } = {}) {
  const useSupa = await checkSupabase();

  let items, sources;

  if (useSupa) {
    let params = "is_published=eq.true&order=rank.asc&limit=100";
    if (category) params += `&category=eq.${encodeURIComponent(category)}`;
    items = await supabaseGet("articles", params);
    sources = await supabaseGet("source_profiles", "limit=100");

    if (search) {
      const q = search.toLowerCase();
      items = items.filter(
        (a) => a.headline.toLowerCase().includes(q) || (a.summary && a.summary.toLowerCase().includes(q))
      );
    }
  } else {
    const data = await loadStaticData();
    items = data.articles.filter((a) => a.is_published);
    sources = data.sources;
    if (category) items = items.filter((a) => a.category === category);
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(
        (a) => a.headline.toLowerCase().includes(q) || (a.summary && a.summary.toLowerCase().includes(q))
      );
    }
  }

  items = items.map((a) => ({ ...a, sources: matchSources(a, sources) }));
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
  const useSupa = await checkSupabase();

  if (useSupa) {
    const rows = await supabaseGet("articles", `slug=eq.${slug}&is_published=eq.true&limit=1`);
    if (!rows.length) throw { response: { status: 404 } };
    const article = rows[0];
    const sources = await supabaseGet("source_profiles", "limit=100");
    const images = await supabaseGet("article_images", `article_id=eq.${article.id}&limit=20`);
    return { ...article, sources: matchSources(article, sources), images };
  }

  const data = await loadStaticData();
  const article = data.articles.find((a) => a.slug === slug && a.is_published);
  if (!article) throw { response: { status: 404 } };
  return { ...article, sources: matchSources(article, data.sources) };
}

export async function fetchTodaysArticles() {
  const today = new Date().toISOString().split("T")[0];
  const result = await fetchArticles();
  return result.items.filter((a) => a.publish_date === today);
}

export async function fetchArticlesByDate(date) {
  const useSupa = await checkSupabase();
  let items, sources;

  if (useSupa) {
    items = await supabaseGet("articles", `publish_date=eq.${date}&is_published=eq.true&order=rank.asc`);
    sources = await supabaseGet("source_profiles", "limit=100");
  } else {
    const data = await loadStaticData();
    items = data.articles.filter((a) => a.is_published && a.publish_date === date);
    sources = data.sources;
  }
  return items.map((a) => ({ ...a, sources: matchSources(a, sources) }));
}

export async function fetchCategories() {
  const result = await fetchArticles({ pageSize: 200 });
  const counts = {};
  result.items.forEach((a) => {
    const cat = a.category || "Uncategorized";
    counts[cat] = (counts[cat] || 0) + 1;
  });
  return Object.entries(counts)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count);
}

export async function fetchAvailableDates() {
  const result = await fetchArticles({ pageSize: 200 });
  const counts = {};
  result.items.forEach((a) => {
    counts[a.publish_date] = (counts[a.publish_date] || 0) + 1;
  });
  return Object.entries(counts)
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

export async function fetchProfiles() {
  const useSupa = await checkSupabase();
  if (useSupa) {
    try { return await supabaseGet("linkedin_profiles", "order=name.asc&limit=200"); } catch {}
  }
  const data = await loadStaticData();
  return data.profiles || [];
}

export async function fetchCompanies() {
  const useSupa = await checkSupabase();
  if (useSupa) {
    try { return await supabaseGet("linkedin_companies", "order=name.asc&limit=200"); } catch {}
  }
  const data = await loadStaticData();
  return data.companies || [];
}
