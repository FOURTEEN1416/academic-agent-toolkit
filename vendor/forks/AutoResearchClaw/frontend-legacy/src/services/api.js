/**
 * REST API client for ResearchClaw.
 */
const API = {
  base: '/api',

  async get(path) {
    const res = await fetch(`${this.base}${path}`);
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return res.json();
  },

  async post(path, body = {}) {
    const res = await fetch(`${this.base}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return res.json();
  },

  // Convenience methods
  health() { return this.get('/health'); },
  config() { return this.get('/config'); },
  pipelineStatus() { return this.get('/pipeline/status'); },
  pipelineStages() { return this.get('/pipeline/stages'); },
  startPipeline(opts) { return this.post('/pipeline/start', opts); },
  stopPipeline() { return this.post('/pipeline/stop'); },
  listRuns() { return this.get('/runs'); },
  getRun(id) { return this.get(`/runs/${id}`); },
  getMetrics(id) { return this.get(`/runs/${id}/metrics`); },
  listProjects() { return this.get('/projects'); },
};
