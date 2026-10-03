/**
 * ClinRESET — Frontend Client Controller
 *
 * Implements a strict single-source-of-truth state machine (setView) for:
 *   - "idle": Only upload drop-zone visible
 *   - "processing": Drop-zone hidden, processing spinner and cosmetic progress visible
 *   - "done": Results view rendered, upload panel hidden
 *   - "error": Error card visible with specific server/client error message
 */

(function () {
  'use strict';

  // DOM Elements
  const uploadView = document.getElementById('upload-view');
  const resultsView = document.getElementById('results-view');
  const dropZone = document.getElementById('drop-zone');
  const pdfInput = document.getElementById('pdf-input');
  const btnBrowse = document.getElementById('btn-browse');
  const processingState = document.getElementById('processing-state');
  const statusText = document.getElementById('status-text');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const errorState = document.getElementById('error-state');
  const errorMessage = document.getElementById('error-message');
  const btnRetry = document.getElementById('btn-retry');
  const btnReset = document.getElementById('btn-reset');

  // State
  let _lastReport = null;   // Holds the last processed report for export
  let _lastFilename = null; // Holds the last uploaded filename

  const reportMetaHeader = document.getElementById('report-meta-header');
  const alertLegendBar = document.getElementById('alert-legend-bar');
  const legendHeader = document.getElementById('legend-header');
  const btnLegendToggle = document.getElementById('btn-legend-toggle');
  const reportSummaryContainer = document.getElementById('report-summary-container');
  const secSummary = document.getElementById('sec-summary');
  const keyFindingsContainer = document.getElementById('key-findings-container');
  const measurementsContainer = document.getElementById('measurements-container');
  const contextContainer = document.getElementById('context-container');
  const limitationsList = document.getElementById('limitations-list');

  // Timers and state variables
  let pollInterval = null;
  let cosmeticTimer = null;
  let currentJobId = null;

  /* ==========================================================================
     DOM VISIBILITY HELPERS
     Strictly toggle both HTML5 'hidden' attribute and '.is-hidden' / '.hidden'
     ========================================================================== */
  function showElement(el) {
    if (!el) return;
    el.removeAttribute('hidden');
    el.classList.remove('hidden', 'is-hidden');
  }

  function hideElement(el) {
    if (!el) return;
    el.setAttribute('hidden', '');
    el.classList.add('is-hidden');
    el.classList.add('hidden');
  }

  /* ==========================================================================
     COSMETIC STATUS ROTATION
     NOTE: The labels below represent a client-side timed sequence of steps
     for visual user feedback while the backend asynchronously executes the
     synchronous extraction and reporting pipeline.
     ========================================================================== */
  const COSMETIC_STEPS = [
    { text: 'Extracting document text & tables (PyMuPDF4LLM)...', progress: '25%' },
    { text: 'Classifying document type (Rule-based signature)...', progress: '45%' },
    { text: 'Extracting clinical entities & terminology normalization...', progress: '65%' },
    { text: 'Evaluating reference intervals & clinical significance...', progress: '85%' },
    { text: 'Generating deterministic explanations & final report...', progress: '95%' },
  ];

  function startCosmeticProgress() {
    stopCosmeticProgress();
    let stepIndex = 0;
    if (statusText) statusText.textContent = COSMETIC_STEPS[0].text;
    if (progressBarFill) progressBarFill.style.width = COSMETIC_STEPS[0].progress;

    cosmeticTimer = setInterval(() => {
      stepIndex++;
      if (stepIndex < COSMETIC_STEPS.length) {
        if (statusText) statusText.style.opacity = '0';
        setTimeout(() => {
          if (statusText) {
            statusText.textContent = COSMETIC_STEPS[stepIndex].text;
            statusText.style.opacity = '1';
          }
          if (progressBarFill) {
            progressBarFill.style.width = COSMETIC_STEPS[stepIndex].progress;
          }
        }, 200);
      }
    }, 2800);
  }

  function stopCosmeticProgress() {
    if (cosmeticTimer) {
      clearInterval(cosmeticTimer);
      cosmeticTimer = null;
    }
  }

  /* ==========================================================================
     VIEW STATE MACHINE (Single Source of Truth)
     States: "idle" | "processing" | "done" | "error"
     ========================================================================== */
  let currentViewState = 'idle';

  function setView(state, payload) {
    currentViewState = state;

    switch (state) {
      case 'idle':
        stopPolling();
        stopCosmeticProgress();
        if (pdfInput) pdfInput.value = '';

        // Upload view active, Results view hidden
        showElement(uploadView);
        hideElement(resultsView);

        // Within upload view: ONLY drop-zone visible; processing & error hidden
        showElement(dropZone);
        hideElement(processingState);
        hideElement(errorState);
        break;

      case 'processing':
        // Upload view panel remains active; results panel is hidden
        showElement(uploadView);
        hideElement(resultsView);

        // Within upload view: drop-zone and error hidden; processing visible
        hideElement(dropZone);
        hideElement(errorState);
        showElement(processingState);

        startCosmeticProgress();
        break;

      case 'done':
        stopPolling();
        stopCosmeticProgress();

        // Switch panels: upload panel hidden, results panel visible
        hideElement(uploadView);
        showElement(resultsView);

        if (payload) {
          renderFinalReport(payload);
        }
        break;

      case 'error':
        stopPolling();
        stopCosmeticProgress();

        // Upload view panel remains active; results panel hidden
        showElement(uploadView);
        hideElement(resultsView);

        // Within upload view: drop-zone and processing hidden; error visible
        hideElement(dropZone);
        hideElement(processingState);
        showElement(errorState);

        if (errorMessage) {
          errorMessage.textContent = payload || 'An unexpected error occurred during processing.';
        }
        break;

      default:
        console.warn('Unknown view state requested:', state);
    }
  }

  /* ==========================================================================
     FILE UPLOAD & DRAG-AND-DROP
     ========================================================================== */
  if (btnBrowse && pdfInput) {
    btnBrowse.addEventListener('click', (e) => {
      e.stopPropagation();
      pdfInput.click();
    });
  }

  if (dropZone && pdfInput) {
    dropZone.addEventListener('click', () => pdfInput.click());

    ['dragenter', 'dragover'].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        handleFileUpload(files[0]);
      }
    });

    pdfInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
      }
    });
  }

  if (btnRetry) {
    btnRetry.addEventListener('click', () => setView('idle'));
  }
  if (btnReset) {
    btnReset.addEventListener('click', () => setView('idle'));
  }

  // Minimizable Legend Toggle Handler
  function toggleLegend(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!alertLegendBar) return;
    const isCollapsed = alertLegendBar.classList.toggle('collapsed');
    const resultsSidebar = document.getElementById('results-sidebar');
    if (resultsSidebar) {
      resultsSidebar.classList.toggle('legend-collapsed', isCollapsed);
    }
    if (legendHeader) {
      legendHeader.setAttribute('aria-expanded', String(!isCollapsed));
      legendHeader.setAttribute('title', isCollapsed ? 'Click to expand legend' : 'Click to minimize legend');
    }
    if (btnLegendToggle) {
      btnLegendToggle.setAttribute('aria-expanded', String(!isCollapsed));
      btnLegendToggle.setAttribute('title', isCollapsed ? 'Expand legend' : 'Minimize legend');
    }
  }

  if (legendHeader) {
    legendHeader.addEventListener('click', toggleLegend);
    legendHeader.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        toggleLegend(e);
      }
    });
  }

  if (alertLegendBar) {
    alertLegendBar.addEventListener('click', (e) => {
      if (alertLegendBar.classList.contains('collapsed')) {
        toggleLegend(e);
      }
    });
  }

  // Section Minimize / Maximize Controllers
  function initSectionNav() {
    const sectionNavBtns = document.querySelectorAll('.section-nav-btn');
    sectionNavBtns.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const targetId = btn.getAttribute('data-section');
        if (!targetId) return;
        const targetSection = document.getElementById(targetId);
        if (!targetSection) return;

        const isMinimized = targetSection.classList.toggle('is-minimized');
        btn.classList.toggle('is-minimized', isMinimized);

        const dot = btn.querySelector('.sec-nav-dot');
        if (dot) {
          dot.setAttribute('title', isMinimized ? 'Section Minimized' : 'Section Visible');
        }

        // If expanding, smooth scroll to it
        if (!isMinimized) {
          targetSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });
    });

    // Also allow clicking directly on a minimized section header to expand it
    document.querySelectorAll('.results-section').forEach((sec) => {
      const titleWrap = sec.querySelector('.section-title-wrap');
      if (titleWrap) {
        titleWrap.addEventListener('click', () => {
          if (sec.classList.contains('is-minimized')) {
            sec.classList.remove('is-minimized');
            const matchingBtn = document.querySelector(`.section-nav-btn[data-section="${sec.id}"]`);
            if (matchingBtn) {
              matchingBtn.classList.remove('is-minimized');
            }
          }
        });
      }
    });
  }

  initSectionNav();

  async function handleFileUpload(file) {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setView('error', 'Please upload a valid PDF document (.pdf format).');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    _lastFilename = file.name;

    try {
      const response = await fetch('/api/reports', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Upload failed (Status ${response.status})`);
      }

      const data = await response.json();
      currentJobId = data.job_id;

      // REQUIREMENT: Processing section ONLY becomes visible AFTER
      // a successful POST to /api/reports returns a job_id!
      setView('processing');
      startPolling(currentJobId);
    } catch (err) {
      setView('error', err.message || 'Network error while uploading report.');
    }
  }

  /* ==========================================================================
     STATUS POLLING
     ========================================================================== */
  function startPolling(jobId) {
    stopPolling();
    pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/reports/${jobId}`);
        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to check status (Status ${response.status})`);
        }
        const data = await response.json();

        if (data.status === 'done') {
          stopPolling();
          stopCosmeticProgress();
          if (progressBarFill) progressBarFill.style.width = '100%';
          // Save to history before switching view
          if (data.result) {
            saveToHistory(data.result, _lastFilename);
          }
          setTimeout(() => {
            setView('done', data.result);
          }, 350);
        } else if (data.status === 'failed') {
          setView('error', data.error || 'The analysis pipeline failed to complete.');
        }
      } catch (err) {
        setView('error', err.message || 'Connection lost while checking report status.');
      }
    }, 1500);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  /* ==========================================================================
     REPORT RENDERING (Top to Bottom order strictly matching specification)
     ========================================================================== */
  function renderFinalReport(report) {
    if (!report) return;
    _lastReport = report;

    // Reset all sections and nav buttons to expanded state
    document.querySelectorAll('.results-section').forEach((sec) => sec.classList.remove('is-minimized'));
    document.querySelectorAll('.section-nav-btn').forEach((btn) => btn.classList.remove('is-minimized'));

    // 1. Header (report_type + status from report_summary)
    renderHeader(report.report_summary || {});

    // 2. Export toolbar
    renderExportToolbar(report);

    // 2.5 Overall Report Summary
    renderOverallSummary(report.report_summary || {});

    // 3. Key Findings
    renderKeyFindings(report.key_findings || []);

    // 4. Measurements of Interest (with SVG range bars)
    renderMeasurements(report.measurements_of_interest || []);

    // 5. Contextual Relationships
    renderContext(report.context || []);

    // 6. Limitations (persistent disclaimer block)
    renderLimitations(report.limitations || []);
  }

  function renderHeader(summary) {
    if (!reportMetaHeader) return;
    const historyBtn = `<button class="btn-history-nav" id="btn-history-nav" title="View report history">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="10"/></svg>
      History
    </button>`;
    reportMetaHeader.innerHTML = `
      <div class="report-type-badge">${escapeHtml(summary.report_type || 'MEDICAL REPORT')}</div>
      <div class="report-confidence-badge">Status: ${escapeHtml(summary.status || 'CONFIDENT')}</div>
      ${historyBtn}
    `;
    const btnHistNav = document.getElementById('btn-history-nav');
    if (btnHistNav) btnHistNav.addEventListener('click', showHistoryPage);
  }

  function renderOverallSummary(summary) {
    if (!reportSummaryContainer || !secSummary) return;
    
    if (summary.overall_summary) {
      reportSummaryContainer.innerHTML = `<p>${escapeHtml(summary.overall_summary)}</p>`;
      showElement(secSummary);
      const navBtn = document.querySelector('.section-nav-btn[data-section="sec-summary"]');
      if (navBtn) showElement(navBtn);
    } else {
      hideElement(secSummary);
      const navBtn = document.querySelector('.section-nav-btn[data-section="sec-summary"]');
      if (navBtn) hideElement(navBtn);
    }
  }

  function renderKeyFindings(findings) {
    if (!keyFindingsContainer) return;
    keyFindingsContainer.innerHTML = '';
    if (findings.length === 0) {
      keyFindingsContainer.innerHTML = '<p class="section-subtitle">No qualitative findings extracted.</p>';
      return;
    }

    findings.forEach((finding) => {
      const alertClass = getAlertClass(finding.alert_level);
      const card = document.createElement('div');
      card.className = `finding-card ${alertClass}`;

      // Confidence pill
      const conf = finding.confidence !== undefined ? finding.confidence : null;
      let confPill = '';
      if (conf !== null) {
        const pct = Math.round(conf * 100);
        const tier = conf >= 0.75 ? 'high' : conf >= 0.45 ? 'medium' : 'low';
        confPill = `<span class="confidence-pill ${tier}" title="Extraction confidence">${pct}%</span>`;
      }

      card.innerHTML = `
        <div class="card-header-row">
          <div class="concept-title">${escapeHtml(finding.concept)}</div>
          <div style="display:flex;gap:6px;align-items:center">
            ${confPill}
            <span class="assertion-pill">${escapeHtml(finding.assertion || 'PRESENT')}</span>
          </div>
        </div>
        <div class="finding-explanation">${expandAbbreviations(escapeHtml(finding.explanation || 'No explanation generated.'))}</div>
        <div class="finding-basis">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
          </svg>
          <span>${escapeHtml(finding.basis || 'Evaluated from source assertion')}</span>
        </div>
      `;
      keyFindingsContainer.appendChild(card);
    });
  }

  function renderMeasurements(measurements) {
    if (!measurementsContainer) return;
    measurementsContainer.innerHTML = '';
    if (measurements.length === 0) {
      measurementsContainer.innerHTML = '<p class="section-subtitle">No quantitative measurements extracted.</p>';
      return;
    }

    measurements.forEach((meas) => {
      const alertClass = getAlertClass(meas.alert_level);
      const row = document.createElement('div');
      row.className = `measurement-row ${alertClass}`;

      const unitStr = meas.unit ? ` ${meas.unit}` : '';
      const valDisplay = meas.value !== null ? `${meas.value}${unitStr}` : '—';

      // SVG range bar generation
      const chartHtml = buildRangeBarSvg(meas);

      row.innerHTML = `
        <div class="meas-info">
          <div class="meas-name">${escapeHtml(meas.concept)}</div>
          <div>
            <span class="meas-val-badge">${escapeHtml(valDisplay)}</span>
          </div>
        </div>
        <div class="meas-chart-col">
          ${chartHtml}
        </div>
        <div class="meas-explanation-col">
          <div>${escapeHtml(meas.explanation || '')}</div>
          <div class="meas-basis">${escapeHtml(meas.basis || '')}</div>
        </div>
      `;
      measurementsContainer.appendChild(row);
    });
  }

  function buildRangeBarSvg(meas) {
    const val = meas.value;
    const low = meas.low;
    const high = meas.high;
    const isLoinc = meas.range_source === 'loinc_standard';

    // If reference range missing even after LOINC lookup, show pill
    if (low === null || high === null || isNaN(low) || isNaN(high) || val === null || isNaN(val)) {
      return `<span class="meas-no-range-pill">No reference range reported</span>`;
    }

    const numVal = parseFloat(val);
    const numLow = parseFloat(low);
    const numHigh = parseFloat(high);

    // Compute dynamic SVG axis scale
    const span = Math.max(numHigh - numLow, 1);
    const pad = Math.max(span * 0.25, Math.abs(numVal - numHigh) * 1.2, Math.abs(numLow - numVal) * 1.2);
    const minAxis = Math.min(numLow - pad, numVal - 0.5);
    const maxAxis = Math.max(numHigh + pad, numVal + 0.5);
    const axisSpan = maxAxis - minAxis || 1;

    const xLow = Math.max(15, Math.min(245, 15 + ((numLow - minAxis) / axisSpan) * 230));
    const xHigh = Math.max(15, Math.min(245, 15 + ((numHigh - minAxis) / axisSpan) * 230));
    const xVal = Math.max(15, Math.min(245, 15 + ((numVal - minAxis) / axisSpan) * 230));

    const isOutside = numVal < numLow || numVal > numHigh;
    const markerColor = isOutside ? '#f97316' : '#22c55e';
    // Dashed track for LOINC standard ranges; solid for ranges from the report
    const trackStroke = isLoinc ? '#0284c7" stroke-dasharray="4 3' : '#0284c7';
    const loincBadge = isLoinc
      ? `<div class="loinc-range-badge"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>Standard range (LOINC)</div>`
      : '';

    return `
      <svg class="meas-chart-svg" viewBox="0 0 260 38">
        <!-- Background Track -->
        <line x1="15" y1="18" x2="245" y2="18" stroke="#334155" stroke-width="4" stroke-linecap="round"/>
        <!-- Normal Reference Track -->
        <line x1="${xLow}" y1="18" x2="${xHigh}" y2="18" stroke="${trackStroke}" stroke-width="6" stroke-linecap="round"/>
        <!-- Low Bound Tick & Label -->
        <line x1="${xLow}" y1="12" x2="${xLow}" y2="24" stroke="#94a3b8" stroke-width="1.5"/>
        <text x="${xLow}" y="34" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="Inter, sans-serif">${cleanNum(numLow)}</text>
        <!-- High Bound Tick & Label -->
        <line x1="${xHigh}" y1="12" x2="${xHigh}" y2="24" stroke="#94a3b8" stroke-width="1.5"/>
        <text x="${xHigh}" y="34" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="Inter, sans-serif">${cleanNum(numHigh)}</text>
        <!-- Value Marker -->
        <circle cx="${xVal}" cy="18" r="6" fill="${markerColor}" stroke="#ffffff" stroke-width="2"/>
      </svg>
      ${loincBadge}
    `;
  }


  function renderContext(contexts) {
    if (!contextContainer) return;
    contextContainer.innerHTML = '';
    if (contexts.length === 0) {
      contextContainer.innerHTML = '<p class="section-subtitle">No report-level co-occurring finding clusters detected.</p>';
      return;
    }

    contexts.forEach((ctx, idx) => {
      const card = document.createElement('div');
      card.className = 'context-card';

      const conceptTags = (ctx.concepts || [])
        .map((c) => `<span class="context-concept-tag">${escapeHtml(c)}</span>`)
        .join('');

      card.innerHTML = `
        <div class="context-card-header">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m8 3 4 8 5-5 5 15H2L8 3z"/>
          </svg>
          <span>Co-occurring Finding Group ${idx + 1}</span>
        </div>
        <div class="context-concepts-list">
          ${conceptTags}
        </div>
        <div class="context-explanation">${escapeHtml(ctx.explanation || '')}</div>
      `;
      contextContainer.appendChild(card);
    });
  }

  function renderLimitations(limitations) {
    if (!limitationsList) return;
    limitationsList.innerHTML = '';
    limitations.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = item;
      limitationsList.appendChild(li);
    });
  }

  /* ==========================================================================
     EXPORT TOOLBAR — Download PDF + Copy to Clipboard
     ========================================================================== */
  function renderExportToolbar(report) {
    const container = document.getElementById('export-toolbar-container');
    if (!container) return;
    container.innerHTML = `
      <div class="export-toolbar">
        <button class="btn-export download" id="btn-download-pdf" title="Download analysis as PDF">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download PDF
        </button>
        <button class="btn-export copy" id="btn-copy-summary" title="Copy summary to clipboard">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          Copy Summary
        </button>
      </div>
    `;

    document.getElementById('btn-download-pdf')?.addEventListener('click', () => {
      window.print();
    });

    document.getElementById('btn-copy-summary')?.addEventListener('click', function () {
      const btn = this;
      const text = buildPlainTextSummary(report);
      navigator.clipboard.writeText(text).then(() => {
        btn.classList.add('copied');
        btn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          Copied!
        `;
        setTimeout(() => {
          btn.classList.remove('copied');
          btn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            Copy Summary
          `;
        }, 2000);
      });
    });
  }

  function buildPlainTextSummary(report) {
    const lines = [];
    const s = report.report_summary || {};
    lines.push(`ClinRESET Report Analysis`);
    lines.push(`Report Type: ${s.report_type || 'Unknown'}  |  Status: ${s.status || 'Unknown'}`);
    lines.push('');

    if (report.key_findings && report.key_findings.length) {
      lines.push('=== KEY FINDINGS ===');
      report.key_findings.forEach(f => {
        lines.push(`• ${f.concept} [${f.alert_level}]: ${f.basis || ''}`);
      });
      lines.push('');
    }
    if (report.measurements_of_interest && report.measurements_of_interest.length) {
      lines.push('=== MEASUREMENTS ===');
      report.measurements_of_interest.forEach(m => {
        const unit = m.unit ? ` ${m.unit}` : '';
        lines.push(`• ${m.concept}: ${m.value}${unit}  [${m.alert_level}]  ${m.basis || ''}`);
      });
      lines.push('');
    }
    lines.push('Generated by ClinRESET — for informational purposes only.');
    return lines.join('\n');
  }

  /* ==========================================================================
     REPORT HISTORY — localStorage-based history list
     ========================================================================== */
  const HISTORY_KEY = 'clinreset_history';
  const MAX_HISTORY = 20;

  function saveToHistory(report, filename) {
    const history = getHistory();
    const entry = {
      id: Date.now(),
      filename: filename || 'report.pdf',
      timestamp: new Date().toISOString(),
      report_type: (report.report_summary || {}).report_type || 'UNKNOWN',
      status: (report.report_summary || {}).status || '',
      findings_count: (report.key_findings || []).length,
      measurements_count: (report.measurements_of_interest || []).length,
      report: report,
    };
    history.unshift(entry);    // newest first
    if (history.length > MAX_HISTORY) history.splice(MAX_HISTORY);
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (e) { /* storage full — skip */ }
  }

  function getHistory() {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    } catch { return []; }
  }

  function showHistoryPage() {
    const history = getHistory();
    let histDiv = document.getElementById('history-view');
    if (!histDiv) {
      histDiv = document.createElement('div');
      histDiv.id = 'history-view';
      resultsView?.parentElement?.insertBefore(histDiv, resultsView);
    }
    histDiv.removeAttribute('hidden');
    histDiv.classList.remove('hidden');
    hideElement(resultsView);

    const emptyMsg = history.length === 0
      ? '<div class="history-empty">No past reports found. Upload a PDF to get started.</div>'
      : '';

    const cards = history.map(entry => {
      const date = new Date(entry.timestamp).toLocaleString();
      return `
        <div class="history-card" data-id="${entry.id}">
          <div class="history-card-info">
            <div class="history-card-name" title="${escapeHtml(entry.filename)}">${escapeHtml(entry.filename)}</div>
            <div class="history-card-meta">${escapeHtml(date)} &bull; ${entry.findings_count} findings &bull; ${entry.measurements_count} measurements</div>
          </div>
          <div class="history-card-badges">
            <span class="history-type-badge">${escapeHtml(entry.report_type)}</span>
            <button class="btn-history-view" data-id="${entry.id}">View</button>
          </div>
        </div>`;
    }).join('');

    histDiv.innerHTML = `
      <div class="history-header">
        <h2>Report History</h2>
        <button class="btn-export copy" id="btn-history-back">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          Back
        </button>
      </div>
      <div class="history-list">${emptyMsg}${cards}</div>
    `;

    document.getElementById('btn-history-back')?.addEventListener('click', () => {
      hideElement(histDiv);
      if (_lastReport) showElement(resultsView);
      else setView('idle');
    });

    histDiv.querySelectorAll('.btn-history-view').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        const entry = getHistory().find(e => e.id === id);
        if (entry && entry.report) {
          hideElement(histDiv);
          showElement(resultsView);
          renderFinalReport(entry.report);
        }
      });
    });
  }

  /* ==========================================================================
     ABBREVIATION EXPANSION — dotted-underline tooltips on common abbrevs
     ========================================================================== */
  const ABBREV_MAP = {
    'LVH': 'Left Ventricular Hypertrophy',
    'LVEF': 'Left Ventricular Ejection Fraction',
    'EF': 'Ejection Fraction',
    'ECHO': 'Echocardiogram',
    'TSH': 'Thyroid Stimulating Hormone',
    'T3': 'Triiodothyronine (thyroid hormone)',
    'T4': 'Thyroxine (thyroid hormone)',
    'LDL': 'Low-Density Lipoprotein (bad cholesterol)',
    'HDL': 'High-Density Lipoprotein (good cholesterol)',
    'BMI': 'Body Mass Index',
    'BP': 'Blood Pressure',
    'HR': 'Heart Rate',
    'SpO2': 'Blood Oxygen Saturation',
    'HbA1c': 'Glycated Haemoglobin (3-month average blood sugar)',
    'FSH': 'Follicle Stimulating Hormone',
    'LH': 'Luteinizing Hormone',
    'DHEA': 'Dehydroepiandrosterone',
    'PCOS': 'Polycystic Ovary Syndrome',
    'CBC': 'Complete Blood Count',
    'WBC': 'White Blood Cell Count',
    'RBC': 'Red Blood Cell Count',
    'Hgb': 'Haemoglobin',
    'Hct': 'Haematocrit',
    'eGFR': 'estimated Glomerular Filtration Rate (kidney function)',
    'ALT': 'Alanine Aminotransferase (liver enzyme)',
    'AST': 'Aspartate Aminotransferase (liver enzyme)',
    'CRP': 'C-Reactive Protein (inflammation marker)',
    'INR': 'International Normalised Ratio (clotting time)',
    'ECG': 'Electrocardiogram',
    'EKG': 'Electrocardiogram',
    'IV': 'Intravenous',
  };

  // Build a regex matching all known abbreviations as whole words (case-sensitive)
  const _abbrevRe = new RegExp(
    '\\b(' + Object.keys(ABBREV_MAP).map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\b',
    'g'
  );

  function expandAbbreviations(html) {
    // html is already escaped — only wrap abbrev text nodes
    return html.replace(_abbrevRe, (match) => {
      const full = ABBREV_MAP[match];
      return full
        ? `<abbr class="abbr-term" title="${full}">${match}</abbr>`
        : match;
    });
  }

  /* ==========================================================================
     UTILITY HELPERS
     ========================================================================== */
  function getAlertClass(level) {
    switch (String(level).toUpperCase()) {
      case 'GREEN': return 'alert-green';
      case 'YELLOW': return 'alert-yellow';
      case 'ORANGE': return 'alert-orange';
      case 'RED': return 'alert-red';
      default: return 'alert-grey';
    }
  }

  function cleanNum(n) {
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /* ==========================================================================
     INITIALIZATION
     Strictly enforce "idle" state on load so ONLY drop-zone is visible.
     ========================================================================== */
  setView('idle');
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setView('idle'));
  }
})();
