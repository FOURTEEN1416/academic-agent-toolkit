/**
 * PipelineView — detailed 23-stage visualization.
 */
const PipelineView = {
  _stages: null,

  async render(container) {
    container.innerHTML = `
      <div class="card">
        <h2>23-Stage Research Pipeline</h2>
        <p style="color:var(--text-secondary);margin-bottom:16px">
          Each stage is executed sequentially. Gate stages require approval.
        </p>
        <div id="pipeline-detail"></div>
      </div>
    `;
    await this.refresh();
  },

  async refresh() {
    try {
      const [stagesDef, status] = await Promise.all([
        API.pipelineStages(),
        API.pipelineStatus(),
      ]);
      this._stages = stagesDef.stages;
      this._renderDetail(status);
    } catch (e) {
      console.warn('PipelineView refresh failed:', e);
    }
  },

  _renderDetail(status) {
    const el = document.getElementById('pipeline-detail');
    if (!el || !this._stages) return;
    const current = status.current_stage || 0;

    const phases = {};
    this._stages.forEach(s => {
      const p = s.phase || 'Other';
      if (!phases[p]) phases[p] = [];
      phases[p].push(s);
    });

    el.innerHTML = Object.entries(phases).map(([phase, stages]) => `
      <div style="margin-bottom:20px">
        <h3 style="font-size:13px;color:var(--purple);margin-bottom:8px">Phase ${phase}</h3>
        <div style="display:flex;flex-wrap:wrap;gap:8px">
          ${stages.map(s => {
            let cls = '';
            if (s.number < current) cls = 'done';
            else if (s.number === current && status.status === 'running') cls = 'running';
            return `<div class="stage-cell ${cls}" style="min-width:160px;text-align:left">
              <div class="stage-num" style="display:inline">${s.number}.</div>
              <span class="stage-name" style="display:inline">${s.label || s.name.replace(/_/g, ' ')}</span>
            </div>`;
          }).join('')}
        </div>
      </div>
    `).join('');
  },

  onEvent(event) {
    if (['stage_complete', 'stage_start', 'stage_fail'].includes(event.type)) {
      this.refresh();
    }
  }
};
