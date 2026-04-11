import crypto from "crypto";

const SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co";
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

const headers = {
  apikey: SUPABASE_SERVICE_KEY,
  Authorization: `Bearer ${SUPABASE_SERVICE_KEY}`,
  "Content-Type": "application/json",
  Prefer: "return=representation",
};

function getFingerprint(req) {
  const ip = req.headers["x-forwarded-for"]?.split(",")[0]?.trim()
    || req.headers["x-real-ip"]
    || "unknown";
  const ua = req.headers["user-agent"] || "";
  return crypto.createHash("sha256").update(`${ip}|${ua}`).digest("hex").slice(0, 16);
}

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();

  if (!SUPABASE_SERVICE_KEY) {
    return res.status(500).json({ error: "Not configured" });
  }

  const fingerprint = getFingerprint(req);

  // GET: check if user already liked + get count
  if (req.method === "GET") {
    const { article_id } = req.query;
    if (!article_id) return res.status(400).json({ error: "article_id required" });

    try {
      // Check if this fingerprint liked this article
      const likeRes = await fetch(
        `${SUPABASE_URL}/rest/v1/article_likes?article_id=eq.${article_id}&fingerprint=eq.${fingerprint}&select=id`,
        { headers }
      );
      const likes = likeRes.ok ? await likeRes.json() : [];
      const hasLiked = likes.length > 0;

      // Get total count
      const countRes = await fetch(
        `${SUPABASE_URL}/rest/v1/article_likes?article_id=eq.${article_id}&select=id`,
        { headers }
      );
      const total = countRes.ok ? (await countRes.json()).length : 0;

      return res.status(200).json({ liked: hasLiked, count: total });
    } catch (e) {
      return res.status(500).json({ error: e.message });
    }
  }

  // POST: toggle like
  if (req.method === "POST") {
    const { article_id } = req.body || {};
    if (!article_id) return res.status(400).json({ error: "article_id required" });

    try {
      // Check if already liked
      const checkRes = await fetch(
        `${SUPABASE_URL}/rest/v1/article_likes?article_id=eq.${article_id}&fingerprint=eq.${fingerprint}&select=id`,
        { headers }
      );
      const existing = checkRes.ok ? await checkRes.json() : [];

      if (existing.length > 0) {
        // Unlike: remove the like
        await fetch(
          `${SUPABASE_URL}/rest/v1/article_likes?id=eq.${existing[0].id}`,
          { method: "DELETE", headers }
        );

        // Update count
        const countRes = await fetch(
          `${SUPABASE_URL}/rest/v1/article_likes?article_id=eq.${article_id}&select=id`,
          { headers }
        );
        const count = countRes.ok ? (await countRes.json()).length : 0;

        await fetch(
          `${SUPABASE_URL}/rest/v1/articles?id=eq.${article_id}`,
          { method: "PATCH", headers, body: JSON.stringify({ likes_count: count }) }
        );

        return res.status(200).json({ liked: false, count });
      } else {
        // Like: insert
        await fetch(
          `${SUPABASE_URL}/rest/v1/article_likes`,
          { method: "POST", headers, body: JSON.stringify({ article_id, fingerprint }) }
        );

        // Update count
        const countRes = await fetch(
          `${SUPABASE_URL}/rest/v1/article_likes?article_id=eq.${article_id}&select=id`,
          { headers }
        );
        const count = countRes.ok ? (await countRes.json()).length : 0;

        await fetch(
          `${SUPABASE_URL}/rest/v1/articles?id=eq.${article_id}`,
          { method: "PATCH", headers, body: JSON.stringify({ likes_count: count }) }
        );

        return res.status(200).json({ liked: true, count });
      }
    } catch (e) {
      return res.status(500).json({ error: e.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
