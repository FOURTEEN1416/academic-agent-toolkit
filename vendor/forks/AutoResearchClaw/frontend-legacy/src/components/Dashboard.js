/**
 * Dashboard component — overview stats and pipeline progress.
 */
const Dashboard = {
  _chart: null,

  async render(container) {
    container.innerHTML = `
      <div class="stats-grid" id="stats-grid"></div>
      <div class="card">
        <h2>Pipeline Progress</h2>
        <div class="progress-bar"><div class="fill" id="progress-fill" style="width:0%"></div></div>
        <div id="progress-text" style="font-size:13px;color:var(--text-secondary);margin-bottom:12px"></div>
        <div class="pipeline-stages" id="pipeline-stages"></div>
      </div>
      <div class="card">
        <h2>Recent Runs</h2>
        <div id="runs-list" style="font-size:14px"></div>
      </div>
    `;
    await this.refresh();
  },

  async refresh() {
    try {
      const [status, stages, runs] = await Promise.all([
        API.pipelineStatus(),
        API.pipelineStages(),
        API.listRuns(),
      ]);
      this._renderStats(status);
      this._renderStages(stages.stages, status);
      this._renderRuns(runs.runs);
    } catch (e) {
      console.warn('Dashboard refresh failed:', e);
    }
  },

  _renderStats(status) {
    const grid = document.getElementById('stats-grid');
    if (!grid) return;
    const stage = status.current_stage || 0;
    const s = status.status || 'idle';
    grid.innerHTML = `
      <div class="stat-card">
        <div class="label">Status</div>
        <div class="value ${s === 'running' ? 'accent' : s === 'completed' ? 'success' : ''}">${s}</div>
      </div>
      <div class="stat-card">
        <div class="label">Current Stage</div>
        <div class="value accent">${stage}/23</div>
      </div>
      <div class="stat-card">
        <div class="label">Run ID</div>
        <div class="value" style="font-size:14px">${status.run_id || '—'}</div>
      </div>
      <div class="stat-card">
        <div class="label">Topic</div>
        <div class="value" style="font-size:14px">${status.topic || '—'}</div>
      </div>
    `;
  },

  _renderStages(stages, status) {
    const el = document.getElementById('pipeline-stages');
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    if (!el) return;

    const current = status.current_stage || 0;
    const pct = Math.round((current / 23) * 100);
    if (fill) fill.style.width = `${pct}%`;
    if (text) text.textContent = `${current}/23 stages (${pct}%)`;

    el.innerHTML = stages.map(s => {
      let cls = '';
      if (s.number < current) cls = 'done';
      else if (s.number === current && status.status === 'running') cls = 'running';
      return `<div class="stage-cell ${cls}">
        <div class="stage-num">${s.number}</div>
        <div class="stage-name">${s.name.replace(/_/g, ' ')}</div>
      </div>`;
    }).join('');
  },

  _renderRuns(runs) {
    const el = document.getElementById('runs-list');
    if (!el) return;
    if (!runs || !runs.length) {
      el.innerHTML = '<p style="color:var(--text-muted)">No runs found.</p>';
      return;
    }
    el.innerHTML = runs.slice(0, 10).map(r => `
      <div style="padding:8px 0;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px">
        <span style="font-family:var(--font-mono);font-size:13px;color:var(--accent)">${r.run_id}</span>
        <span class="status-badge ${r.checkpoint?.status || 'idle'}">${r.checkpoint?.status || 'unknown'}</span>
        <span style="color:var(--text-muted);font-size:12px">${r.checkpoint?.stage_name || ''}</span>
      </div>
    `).join('');
  },

  onEvent(event) {
    if (['stage_complete', 'stage_start', 'pipeline_started', 'pipeline_completed',
         'run_discovered', 'run_status_changed'].includes(event.type)) {
      this.refresh();
    }
  }
};
