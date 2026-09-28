/**
 * WizardFlow — in-browser setup wizard.
 */
const WizardFlow = {
  _step: 0,
  _config: {},

  render(container) {
    container.innerHTML = `
      <div class="card" style="max-width:600px;margin:0 auto">
        <h2>Setup Wizard</h2>
        <div id="wizard-content"></div>
        <div style="display:flex;justify-content:space-between;margin-top:20px">
          <button id="wiz-back" style="display:none" class="wiz-btn">Back</button>
          <button id="wiz-next" class="wiz-btn primary">Next</button>
        </div>
      </div>
      <style>
        .wiz-btn { padding:8px 20px; border-radius:6px; border:1px solid var(--border);
                   background:var(--bg-tertiary); color:var(--text-primary); cursor:pointer; font-size:14px; }
        .wiz-btn.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
        .wiz-btn:hover { opacity:0.9; }
        .wiz-input { width:100%; padding:10px; background:var(--bg-tertiary); border:1px solid var(--border);
                     border-radius:6px; color:var(--text-primary); font-size:14px; margin-top:8px; }
        .wiz-input:focus { border-color:var(--accent); outline:none; }
        .wiz-option { padding:12px; border:1px solid var(--border); border-radius:6px; margin:6px 0;
                      cursor:pointer; transition:all 0.15s; }
        .wiz-option:hover { border-color:var(--accent); }
        .wiz-option.selected { border-color:var(--accent); background:rgba(88,166,255,0.1); }
      </style>
    `;

    document.getElementById('wiz-next').addEventListener('click', () => this._next());
    document.getElementById('wiz-back').addEventListener('click', () => this._back());
    this._renderStep();
  },

  _steps: [
    {
      title: 'Research Topic',
      html: '<p style="color:var(--text-secondary);margin-bottom:12px">What do you want to research?</p><input class="wiz-input" id="wiz-topic" placeholder="e.g., Domain generalization under distribution shift" />',
      collect: () => ({ topic: document.getElementById('wiz-topic')?.value || '' }),
    },
    {
      title: 'Research Domain',
      html: `<p style="color:var(--text-secondary);margin-bottom:12px">Select your domain:</p>
        <div class="wiz-option" data-value="cv">Computer Vision</div>
        <div class="wiz-option" data-value="nlp">Natural Language Processing</div>
        <div class="wiz-option" data-value="rl">Reinforcement Learning</div>
        <div class="wiz-option" data-value="ml">General ML</div>
        <div class="wiz-option" data-value="ai4science">AI for Science</div>`,
      collect: () => ({ domain: document.querySelector('.wiz-option.selected')?.dataset.value || 'ml' }),
    },
    {
      title: 'Experiment Mode',
      html: `<p style="color:var(--text-secondary);margin-bottom:12px">How should experiments run?</p>
        <div class="wiz-option selected" data-value="docker">Docker (recommended — isolated, GPU support)</div>
        <div class="wiz-option" data-value="simulated">Simulated (quick demo, no real experiments)</div>
        <div class="wiz-option" data-value="sandbox">Local sandbox (runs on host machine)</div>`,
      collect: () => ({ mode: document.querySelector('.wiz-option.selected')?.dataset.value || 'docker' }),
    },
    {
      title: 'Ready!',
      html: '<p style="color:var(--success);font-size:16px">Configuration complete! Click "Finish" to generate your config.</p>',
      collect: () => ({}),
    },
  ],

  _renderStep() {
    const content = document.getElementById('wizard-content');
    const backBtn = document.getElementById('wiz-back');
    const nextBtn = document.getElementById('wiz-next');
    if (!content) return;

    const step = this._steps[this._step];
    content.innerHTML = `<h3 style="margin-bottom:12px">${step.title}</h3>${step.html}`;

    backBtn.style.display = this._step > 0 ? 'block' : 'none';
    nextBtn.textContent = this._step === this._steps.length - 1 ? 'Finish' : 'Next';

    // Add click handlers for options
    content.querySelectorAll('.wiz-option').forEach(opt => {
      opt.addEventListener('click', () => {
        content.querySelectorAll('.wiz-option').forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
      });
    });
  },

  _next() {
    const step = this._steps[this._step];
    Object.assign(this._config, step.collect());

    if (this._step < this._steps.length - 1) {
      this._step++;
      this._renderStep();
    } else {
      this._finish();
    }
  },

  _back() {
    if (this._step > 0) {
      this._step--;
      this._renderStep();
    }
  },

  _finish() {
    const content = document.getElementById('wizard-content');
    if (content) {
      content.innerHTML = `
        <h3>Configuration Generated</h3>
        <pre style="background:var(--bg-primary);padding:12px;border-radius:6px;font-size:13px;overflow-x:auto;margin-top:12px">${JSON.stringify(this._config, null, 2)}</pre>
        <p style="color:var(--text-secondary);margin-top:12px">Copy this to your config.yaml or use the CLI: <code>researchclaw wizard</code></p>
      `;
    }
  },

  onEvent() {}
};
