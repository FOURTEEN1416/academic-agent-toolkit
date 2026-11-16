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
  const supportMethods = [...document.querySelectorAll("[data-support-method]")];
  const supportCards = [...document.querySelectorAll("[data-support-card]")];
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
  if (new URLSearchParams(window.location.search).get("support") === "1") {
    window.requestAnimationFrame(() => openSupportDialog(supportOpeners[0] || null));
  }
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

  supportMethods.forEach((method) => method.addEventListener("click", () => {
    const selected = method.dataset.supportMethod;
    supportMethods.forEach((item) => {
      const active = item === method;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-selected", String(active));
    });
    supportCards.forEach((card) => {
      const active = card.dataset.supportCard === selected;
      card.classList.toggle("is-active", active);
      card.hidden = !active;
    });
  }));

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
      return `Install PaperSpine5 ${manifest.version} from zero:\n1. Read ${manifestUrl}.\n2. Default to a full platform suite: detect the operating system and CPU, then select the exactly matching Windows x64, Linux x86_64, macOS arm64, or macOS x86_64 suite. This release provides only full platform suites; the historical Skill-only archive lacks the Web core and runtime.\n3. Download the selected artifact from its download_url, compute SHA-256, and compare both the digest and byte count character-for-character with the manifest. Stop on any mismatch.\n4. Read README.md, INSTALL.md, UPDATE.md, and UNINSTALL.md before changing the host.\n5. On Windows x64 run: powershell -ExecutionPolicy Bypass -File .\\install.ps1 -Target codex -CleanLegacy. On macOS/Linux run: sh ./install.sh --target codex --clean-legacy. Use the documented Claude Code or both-host target if requested.\n6. Do not overwrite settings.json, config.toml, or unrelated Skills. The self-contained suites must not install a system Python.\n7. Require first-start REST/MCP READY, then restart the host and verify paper-spine is discovered.\n8. When the user starts paper work, the installed paper-spine Skill creates or resumes the same public task and opens its bound 127.0.0.1 workbench URL. Let the user save configuration there and have the host read it back before proceeding. Do not create a sample paper task as an installation test or expose the local server publicly.\n9. Report the URL, platform, bytes, SHA-256, install target, backup, runtime health, host rediscovery, and workspace snapshot separately. Mark every untested layer NOT VERIFIED. macOS is unsigned and unnotarized; Linux support is glibc x86_64 only.`;
    }
    return `请从零开始下载并安装 PaperSpine5 ${manifest.version}：\n1. 读取 ${manifestUrl}；\n2. 默认安装平台套件：识别操作系统与 CPU，并选择完全匹配的 Windows x64、Linux x86_64、macOS arm64 或 macOS x86_64 套件；本次发布只提供完整平台套件，历史独立 Skill 包缺少 Web 核心和运行时，不用于安装；\n3. 从 manifest 的 download_url 下载制品，同时核对字节数和 SHA-256；任一不一致立即停止；\n4. 改动宿主前先阅读 README.md、INSTALL.md、UPDATE.md 与 UNINSTALL.md；\n5. Windows x64 运行 powershell -ExecutionPolicy Bypass -File .\\install.ps1 -Target codex -CleanLegacy；macOS/Linux 运行 sh ./install.sh --target codex --clean-legacy；如需 Claude Code 或双宿主，使用文档中的对应 target；\n6. 不覆盖 settings.json、config.toml 或无关 Skill；自包含 suite 不应安装系统 Python；\n7. 必须确认 first-start 的 REST/MCP READY，重启宿主后确认发现 paper-spine；\n8. 用户开始论文工作时，由已安装的 paper-spine Skill 创建或恢复同一公开任务，打开其绑定的 127.0.0.1 工作台链接；用户保存配置后，宿主读回再继续。不为安装自检创建演示论文任务，不把服务暴露到公网；\n9. 分别报告下载 URL、平台、字节数、SHA-256、安装目标、备份、runtime health、宿主重新发现和网页 snapshot。未验证项写 NOT VERIFIED。macOS 尚未签名和 notarize；Linux 仅声明 glibc x86_64。`;
  };

  const disableReleaseLinks = () => {
    document.querySelectorAll("#primary-download, [data-artifact-kind]").forEach((link) => {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
    });
    const state = document.getElementById("asset-state");
    if (state) state.textContent = locale.startsWith("en") ? "Manifest unavailable" : "Manifest 不可用";
  };

  const applyReleaseManifest = (manifest) => {
    if (manifest.product !== "PaperSpine5" || !manifest.version || !Array.isArray(manifest.artifacts) || manifest.artifacts.length < 2) {
      throw new Error("unexpected release manifest");
    }
    const primary = manifest.artifacts.find((item) => item.kind === "suite");
    if (!primary?.download_url || !primary.sha256 || !Number.isInteger(primary.bytes)) throw new Error("primary suite artifact is incomplete");
    const primaryLink = document.getElementById("primary-download");
    if (primaryLink) {
      primaryLink.href = primary.download_url;
      primaryLink.removeAttribute("aria-disabled");
    }
    document.querySelectorAll("[data-artifact-kind]").forEach((link) => {
      const artifact = manifest.artifacts.find((item) => item.kind === link.dataset.artifactKind);
      if (!artifact?.download_url || !artifact.sha256 || !Number.isInteger(artifact.bytes)) {
        link.removeAttribute("href");
        link.setAttribute("aria-disabled", "true");
        return;
      }
      link.href = artifact.download_url;
      link.removeAttribute("aria-disabled");
      link.classList.toggle("is-primary", artifact.kind === "suite");
      link.dataset.sha256 = artifact.sha256;
      link.title = `${artifact.file} · ${formatReleaseBytes(artifact.bytes)} bytes · SHA-256 ${artifact.sha256}`;
    });
    document.querySelectorAll("[data-artifact-size]").forEach((node) => {
      const artifact = manifest.artifacts.find((item) => item.kind === node.dataset.artifactSize);
      if (Number.isInteger(artifact?.bytes)) node.textContent = `${(artifact.bytes / 1000000).toFixed(2)} MB`;
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
