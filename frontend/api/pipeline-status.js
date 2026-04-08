export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });

  const ghToken = process.env.GITHUB_TOKEN;
  if (!ghToken) {
    return res.status(500).json({ error: "GitHub token not configured" });
  }

  try {
    const response = await fetch(
      "https://api.github.com/repos/keyochali/kurdistan-business-insight/actions/runs?per_page=1",
      {
        headers: {
          Authorization: `Bearer ${ghToken}`,
          Accept: "application/vnd.github.v3+json",
        },
      }
    );

    if (response.ok) {
      const data = await response.json();
      const run = data.workflow_runs?.[0];
      if (run) {
        return res.status(200).json({
          status: run.status,
          conclusion: run.conclusion,
          started_at: run.created_at,
          name: run.name,
          url: run.html_url,
        });
      }
    }

    return res.status(200).json({ status: "unknown" });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
