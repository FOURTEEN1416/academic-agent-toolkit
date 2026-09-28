/**
 * ResearchClaw SPA — main application entry point.
 */
(function () {
  'use strict';

  // View registry
  const views = {
    dashboard: Dashboard,
    pipeline: PipelineView,
    chat: ChatPanel,
    experiments: ExperimentMonitor,
    paper: PaperPreview,
    projects: ProjectList,
    wizard: WizardFlow,
  };

  let currentView = 'dashboard';

  function navigateTo(viewName) {
    if (!views[viewName]) return;
    currentView = viewName;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.view === viewName);
    });

    // Render view
    const main = document.getElementById('main-content');
    if (main) {
      const view = views[viewName];
      if (view.render) {
        view.render(main);
      }
    }
  }

  // Init
  document.addEventListener('DOMContentLoaded', async () => {
    // Bind navigation
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo(el.dataset.view);
      });
    });

    // Connect events WebSocket
    eventsWS.on('open', () => {
      const badge = document.getElementById('connection-badge');
      if (badge) {
        badge.textContent = 'Connected';
        badge.className = 'status-badge running';
      }
    });

    eventsWS.on('close', () => {
      const badge = document.getElementById('connection-badge');
      if (badge) {
        badge.textContent = 'Disconnected';
        badge.className = 'status-badge failed';
      }
    });

    // Route events to active view
    eventsWS.on('message', (data) => {
      const view = views[currentView];
      if (view && view.onEvent) {
        view.onEvent(data);
      }

      // Browser notifications
      if (Notification.permission === 'granted') {
        if (data.type === 'pipeline_completed') {
          new Notification('ResearchClaw', { body: 'Pipeline completed!' });
        } else if (data.type === 'stage_fail') {
          new Notification('ResearchClaw', { body: `Stage failed: ${data.data?.current_stage_name || ''}` });
        }
      }
    });

    eventsWS.connect();

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    // Load initial view
    navigateTo('dashboard');

    // Update header status
    try {
      const health = await API.health();
      const statusEl = document.getElementById('server-status');
      if (statusEl) statusEl.textContent = `v${health.version}`;
    } catch (e) {
      console.warn('Health check failed:', e);
    }
  });
})();
