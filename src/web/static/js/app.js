/**
 * ClinRESET Web Application - Client-Side Controller
 * Handles Report Simplification, Methodology Configuration,
 * Live Extraction Testing Sandbox, and Provenance Inspection.
 */

// Application State
const state = {
  currentTab: 'simplifier',
  activeBackend: 'heuristic',
  methodologies: {},
  sampleReports: {},
  currentReportResult: null,
  selectedFile: null,
};

// ============================================================================
// Initialization
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initDragAndDrop();
  fetchSampleReports();
  fetchMethodologyStatus();
});

// ============================================================================
// Navigation & Tab Switching
// ============================================================================
function switchTab(tabName) {
  state.currentTab = tabName;

  const simplifierBtn = document.getElementById('tab-simplifier-btn');
  const studioBtn = document.getElementById('tab-studio-btn');
  const simplifierPane = document.getElementById('tab-simplifier');
  const studioPane = document.getElementById('tab-studio');

  if (tabName === 'simplifier') {
    simplifierBtn.classList.add('active');
    studioBtn.classList.remove('active');
    simplifierPane.classList.add('active');
    studioPane.classList.remove('active');
  } else {
    studioBtn.classList.add('active');
    simplifierBtn.classList.remove('active');
    studioPane.classList.add('active');
    simplifierPane.classList.remove('active');
    // Refresh methodology status whenever entering studio
    fetchMethodologyStatus();
  }
}

// ============================================================================
// Methodology Studio Operations
// ============================================================================
async function fetchMethodologyStatus() {
  try {
    const res = await fetch('/api/methodologies');
    if (!res.ok) throw new Error('Failed to fetch methodology status');
    const data = await res.json();

    state.activeBackend = data.active_backend;
    state.methodologies = data;

    // Update active badges in Navbar
    const badge = document.getElementById('active-backend-badge');
    const dot = document.getElementById('active-backend-dot');
    if (badge) badge.textContent = data.active_backend.toUpperCase();
    if (dot) dot.className = 'status-indicator-dot ' + (data.active_backend === 'heuristic' ? 'online' : 'active');

    // Update methodology cards
    updateBackendCards(data.active_backend, data.availability);

    // Populate configuration form inputs if available
    const cfg = data.config || {};
    const backendSelect = document.getElementById('cfg-backend');
    if (backendSelect) backendSelect.value = data.active_backend;

    const ollamaUrlInput = document.getElementById('cfg-ollama-url');
    if (ollamaUrlInput && cfg.ollama_url) ollamaUrlInput.value = cfg.ollama_url;

    const ollamaModelInput = document.getElementById('cfg-ollama-model');
    if (ollamaModelInput && cfg.ollama_model) ollamaModelInput.value = cfg.ollama_model;

    const hfTokenInput = document.getElementById('cfg-hf-token');
    if (hfTokenInput && cfg.hf_token) hfTokenInput.value = cfg.hf_token;

    const hfModelInput = document.getElementById('cfg-hf-model');
    if (hfModelInput && cfg.hf_model) hfModelInput.value = cfg.hf_model;

  } catch (err) {
    console.error('Error fetching methodology status:', err);
  }
}

function updateBackendCards(activeBackend, availability) {
  const backends = ['heuristic', 'ollama', 'hf_api', 'transformers'];

  backends.forEach((backend) => {
    const card = document.getElementById(`card-${backend}`);
    const badge = document.getElementById(`badge-${backend}`);
    if (!card || !badge) return;

    const isAvailable = availability ? availability[backend] : false;
    const isActive = activeBackend === backend;

    card.classList.toggle('active-backend-card', isActive);

    if (isActive) {
      badge.textContent = 'ACTIVE';
      badge.className = 'badge badge-success';
    } else if (isAvailable) {
      badge.textContent = 'AVAILABLE';
      badge.className = 'badge badge-info';
    } else {
      badge.textContent = 'NOT CONFIGURED';
      badge.className = 'badge badge-secondary';
    }
  });
}

function selectBackend(backend) {
  const backendSelect = document.getElementById('cfg-backend');
  if (backendSelect) {
    backendSelect.value = backend;
  }
  // Focus and highlight form for quick save
  const formCard = document.querySelector('.settings-card');
  if (formCard) {
    formCard.scrollIntoView({ behavior: 'smooth' });
    formCard.classList.add('pulse-highlight');
    setTimeout(() => formCard.classList.remove('pulse-highlight'), 1200);
  }
}

