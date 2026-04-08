export default async function handler(req, res) {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

  const { password, mode } = req.body || {};

  // Verify admin password
  if (password !== process.env.ADMIN_PASSWORD) {
    return res.status(403).json({ error: "Invalid password" });
  }

  if (!["scrape", "regenerate"].includes(mode)) {
    return res.status(400).json({ error: "Invalid mode. Use 'scrape' or 'regenerate'." });
  }

  const ghToken = process.env.GITHUB_TOKEN;
  if (!ghToken) {
    return res.status(500).json({ error: "GitHub token not configured" });
  }

  try {
    const response = await fetch(
      "https://api.github.com/repos/keyochali/kurdistan-business-insight/actions/workflows/pipeline.yml/dispatches",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${ghToken}`,
          Accept: "application/vnd.github.v3+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ref: "master",
          inputs: { mode },
        }),
      }
    );

    if (response.status === 204) {
      return res.status(200).json({ success: true, message: "Pipeline triggered!" });
    } else {
      const err = await response.text();
      return res.status(response.status).json({ error: `GitHub API error: ${err}` });
    }
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
