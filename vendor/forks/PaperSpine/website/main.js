(() => {
  "use strict";

  document.documentElement.classList.add("js");

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hoverCapable = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const progress = document.querySelector(".scroll-progress span");
  const toast = document.querySelector(".copy-toast");
  const navLinks = [...document.querySelectorAll(".site-header nav a")];
  const locale = document.body.dataset.locale || "zh-CN";
  const manifestPath = document.body.dataset.manifestPath || "downloads/manifest.json";
  let scrollQueued = false;
  let toastTimer = 0;

  const updateScroll = () => {
    const range = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const value = Math.min(1, Math.max(0, window.scrollY / range));
    if (progress) progress.style.transform = `scaleX(${value.toFixed(4)})`;
    scrollQueued = false;
  };

  window.addEventListener("scroll", () => {
    if (!scrollQueued) {
      scrollQueued = true;
      window.requestAnimationFrame(updateScroll);
    }
  }, { passive: true });
  updateScroll();

  const revealItems = [...document.querySelectorAll(".reveal")];
  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  } else {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8%", threshold: .08 });
    revealItems.forEach((item) => revealObserver.observe(item));
  }

  const sections = navLinks
    .map((link) => link.getAttribute("href"))
    .filter((href) => href && href.startsWith("#"))
    .map((href) => document.querySelector(href))
    .filter(Boolean);
  if ("IntersectionObserver" in window) {
    const sectionObserver = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      navLinks.forEach((link) => {
        link.classList.toggle("is-active", link.getAttribute("href") === `#${visible.target.id}`);
      });
    }, { rootMargin: "-25% 0px -60%", threshold: [0, .1, .4] });
    sections.forEach((section) => sectionObserver.observe(section));
  }

  const copyText = async (value) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return;
    }
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    if (!copied) throw new Error("copy failed");
  };

  const showToast = (message) => {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.add("is-visible");
    toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 1800);
  };

  document.querySelectorAll("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = document.getElementById(button.dataset.copyTarget);
      if (!target) return;
      const value = target.textContent.trim();
      try {
        await copyText(value);
        showToast(locale.startsWith("en") ? "AI install instruction copied" : "AI 安装指令已复制");
      } catch (_) {
        showToast(locale.startsWith("en") ? "Copy failed; select the text manually" : "复制失败，请手动选择文本");
      }
    });
  });

  const supportDialog = document.getElementById("support-dialog");
  const supportThanks = document.getElementById("support-thanks");
  const supportOpeners = [...document.querySelectorAll("[data-support-open]")];
  const supportClosers = [...document.querySelectorAll("[data-support-close]")];
  const supportConfirm = document.querySelector("[data-support-confirm]");
  let supportReturnFocus = null;
  let supportThanksTimer = 0;

  const closeSupportDialog = () => {
    if (!supportDialog) return;
    if (typeof supportDialog.close === "function" && supportDialog.open) supportDialog.close();
    else supportDialog.removeAttribute("open");
  };

  const openSupportDialog = (trigger) => {
    if (!supportDialog) return;
    supportReturnFocus = trigger;
    if (typeof supportDialog.showModal === "function") supportDialog.showModal();
    else supportDialog.setAttribute("open", "");
  };

  supportOpeners.forEach((button) => button.addEventListener("click", () => openSupportDialog(button)));
  supportClosers.forEach((button) => button.addEventListener("click", closeSupportDialog));

  if (supportDialog) {
    supportDialog.addEventListener("click", (event) => {
      if (event.target === supportDialog) closeSupportDialog();
    });
    supportDialog.addEventListener("close", () => {
      if (supportReturnFocus instanceof HTMLElement) supportReturnFocus.focus();
    });
  }

  const hideSupportThanks = () => {
    if (!supportThanks) return;
    supportThanks.classList.remove("is-active");
    supportThanks.hidden = true;
  };

  if (supportThanks) {
    supportThanks.addEventListener("animationend", (event) => {
      if (event.target === supportThanks && event.animationName === "support-overlay") hideSupportThanks();
    });
  }

  if (supportConfirm) {
    supportConfirm.addEventListener("click", () => {
      closeSupportDialog();
      if (!supportThanks) return;
      window.clearTimeout(supportThanksTimer);
      supportThanks.hidden = false;
      supportThanks.classList.remove("is-active");
      window.requestAnimationFrame(() => {
        supportThanks.classList.add("is-active");
        supportThanksTimer = window.setTimeout(hideSupportThanks, reduceMotion ? 1800 : 3600);
      });
    });
  }

  if (!reduceMotion && hoverCapable) {
    document.querySelectorAll("[data-tilt]").forEach((card) => {
      card.addEventListener("pointermove", (event) => {
        const rect = card.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - .5;
        const y = (event.clientY - rect.top) / rect.height - .5;
        card.style.setProperty("--tilt-x", `${(-y * 1.4).toFixed(2)}deg`);
        card.style.setProperty("--tilt-y", `${(x * 1.8).toFixed(2)}deg`);
      });
      card.addEventListener("pointerleave", () => {
        card.style.setProperty("--tilt-x", "0deg");
        card.style.setProperty("--tilt-y", "0deg");
      });
    });
  }

  const workflowSteps = [...document.querySelectorAll(".workflow-list li")];
  if ("IntersectionObserver" in window) {
    const workflowObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        workflowSteps.forEach((step) => step.classList.toggle("is-current", step === entry.target));
      });
    }, { rootMargin: "-35% 0px -45%", threshold: .1 });
    workflowSteps.forEach((step) => workflowObserver.observe(step));
  }

  const animateMetric = (node) => {
    const target = Number(node.dataset.count || node.textContent);
    if (!Number.isFinite(target) || reduceMotion) return;
    const started = performance.now();
    const duration = 900;
    const frame = (now) => {
      const raw = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - raw, 3);
      node.textContent = String(Math.round(target * eased));
      if (raw < 1) window.requestAnimationFrame(frame);
    };
    node.textContent = "0";
    window.requestAnimationFrame(frame);
  };

  if (!reduceMotion && "IntersectionObserver" in window) {
    const metricObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        animateMetric(entry.target);
        observer.unobserve(entry.target);
      });
    }, { threshold: .55 });
    document.querySelectorAll("[data-count]").forEach((metric) => metricObserver.observe(metric));
  }

  const formatReleaseBytes = (bytes) => new Intl.NumberFormat(locale).format(bytes);

  const buildInstallPrompt = (manifest, primary) => {
    const manifestUrl = manifest.release_assets?.manifest_url || new URL(manifestPath, window.location.href).href;
    if (locale.startsWith("en")) {
      return `Install PaperSpine5 ${manifest.version} from zero:\n1. Read ${manifestUrl}.\n2. Choose exactly one package for the current host. Prefer ${primary.file} for ordinary Codex or Claude Code Skill installation; use a native host package only when that host integration is required.\n3. Download the selected artifact from its download_url, compute SHA-256, and compare it character-for-character with the manifest. Stop on any mismatch.\n4. Extract into a new persistent directory. Read README.md, INSTALL.md, UPDATE.md, and UNINSTALL.md before changing the host.\n5. For the universal package on Windows/Codex run .\\install.ps1 -Target codex; use -Target claude-code for Claude Code. On macOS/Linux run bash install.sh --host codex or --host claude-code.\n6. Do not overwrite settings.json, config.toml, or unrelated Skills. Ask before installing Python 3 or optional scientific-figure dependencies.\n7. Require runtime health PASS, then open a new task or restart the host and verify PaperSpine5 is discovered.\n8. Launch the 127.0.0.1 workspace only for a real integration_job.json. Never invent a paper job or expose the local server publicly.\n9. Report the URL, bytes, SHA-256, install target, backup, runtime health, host rediscovery, and workspace snapshot separately. Mark every untested layer NOT VERIFIED.`;
    }
    return `请从零开始下载并安装 PaperSpine5 ${manifest.version}：\n1. 读取 ${manifestUrl}；\n2. 根据当前宿主只选择一个包。普通 Codex / Claude Code 优先用 ${primary.file}；需要宿主原生插件时再选对应插件包；\n3. 从 manifest 的 download_url 下载 ZIP，计算 SHA-256，并与 manifest 中同名制品逐字符比较；不一致立即停止；\n4. 解压到新的持久目录，先阅读 README.md、INSTALL.md、UPDATE.md 与 UNINSTALL.md；\n5. 通用包在 Windows/Codex 运行 .\\install.ps1 -Target codex；Claude Code 改为 -Target claude-code。macOS/Linux 运行 bash install.sh --host codex 或 --host claude-code；\n6. 不覆盖 settings.json、config.toml 或无关 Skill；如缺少 Python 3 或可选科研图依赖，先说明来源与改动范围，再征得许可；\n7. 必须确认 runtime health 返回 PASS，并在安装后开启新任务或重启宿主，确认 PaperSpine5 可被发现；\n8. 只有存在真实 integration_job.json 时才启动 127.0.0.1 本地网页；不生成假论文任务，不暴露到公网；\n9. 最后分别报告下载 URL、文件字节数、SHA-256、安装目标、备份、runtime health、宿主重新发现和网页 snapshot。未验证项写 NOT VERIFIED。`;
  };

  const disableReleaseLinks = () => {
    document.querySelectorAll("#primary-download, #artifact-grid a").forEach((link) => {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
    });
    const state = document.getElementById("asset-state");
    if (state) state.textContent = locale.startsWith("en") ? "Manifest unavailable" : "Manifest 不可用";
  };

  const applyReleaseManifest = (manifest) => {
    if (manifest.product !== "PaperSpine5" || manifest.version !== "0.3.0-rc.1" || !Array.isArray(manifest.artifacts) || manifest.artifacts.length !== 4) {
      throw new Error("unexpected release manifest");
    }
    const primary = manifest.artifacts.find((item) => item.kind === "universal-skill");
    if (!primary?.download_url || !primary.sha256 || !Number.isInteger(primary.bytes)) throw new Error("primary artifact is incomplete");
    const primaryLink = document.getElementById("primary-download");
    if (primaryLink) primaryLink.href = primary.download_url;
    document.querySelectorAll("#artifact-grid a[data-artifact-kind]").forEach((link) => {
      const artifact = manifest.artifacts.find((item) => item.kind === link.dataset.artifactKind);
      if (!artifact?.download_url) return;
      link.href = artifact.download_url;
      link.classList.toggle("is-primary", artifact.kind === "universal-skill");
      link.dataset.sha256 = artifact.sha256;
      link.title = `${artifact.file} · ${formatReleaseBytes(artifact.bytes)} bytes · SHA-256 ${artifact.sha256}`;
    });
    const version = document.getElementById("release-version");
    const size = document.getElementById("release-size");
    const manifestLink = document.getElementById("manifest-link");
    const checksumLink = document.getElementById("checksum-link");
    const prompt = document.querySelector("#ai-zero-prompt code");
    const state = document.getElementById("asset-state");
    if (version) version.textContent = `Version · ${manifest.version}`;
    if (size) size.textContent = `ZIP · ${formatReleaseBytes(primary.bytes)} bytes`;
    if (manifestLink && manifest.release_assets?.manifest_url) manifestLink.href = manifest.release_assets.manifest_url;
    if (checksumLink && manifest.release_assets?.checksums_url) checksumLink.href = manifest.release_assets.checksums_url;
    if (prompt) prompt.textContent = buildInstallPrompt(manifest, primary);
    if (state) state.textContent = locale.startsWith("en") ? "Manifest verified" : "Manifest 已载入";
  };

  fetch(manifestPath, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
      return response.json();
    })
    .then(applyReleaseManifest)
    .catch((error) => {
      console.error("PaperSpine5 release manifest failed closed:", error.message);
      disableReleaseLinks();
    });
})();
