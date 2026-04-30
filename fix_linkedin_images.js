/**
 * Fix broken LinkedIn image URLs by uploading local copies to Supabase Storage
 * and updating the featured_image_url in the database.
 *
 * LinkedIn CDN URLs return 403 when hotlinked from external sites.
 * The pipeline already downloaded these images locally — this script
 * uploads them to Supabase Storage and points the DB at the public URLs.
 */

const fs = require("fs");
const path = require("path");
const https = require("https");
const http = require("http");

const SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co";
const SUPABASE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRna2FqdHpkdWFnaWFvaHd1aWxoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzMTg2MywiZXhwIjoyMDg4NDA3ODYzfQ.NxlhFmuFlAwhXZlTDclGXEGUOepFOnHyCXjM6bEV0mc";

const IMAGES_DIR = path.join(__dirname, "backend", "static", "images");

function fetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith("https") ? https : http;
    const req = mod.request(url, options, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        const body = Buffer.concat(chunks);
        resolve({ status: res.statusCode, body, headers: res.headers });
      });
    });
    req.on("error", reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

function supaRest(method, table, params = "", body = null) {
  const url = `${SUPABASE_URL}/rest/v1/${table}?${params}`;
  const headers = {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
    "Content-Type": "application/json",
    Prefer: "return=representation",
  };
  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);
  return fetch(url, options).then((r) => ({
    status: r.status,
    data: JSON.parse(r.body.toString()),
  }));
}

async function uploadToStorage(filePath, storagePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const ext = path.extname(filePath).toLowerCase();
  const contentType =
    ext === ".png" ? "image/png" : ext === ".webp" ? "image/webp" : "image/jpeg";

  const url = `${SUPABASE_URL}/storage/v1/object/article-images/${storagePath}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": contentType,
      "x-upsert": "true",
    },
    body: fileBuffer,
  });

  if (res.status === 200 || res.status === 201) {
    return `${SUPABASE_URL}/storage/v1/object/public/article-images/${storagePath}`;
  }
  console.error(`  Upload failed (${res.status}): ${res.body.toString().slice(0, 200)}`);
  return null;
}

async function main() {
  console.log("Fetching articles with LinkedIn image URLs...\n");

  const { data: articles } = await supaRest(
    "GET",
    "articles",
    "is_published=eq.true&featured_image_url=like.*licdn.com*&select=id,slug,featured_image_url,featured_image_local&limit=200"
  );

  console.log(`Found ${articles.length} articles with LinkedIn image URLs.\n`);

  let fixed = 0;
  let failed = 0;

  for (const article of articles) {
    const { id, slug, featured_image_local } = article;
    console.log(`[${id}] ${slug}`);

    // Find the local file
    const localPath = featured_image_local
      ? path.join(IMAGES_DIR, "..", featured_image_local)
      : null;

    if (!localPath || !fs.existsSync(localPath)) {
      console.log(`  SKIP: no local file found (${featured_image_local})`);
      failed++;
      continue;
    }

    // Upload to Supabase Storage
    const ext = path.extname(localPath);
    const storagePath = `linkedin/${slug}${ext}`;
    console.log(`  Uploading ${path.basename(localPath)} -> ${storagePath}`);

    const publicUrl = await uploadToStorage(localPath, storagePath);
    if (!publicUrl) {
      failed++;
      continue;
    }

    // Update the database
    const patchRes = await supaRest("PATCH", "articles", `id=eq.${id}`, {
      featured_image_url: publicUrl,
    });

    if (patchRes.status < 300) {
      console.log(`  OK: ${publicUrl}`);
      fixed++;
    } else {
      console.log(`  DB update failed: ${patchRes.status}`);
      failed++;
    }
  }

  // Also fix article_images table
  console.log("\n--- Fixing article_images table ---\n");

  const { data: images } = await supaRest(
    "GET",
    "article_images",
    "image_url=like.*licdn.com*&select=id,article_id,image_url,local_path&limit=500"
  );

  console.log(`Found ${images.length} article_images with LinkedIn URLs.\n`);

  let imgFixed = 0;
  for (const img of images) {
    const localFile = img.local_path
      ? path.join(IMAGES_DIR, "..", img.local_path)
      : null;

    if (!localFile || !fs.existsSync(localFile)) {
      continue;
    }

    const ext = path.extname(localFile);
    const storagePath = `linkedin/extra/${path.basename(localFile, ext)}${ext}`;

    const publicUrl = await uploadToStorage(localFile, storagePath);
    if (!publicUrl) continue;

    const patchRes = await supaRest("PATCH", "article_images", `id=eq.${img.id}`, {
      image_url: publicUrl,
    });

    if (patchRes.status < 300) {
      imgFixed++;
    }
  }

  console.log(`\n=== Summary ===`);
  console.log(`Articles fixed: ${fixed}/${articles.length}`);
  console.log(`Articles failed: ${failed}`);
  console.log(`Extra images fixed: ${imgFixed}/${images.length}`);
}

main().catch(console.error);