async function saveConfiguration(event) {
  if (event) event.preventDefault();

  const statusEl = document.getElementById('save-status');
  if (statusEl) {
    statusEl.textContent = 'Saving configuration...';
    statusEl.className = 'save-status saving';
  }

  const payload = {
    active_backend: document.getElementById('cfg-backend').value,
    ollama_url: document.getElementById('cfg-ollama-url').value.trim() || undefined,
    ollama_model: document.getElementById('cfg-ollama-model').value.trim() || undefined,
    hf_token: document.getElementById('cfg-hf-token').value.trim() || undefined,
    hf_model: document.getElementById('cfg-hf-model').value.trim() || undefined,
  };

  try {
    const res = await fetch('/api/methodologies/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to update configuration');

    state.activeBackend = data.current_config.active_backend;

    if (statusEl) {
      statusEl.textContent = `✓ ${data.message}`;
      statusEl.className = 'save-status success';
      setTimeout(() => { statusEl.textContent = ''; }, 4000);
    }

    // Refresh display
    await fetchMethodologyStatus();
  } catch (err) {
    console.error('Error saving configuration:', err);
    if (statusEl) {
      statusEl.textContent = `✗ ${err.message}`;
      statusEl.className = 'save-status error';
    }
  }
}

// ============================================================================
// Live Extraction Sandbox
// ============================================================================
function applySandboxPreset() {
  const presetSelect = document.getElementById('sandbox-preset');
  const sentenceArea = document.getElementById('sandbox-sentence');
  if (presetSelect && sentenceArea && presetSelect.value) {
    sentenceArea.value = presetSelect.value;
  }
}

async function runSandboxTest() {
  const sentenceArea = document.getElementById('sandbox-sentence');
  const sentence = sentenceArea.value.trim();

  if (!sentence) {
    alert('Please enter or select a clinical sentence to test.');
    sentenceArea.focus();
    return;
  }

  const btnText = document.getElementById('sandbox-btn-text');
  const spinner = document.getElementById('sandbox-spinner');
  const outputContainer = document.getElementById('sandbox-output-container');
  const resultsList = document.getElementById('sandbox-results-list');

  btnText.textContent = 'Extracting...';
  spinner.classList.remove('hidden');

  try {
    const res = await fetch('/api/methodologies/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sentence: sentence,
        backend: state.activeBackend,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Extraction test failed');

    // Populate header stats
    document.getElementById('sb-engine').textContent = data.backend_used.toUpperCase();
    document.getElementById('sb-latency').textContent = `${data.elapsed_ms} ms`;
    document.getElementById('sb-count').textContent = data.count;

    // Render concept cards
    resultsList.innerHTML = '';
    if (data.concepts_extracted && data.concepts_extracted.length > 0) {
      data.concepts_extracted.forEach((item) => {
        const card = document.createElement('div');
        card.className = 'sandbox-concept-card';

        const assertionClass = item.assertion === 'ABSENT' ? 'badge-danger' : 'badge-success';
        const groundingIcon = item.is_grounded ? '✓ Grounded' : '⚠️ Unverified';
        const groundingClass = item.is_grounded ? 'badge-info' : 'badge-warning';

        card.innerHTML = `
          <div class="sandbox-concept-header">
            <h4>${escapeHtml(item.concept)}</h4>
            <div class="sandbox-concept-badges">
              <span class="badge ${assertionClass}">${escapeHtml(item.assertion)}</span>
              <span class="badge ${groundingClass}">${groundingIcon}</span>
            </div>
          </div>
        `;
        resultsList.appendChild(card);
      });
    } else {
      resultsList.innerHTML = '<div class="empty-state">No clinical concepts extracted from this sentence.</div>';
    }

    outputContainer.classList.remove('hidden');
    outputContainer.scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    alert(`Sandbox Error: ${err.message}`);
  } finally {
    btnText.textContent = 'Run Extraction Test';
    spinner.classList.add('hidden');
  }
}

// ============================================================================
// Drag & Drop and Sample Report Loading
// ============================================================================
function initDragAndDrop() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('pdf-input');
  const fileNameDisplay = document.getElementById('selected-file-name');

  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-over');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0 && files[0].name.toLowerCase().endsWith('.pdf')) {
      handleFileSelected(files[0]);
    } else {
      alert('Please upload a valid PDF document.');
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });
}

function handleFileSelected(file) {
  state.selectedFile = file;
  const fileNameDisplay = document.getElementById('selected-file-name');
  if (fileNameDisplay) {
    fileNameDisplay.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    fileNameDisplay.classList.add('active');
  }
  // Clear sample select dropdown
  const sampleSelect = document.getElementById('sample-select');
  if (sampleSelect) sampleSelect.value = '';
}

