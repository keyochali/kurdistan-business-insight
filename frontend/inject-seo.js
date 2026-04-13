/**
 * Post-build: inject article content into index.html for SEO.
 * Google can crawl the hidden semantic HTML even before JS loads.
 */
const fs = require("fs");
const https = require("https");

const SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co";
const ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI4MzE4NjMsImV4cCI6MjA4ODQwNzg2M30.5UuGFW-8EC7Neu9uOwakCdzfDQ5o3mZaAQjpYs6WEfk";
const SITE_URL = "https://frontend-eight-azure-29.vercel.app";

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { apikey: ANON_KEY, Authorization: `Bearer ${ANON_KEY}` } }, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch { resolve([]); }
      });
    }).on("error", reject);
  });
}

async function main() {
  const articles = await fetchJSON(
    `${SUPABASE_URL}/rest/v1/articles?is_published=eq.true&select=slug,headline,summary,category,publish_date&order=rank.asc&limit=30`
  );

  console.log(`Injecting SEO for ${articles.length} articles...`);

  let html = fs.readFileSync("build/index.html", "utf8");

  // Build hidden semantic HTML block
  let seo = '<div id="seo-content" style="display:none" aria-hidden="true">\n';
  seo += "<h1>Kurdistan Business Insight — Daily Business News</h1>\n";
  seo += "<p>Daily curated business news from Kurdistan Region's most influential leaders and companies.</p>\n";

  for (const a of articles) {
    const summary = (a.summary || "").replace(/"/g, "&quot;").replace(/</g, "&lt;");
    seo += `<article><h2><a href="/article/${a.slug}">${a.headline}</a></h2><p>${summary.slice(0, 200)}</p></article>\n`;
  }
  seo += "</div>\n";

  // JSON-LD for homepage
  const jsonld = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Kurdistan Business Insight",
    url: SITE_URL,
    description: "Daily curated business news from Kurdistan Region.",
  });
  seo += `<script type="application/ld+json">${jsonld}</script>\n`;

  // Inject before <div id="root">
  html = html.replace('<div id="root">', seo + '<div id="root">');

  fs.writeFileSync("build/index.html", html);
  console.log("SEO content injected into index.html");
}

main().catch((e) => {
  console.error("SEO injection failed:", e.message);
  process.exit(0); // Don't fail the build
});
