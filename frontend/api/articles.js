const SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co";
const SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI4MzE4NjMsImV4cCI6MjA4ODQwNzg2M30.5UuGFW-8EC7Neu9uOwakCdzfDQ5o3mZaAQjpYs6WEfk";

const headers = {
  apikey: SUPABASE_ANON,
  Authorization: `Bearer ${SUPABASE_ANON}`,
};

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();

  const { slug } = req.query;

  try {
    // Try Supabase first
    const url = slug
      ? `${SUPABASE_URL}/rest/v1/articles?slug=eq.${slug}&is_published=eq.true&limit=1`
      : `${SUPABASE_URL}/rest/v1/articles?is_published=eq.true&order=rank.asc&limit=100`;

    const response = await fetch(url, { headers });

    if (response.ok) {
      const data = await response.json();
      if (data.length > 0) {
        // Also fetch source profiles for matching
        const srcRes = await fetch(
          `${SUPABASE_URL}/rest/v1/source_profiles?limit=100`,
          { headers }
        );
        const sources = srcRes.ok ? await srcRes.json() : [];

        // Enrich articles with matched sources
        const enriched = data.map((article) => {
          const attr = (article.author_attribution || "").toLowerCase();
          const matched = sources.filter(
            (s) => s.name && attr.includes(s.name.toLowerCase())
          );
          return { ...article, sources: matched };
        });

        return res.status(200).json(slug ? enriched[0] : enriched);
      }
    }

    // Fallback: articles table might not exist yet
    return res.status(slug ? 404 : 200).json(slug ? { error: "Not found" } : []);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
