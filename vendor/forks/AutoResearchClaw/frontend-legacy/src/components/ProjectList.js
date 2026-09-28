/**
 * ProjectList — browse and manage research projects.
 */
const ProjectList = {
  async render(container) {
    container.innerHTML = `
      <div class="card">
        <h2>Projects</h2>
        <div id="project-list"></div>
      </div>
    `;
    await this.refresh();
  },

  async refresh() {
    try {
      const data = await API.listProjects();
      this._renderList(data.projects);
    } catch (e) {
      console.warn('ProjectList refresh failed:', e);
    }
  },

  _renderList(projects) {
    const el = document.getElementById('project-list');
    if (!el) return;
    if (!projects || !projects.length) {
      el.innerHTML = '<p style="color:var(--text-muted)">No projects found. Start a pipeline run first.</p>';
      return;
    }
    el.innerHTML = projects.map(p => `
      <div style="padding:12px;border:1px solid var(--border);border-radius:var(--radius);margin-bottom:8px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-family:var(--font-mono);color:var(--accent)">${p.id}</span>
          <span class="status-badge ${p.status}">${p.status}</span>
        </div>
        ${p.current_stage ? `<div style="font-size:12px;color:var(--text-muted);margin-top:4px">Stage: ${p.current_stage}</div>` : ''}
      </div>
    `).join('');
  },

  onEvent(event) {
    if (['run_discovered', 'pipeline_completed'].includes(event.type)) {
      this.refresh();
    }
  }
};
