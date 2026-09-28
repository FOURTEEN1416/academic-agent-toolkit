/**
 * PaperPreview — render paper markdown/PDF.
 */
const PaperPreview = {
  async render(container) {
    container.innerHTML = `
      <div class="card">
        <h2>Paper Preview</h2>
        <div id="paper-content" style="font-size:14px;line-height:1.8;color:var(--text-secondary)">
          <p>Paper preview will appear here after Stage 17 (Paper Draft) completes.</p>
        </div>
      </div>
    `;
    await this.refresh();
  },

  async refresh() {
    try {
      const status = await API.pipelineStatus();
      if (!status.run_id) return;
      const run = await API.getRun(status.run_id);
      if (run.has_md || run.has_tex) {
        const content = document.getElementById('paper-content');
        if (content) {
          content.innerHTML = `
            <p style="color:var(--success)">Paper generated!</p>
            <p>Run: <code>${run.run_id}</code></p>
            ${run.has_md ? '<p>Markdown: available</p>' : ''}
            ${run.has_tex ? '<p>LaTeX: available</p>' : ''}
            ${run.has_pdf ? '<p>PDF: available</p>' : ''}
          `;
        }
      }
    } catch (e) {
      console.warn('PaperPreview refresh failed:', e);
    }
  },

  onEvent(event) {
    if (event.type === 'paper_ready') {
      this.refresh();
    }
  }
};