async function fetchSampleReports() {
  try {
    const res = await fetch('/api/reports/samples');
    if (!res.ok) throw new Error('Failed to fetch samples');
    const data = await res.json();
    state.sampleReports = data.samples;

    const select = document.getElementById('sample-select');
    if (!select) return;

    select.innerHTML = '<option value="">-- Select a sample report --</option>';

    for (const [modality, files] of Object.entries(data.samples)) {
      if (files.length === 0) continue;
      const optGroup = document.createElement('optgroup');
      optGroup.label = `${modality.toUpperCase()} Reports (${files.length})`;

      files.forEach((file) => {
        const opt = document.createElement('option');
        opt.value = file.relative_path;
        opt.textContent = `${file.filename} (${file.modality})`;
        optGroup.appendChild(opt);
      });

      select.appendChild(optGroup);
    }

    select.addEventListener('change', () => {
      if (select.value) {
        state.selectedFile = null;
        const fileNameDisplay = document.getElementById('selected-file-name');
        if (fileNameDisplay) {
          fileNameDisplay.textContent = '';
          fileNameDisplay.classList.remove('active');
        }
      }
    });

  } catch (err) {
    console.error('Error fetching sample reports:', err);
  }
}

// ============================================================================
// Report Simplification Execution
// ============================================================================
async function runSimplification() {
  const sampleSelect = document.getElementById('sample-select');
  const samplePath = sampleSelect ? sampleSelect.value : null;

  if (!state.selectedFile && !samplePath) {
    alert('Please select a sample report or upload a PDF first.');
    return;
  }

  const btnText = document.getElementById('btn-text');
  const spinner = document.getElementById('btn-spinner');
  const resultsContainer = document.getElementById('results-container');

  btnText.textContent = 'Processing Pipeline...';
  spinner.classList.remove('hidden');

  try {
    let result;

    if (state.selectedFile) {
      const formData = new FormData();
      formData.append('file', state.selectedFile);

      const res = await fetch('/api/reports/upload', {
        method: 'POST',
        body: formData,
      });

      result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Upload processing failed');
    } else {
      const res = await fetch('/api/reports/sample', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sample_path: samplePath }),
      });

      result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Sample processing failed');
    }

    state.currentReportResult = result;
    renderReportResults(result);

    resultsContainer.classList.remove('hidden');
    resultsContainer.scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    alert(`Simplification Failed: ${err.message}`);
  } finally {
    btnText.textContent = 'Simplify Report';
    spinner.classList.add('hidden');
  }
}

// ============================================================================
// Results Rendering
// ============================================================================
function renderReportResults(data) {
  // Document Meta
  document.getElementById('res-filename').textContent = data.filename || 'report.pdf';
  document.getElementById('res-modality').textContent = (data.report_type || 'Clinical Report').toUpperCase();
  document.getElementById('res-findings-count').textContent = data.findings_count || 0;
  document.getElementById('res-methodology').textContent = (data.active_methodology || 'heuristic').toUpperCase();

  // Patient Friendly Summary
  const summaryEl = document.getElementById('res-patient-summary');
  if (data.patient_explanation && (data.patient_explanation.patient_summary || data.patient_explanation.summary)) {
    summaryEl.textContent = data.patient_explanation.patient_summary || data.patient_explanation.summary;
  } else {
    summaryEl.textContent = 'No summary generated.';
  }

  // Triage Counters
  const triage = (data.interpretation && (data.interpretation.alert_counts || data.interpretation.triage_summary)) || {};
  document.getElementById('count-green').textContent = triage.GREEN || 0;
  document.getElementById('count-yellow').textContent = triage.YELLOW || 0;
  document.getElementById('count-orange').textContent = triage.ORANGE || 0;
  document.getElementById('count-red').textContent = triage.RED || 0;
  document.getElementById('count-grey').textContent = triage.GREY || 0;

  // Clusters
  renderClusters(data.clusters || []);

  // Findings Table
  renderFindingsTable(data.findings || []);

  // Doctor Questions
  renderDoctorQuestions(
    (data.patient_explanation && (data.patient_explanation.questions_for_doctor || data.patient_explanation.doctor_questions)) || []
  );
}

function renderClusters(clusters) {
  const container = document.getElementById('clusters-list');
  container.innerHTML = '';

  if (clusters.length === 0) {
    container.innerHTML = '<div class="empty-state">No multi-observation clinical clusters identified.</div>';
    return;
  }

  clusters.forEach((cluster) => {
    const card = document.createElement('div');
    card.className = 'cluster-card';

    const findingsTags = cluster.findings
      .map((f) => `<span class="cluster-tag">${escapeHtml(f)}</span>`)
      .join('');

    card.innerHTML = `
      <div class="cluster-header">
        <h3>${escapeHtml(cluster.name)}</h3>
        <span class="badge badge-info">${escapeHtml(cluster.organ_system)}</span>
      </div>
      <div class="cluster-tags-container">
        ${findingsTags}
      </div>
    `;
    container.appendChild(card);
  });
}

