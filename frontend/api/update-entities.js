const REPO = "keyochali/kurdistan-business-insight";

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

  const { password, profiles, companies } = req.body || {};

  if (password !== process.env.ADMIN_PASSWORD) {
    return res.status(403).json({ error: "Invalid password" });
  }

  const ghToken = process.env.GITHUB_TOKEN;
  if (!ghToken) return res.status(500).json({ error: "GitHub token not configured" });

  const headers = {
    Authorization: `Bearer ${ghToken}`,
    Accept: "application/vnd.github.v3+json",
    "Content-Type": "application/json",
  };

  try {
    // 1. Get current data.json from repo
    const dataRes = await fetch(
      `https://api.github.com/repos/${REPO}/contents/frontend/public/data.json`,
      { headers }
    );
    if (!dataRes.ok) return res.status(500).json({ error: "Failed to fetch data.json" });

    const dataFile = await dataRes.json();
    const currentData = JSON.parse(Buffer.from(dataFile.content, "base64").toString("utf-8"));

    // 2. Update profiles and companies
    currentData.profiles = profiles;
    currentData.companies = companies;

    // 3. Also update profiles.json and companies.json for the pipeline
    const profilesJson = profiles
      .filter((p) => p.is_active !== false)
      .map((p) => ({ name: p.name, url: p.linkedin_url }));
    const companiesJson = companies
      .filter((c) => c.is_active !== false)
      .map((c) => ({ name: c.name, url: c.linkedin_url }));

    // 4. Commit data.json
    const newContent = Buffer.from(JSON.stringify(currentData)).toString("base64");
    await fetch(
      `https://api.github.com/repos/${REPO}/contents/frontend/public/data.json`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify({
          message: `Update profiles and companies`,
          content: newContent,
          sha: dataFile.sha,
        }),
      }
    );

    // 5. Commit profiles.json
    const profRes = await fetch(
      `https://api.github.com/repos/${REPO}/contents/data/profiles.json`,
      { headers }
    );
    if (profRes.ok) {
      const profFile = await profRes.json();
      await fetch(
        `https://api.github.com/repos/${REPO}/contents/data/profiles.json`,
        {
          method: "PUT",
          headers,
          body: JSON.stringify({
            message: "Update profiles.json",
            content: Buffer.from(JSON.stringify(profilesJson, null, 2)).toString("base64"),
            sha: profFile.sha,
          }),
        }
      );
    }

    // 6. Commit companies.json
    const compRes = await fetch(
      `https://api.github.com/repos/${REPO}/contents/data/companies.json`,
      { headers }
    );
    if (compRes.ok) {
      const compFile = await compRes.json();
      await fetch(
        `https://api.github.com/repos/${REPO}/contents/data/companies.json`,
        {
          method: "PUT",
          headers,
          body: JSON.stringify({
            message: "Update companies.json",
            content: Buffer.from(JSON.stringify(companiesJson, null, 2)).toString("base64"),
            sha: compFile.sha,
          }),
        }
      );
    }

    return res.status(200).json({ success: true, message: "Profiles and companies saved to repo" });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
