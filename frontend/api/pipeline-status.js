const REPO = "keyochali/kurdistan-business-insight";

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });

  const ghToken = process.env.GITHUB_TOKEN;
  if (!ghToken) return res.status(500).json({ error: "GitHub token not configured" });

  const headers = {
    Authorization: `Bearer ${ghToken}`,
    Accept: "application/vnd.github.v3+json",
  };

  try {
    // Get the latest workflow run
    const runsRes = await fetch(
      `https://api.github.com/repos/${REPO}/actions/runs?per_page=1`,
      { headers }
    );

    if (!runsRes.ok) return res.status(200).json({ status: "unknown" });

    const runsData = await runsRes.json();
    const run = runsData.workflow_runs?.[0];
    if (!run) return res.status(200).json({ status: "idle" });

    const result = {
      status: run.status,           // queued | in_progress | completed
      conclusion: run.conclusion,   // success | failure | null (while running)
      started_at: run.created_at,
      updated_at: run.updated_at,
      url: run.html_url,
      run_id: run.id,
      elapsed_seconds: Math.round((Date.now() - new Date(run.created_at).getTime()) / 1000),
      steps: [],
    };

    // If the run is active, fetch job steps for detailed progress
    if (run.status === "in_progress" || run.status === "queued") {
      const jobsRes = await fetch(
        `https://api.github.com/repos/${REPO}/actions/runs/${run.id}/jobs`,
        { headers }
      );

      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        const job = jobsData.jobs?.[0];

        if (job && job.steps) {
          result.steps = job.steps.map((step) => ({
            name: step.name,
            status: step.status,         // queued | in_progress | completed
            conclusion: step.conclusion, // success | failure | skipped | null
            started_at: step.started_at,
            completed_at: step.completed_at,
          }));

          // Calculate progress
          const total = job.steps.length;
          const completed = job.steps.filter((s) => s.status === "completed").length;
          const current = job.steps.find((s) => s.status === "in_progress");

          result.progress = {
            total,
            completed,
            percent: Math.round((completed / total) * 100),
            current_step: current?.name || null,
          };
        }
      }
    }

    // If completed, also get the final step results
    if (run.status === "completed") {
      const jobsRes = await fetch(
        `https://api.github.com/repos/${REPO}/actions/runs/${run.id}/jobs`,
        { headers }
      );
      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        const job = jobsData.jobs?.[0];
        if (job && job.steps) {
          result.steps = job.steps.map((step) => ({
            name: step.name,
            status: step.status,
            conclusion: step.conclusion,
          }));
          result.progress = {
            total: job.steps.length,
            completed: job.steps.length,
            percent: 100,
            current_step: null,
          };
        }
      }
    }

    return res.status(200).json(result);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