function renderFindingsTable(findings) {
  const tbody = document.getElementById('findings-table-body');
  tbody.innerHTML = '';

  if (findings.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">No clinical findings extracted from this document.</td></tr>';
    return;
  }

  findings.forEach((finding, index) => {
    const tr = document.createElement('tr');
    tr.className = 'clickable-row';
    tr.onclick = () => openInspector(index);

    const alertLevel = finding.alert_level || 'GREY';
    const alertBadgeClass = `badge-alert-${alertLevel.toLowerCase()}`;

    const valueStr = finding.value ? `${finding.value} ${finding.unit || ''}`.trim() : '—';
    const rangeStr = finding.reference_range ? `${finding.reference_range}` : '—';
    const snomedBadge = finding.snomed_id
      ? `<span class="badge badge-snomed">${escapeHtml(finding.snomed_id)}</span>`
      : '<span class="text-dim">None</span>';

    const assertionBadge = finding.assertion === 'ABSENT'
      ? '<span class="badge badge-danger">ABSENT</span>'
      : '<span class="badge badge-success">PRESENT</span>';

    tr.innerHTML = `
      <td><span class="alert-pill ${alertBadgeClass}">${alertLevel}</span></td>
      <td><strong>${escapeHtml(finding.preferred_term || finding.concept)}</strong></td>
      <td>${assertionBadge}</td>
      <td><code>${escapeHtml(valueStr)}</code></td>
      <td><span class="text-muted">${escapeHtml(rangeStr)}</span></td>
      <td><span class="layman-text">${escapeHtml(finding.layman_synonym || 'Standard finding')}</span></td>
      <td>${snomedBadge}</td>
    `;

    tbody.appendChild(tr);
  });
}

function renderDoctorQuestions(questions) {
  const list = document.getElementById('questions-list');
  list.innerHTML = '';

  if (questions.length === 0) {
    list.innerHTML = '<li>Discuss these results and any ongoing symptoms with your attending healthcare provider.</li>';
    return;
  }

  questions.forEach((q) => {
    const li = document.createElement('li');
    li.textContent = q;
    list.appendChild(li);
  });
}

// ============================================================================
// Provenance Inspector Modal
// ============================================================================
function openInspector(findingIndex) {
  if (!state.currentReportResult || !state.currentReportResult.findings) return;
  const finding = state.currentReportResult.findings[findingIndex];
  if (!finding) return;

  document.getElementById('modal-concept-name').textContent = finding.concept || 'Finding Details';
  document.getElementById('modal-organ').textContent = finding.organ_system || 'General';
  document.getElementById('modal-preferred-term').textContent = finding.preferred_term || finding.concept;

  // SNOMED
  const snomedEl = document.getElementById('modal-snomed-id');
  snomedEl.textContent = finding.snomed_id ? `SNOMED: ${finding.snomed_id}` : 'Uncoded (Generic finding)';

  // Alert Badge
  const alertEl = document.getElementById('modal-alert-badge');
  const alertLevel = finding.alert_level || 'GREY';
  alertEl.textContent = alertLevel;
  alertEl.className = `inspector-value alert-pill badge-alert-${alertLevel.toLowerCase()}`;

  // Layman Term
  document.getElementById('modal-layman-term').textContent =
    finding.layman_synonym || 'Clinical term with standard medical meaning';

  // Range Basis
  document.getElementById('modal-range-basis').textContent =
    finding.clinical_basis || 'Standard assertion evaluation without numerical reference thresholds.';

  // Source Text Provenance
  document.getElementById('modal-source-text').textContent =
    finding.source_text || 'Exact clause source not recorded.';

  // Page, Section, Method
  document.getElementById('modal-page').textContent = `Page ${finding.page_number || 1}`;
  document.getElementById('modal-section').textContent = finding.section_title || 'REPORT';
  document.getElementById('modal-method').textContent = finding.method || 'Hybrid Rule + Grounded Model';

  // Show Modal
  const modal = document.getElementById('inspector-modal');
  modal.classList.remove('hidden');
}

function closeInspector() {
  const modal = document.getElementById('inspector-modal');
  if (modal) modal.classList.add('hidden');
}

function closeInspectorOnOverlay(event) {
  if (event.target.id === 'inspector-modal') {
    closeInspector();
  }
}

// Utility: HTML Escaping
function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
