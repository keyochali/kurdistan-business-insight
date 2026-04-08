const SUPABASE_URL = "https://dgkajtzduagiaohwuilh.supabase.co";
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

  const { password, action, table, data, id } = req.body || {};

  if (password !== process.env.ADMIN_PASSWORD) {
    return res.status(403).json({ error: "Invalid password" });
  }

  if (!SUPABASE_SERVICE_KEY) {
    return res.status(500).json({ error: "Supabase not configured" });
  }

  const headers = {
    apikey: SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${SUPABASE_SERVICE_KEY}`,
    "Content-Type": "application/json",
    Prefer: "return=representation",
  };

  try {
    if (action === "add") {
      const r = await fetch(`${SUPABASE_URL}/rest/v1/${table}`, {
        method: "POST",
        headers,
        body: JSON.stringify(data),
      });
      if (r.ok) {
        const result = await r.json();
        return res.status(200).json({ success: true, data: result });
      }
      const err = await r.json();
      return res.status(r.status).json({ error: err.message || "Insert failed" });
    }

    if (action === "remove") {
      const r = await fetch(`${SUPABASE_URL}/rest/v1/${table}?id=eq.${id}`, {
        method: "DELETE",
        headers,
      });
      return res.status(200).json({ success: true });
    }

    return res.status(400).json({ error: "Invalid action" });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
