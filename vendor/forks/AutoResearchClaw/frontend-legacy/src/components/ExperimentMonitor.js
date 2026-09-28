/**
 * ExperimentMonitor — training curves and experiment metrics.
 */
const ExperimentMonitor = {
  _chart: null,

  async render(container) {
    container.innerHTML = `
      <div class="card">
        <h2>Experiment Metrics</h2>
        <div id="exp-metrics-summary" style="margin-bottom:16px"></div>
        <div class="chart-container">
          <canvas id="metrics-chart"></canvas>
        </div>
      </div>
      <div class="card">
        <h2>Experiment Log</h2>
        <div class="log-viewer" id="exp-log"></div>
      </div>
    `;
    await this.refresh();
  },

  async refresh() {
    try {
      const status = await API.pipelineStatus();
      if (!status.run_id) {
        document.getElementById('exp-metrics-summary').innerHTML =
          '<p style="color:var(--text-muted)">No active run.</p>';
        return;
      }
      const metrics = await API.getMetrics(status.run_id);
      this._renderMetrics(metrics.metrics);
    } catch (e) {
      console.warn('ExperimentMonitor refresh failed:', e);
    }
  },

  _renderMetrics(metrics) {
    const summary = document.getElementById('exp-metrics-summary');
    if (!summary) return;

    if (!metrics || Object.keys(metrics).length === 0) {
      summary.innerHTML = '<p style="color:var(--text-muted)">No metrics available yet.</p>';
      return;
    }

    const items = Object.entries(metrics)
      .filter(([k, v]) => typeof v === 'number')
      .map(([k, v]) => `
        <div class="stat-card">
          <div class="label">${k}</div>
          <div class="value accent" style="font-size:20px">${typeof v === 'number' ? v.toFixed(4) : v}</div>
        </div>
      `).join('');

    summary.innerHTML = `<div class="stats-grid">${items}</div>`;
  },

  onEvent(event) {
    if (event.type === 'metric_update') {
      this._renderMetrics(event.data.metrics);
    }
  }
};
