const API_BASE = '/api';

const tabButtons = document.querySelectorAll('.tab-button');
const tabContents = {
  jobs: document.getElementById('tab-jobs'),
  settings: document.getElementById('tab-settings'),
  monitor: document.getElementById('tab-monitor'),
};

const jobForm = document.getElementById('job-form');
const jobsTableBody = document.querySelector('#jobs-table tbody');
const logViewer = document.getElementById('log-viewer');
const watermarkTypeToggle = document.getElementById('watermark-type');
const textFields = document.getElementById('text-watermark-fields');
const imageFields = document.getElementById('image-watermark-fields');
const parallelRange = document.getElementById('parallel-range');
const parallelValue = document.getElementById('parallel-value');
const ffmpegBinaryInput = document.getElementById('ffmpeg-binary');
const defaultOutputSelect = document.getElementById('default-output');
const saveSettingsButton = document.getElementById('save-settings');
const refreshSettingsButton = document.getElementById('refresh-settings');
const queueStats = document.getElementById('queue-stats');

let currentWatermarkType = 'text';
let selectedJobId = null;
let jobsCache = [];

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
tabButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const tab = button.dataset.tab;
    tabButtons.forEach((btn) => btn.classList.toggle('active', btn === button));
    Object.entries(tabContents).forEach(([key, node]) => {
      node.style.display = key === tab ? 'block' : 'none';
    });
  });
});

// ---------------------------------------------------------------------------
// Watermark toggle
// ---------------------------------------------------------------------------
watermarkTypeToggle.querySelectorAll('button').forEach((button) => {
  button.addEventListener('click', () => {
    currentWatermarkType = button.dataset.value;
    watermarkTypeToggle.querySelectorAll('button').forEach((btn) => {
      btn.classList.toggle('active', btn === button);
    });
    if (currentWatermarkType === 'text') {
      textFields.style.display = 'block';
      imageFields.style.display = 'none';
    } else {
      textFields.style.display = 'none';
      imageFields.style.display = 'block';
    }
  });
});

// ---------------------------------------------------------------------------
// Job form submission
// ---------------------------------------------------------------------------
jobForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submitButton = jobForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  submitButton.textContent = '提交中...';

  try {
    const formData = new FormData();
    const files = document.getElementById('files').files;
    if (!files.length) {
      throw new Error('请选择至少一个视频文件');
    }
    Array.from(files).forEach((file) => formData.append('files', file));

    formData.append('watermark_type', currentWatermarkType);
    const preset = document.getElementById('preset').value;
    const outputFormat = document.getElementById('output-format').value;

    formData.append('preset', preset);
    formData.append('output_format', outputFormat);
    formData.append('opacity', jobForm.querySelector('[name="opacity"]').value);
    formData.append('position', jobForm.querySelector('[name="position"]').value);
    formData.append('offset_x', jobForm.querySelector('[name="offset_x"]').value);
    formData.append('offset_y', jobForm.querySelector('[name="offset_y"]').value);

    if (currentWatermarkType === 'text') {
      formData.append('watermark_text', jobForm.querySelector('[name="watermark_text"]').value);
      formData.append('font_size', jobForm.querySelector('[name="font_size"]').value);
      formData.append('color', jobForm.querySelector('[name="color"]').value);
    } else {
      const imageFile = jobForm.querySelector('[name="watermark_image"]').files[0];
      if (imageFile) {
        formData.append('watermark_image', imageFile);
      }
    }

    const response = await fetch(`${API_BASE}/jobs`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || '创建任务失败');
    }

    const data = await response.json();
    showToast(`任务 ${data.job_id} 已创建`, 'success');
    jobForm.reset();
    await refreshJobs();
  } catch (error) {
    console.error(error);
    showToast(error.message || '提交失败', 'error');
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = '提交任务';
  }
});

// ---------------------------------------------------------------------------
// Jobs rendering
// ---------------------------------------------------------------------------
async function refreshJobs() {
  try {
    const response = await fetch(`${API_BASE}/jobs`);
    if (!response.ok) throw new Error('无法获取任务列表');
    jobsCache = await response.json();
    renderJobs();
    renderQueueStats();
    if (selectedJobId) {
      await showJobLog(selectedJobId);
    }
  } catch (error) {
    console.error(error);
  }
}

function renderJobs() {
  jobsTableBody.innerHTML = '';
  jobsCache
    .slice()
    .sort((a, b) => b.created_at - a.created_at)
    .forEach((job) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${job.id.slice(0, 8)}...</td>
        <td>${renderStatus(job.status)}</td>
        <td>${Math.round(job.progress * 100)}%</td>
        <td>${formatTime(job.started_at)}</td>
        <td>${formatTime(job.finished_at)}</td>
        <td><button class="secondary" data-job="${job.id}">查看</button></td>
      `;
      row.querySelector('button').addEventListener('click', () => showJobLog(job.id));
      jobsTableBody.appendChild(row);
    });
}

async function showJobLog(jobId) {
  try {
    const response = await fetch(`${API_BASE}/jobs/${jobId}`);
    if (!response.ok) throw new Error('无法获取任务详情');
    const job = await response.json();
    selectedJobId = job.id;
    const entries = job.log.length ? job.log.map((line) => `<div>${escapeHtml(line)}</div>`).join('') : '暂无日志';
    logViewer.innerHTML = entries;
    logViewer.scrollTop = logViewer.scrollHeight;
  } catch (error) {
    console.error(error);
    showToast('日志加载失败', 'error');
  }
}

function renderStatus(status) {
  const map = {
    queued: '<span class="badge pending">排队中</span>',
    running: '<span class="badge pending">进行中</span>',
    completed: '<span class="badge success">完成</span>',
    failed: '<span class="badge error">失败</span>',
    cancelled: '<span class="badge error">已取消</span>',
  };
  return map[status] || status;
}

function formatTime(timestamp) {
  if (!timestamp) return '-';
  const date = new Date(timestamp * 1000);
  return date.toLocaleString();
}

function escapeHtml(str) {
  return str.replace(/[&<>'"]/g, (tag) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[tag] || tag));
}

function renderQueueStats() {
  const stats = {
    total: jobsCache.length,
    running: jobsCache.filter((job) => job.status === 'running').length,
    completed: jobsCache.filter((job) => job.status === 'completed').length,
    failed: jobsCache.filter((job) => job.status === 'failed').length,
  };
  queueStats.querySelector('[data-field="total"]').textContent = stats.total;
  queueStats.querySelector('[data-field="running"]').textContent = stats.running;
  queueStats.querySelector('[data-field="completed"]').textContent = stats.completed;
  queueStats.querySelector('[data-field="failed"]').textContent = stats.failed;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
parallelRange.addEventListener('input', () => {
  parallelValue.textContent = `当前并行：${parallelRange.value}`;
});

saveSettingsButton.addEventListener('click', async () => {
  try {
    const payload = {
      max_parallel_jobs: Number(parallelRange.value),
      default_output_format: defaultOutputSelect.value,
      ffmpeg_binary: ffmpegBinaryInput.value || undefined,
    };
    const response = await fetch(`${API_BASE}/settings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error('保存失败');
    showToast('设置已更新', 'success');
    await loadSettings();
  } catch (error) {
    console.error(error);
    showToast('保存失败', 'error');
  }
});

refreshSettingsButton.addEventListener('click', async () => {
  await loadSettings();
});

async function loadSettings() {
  try {
    const response = await fetch(`${API_BASE}/settings`);
    if (!response.ok) throw new Error('无法读取设置');
    const data = await response.json();
    parallelRange.value = data.max_parallel_jobs;
    parallelValue.textContent = `当前并行：${data.max_parallel_jobs}`;
    defaultOutputSelect.value = data.default_output_format || 'mp4';
    const outputFormatSelect = document.getElementById('output-format');
    if (outputFormatSelect) {
      outputFormatSelect.value = data.default_output_format || 'mp4';
    }
    ffmpegBinaryInput.value = data.ffmpeg_binary || '';
  } catch (error) {
    console.error(error);
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.textContent = message;
  toast.style.position = 'fixed';
  toast.style.bottom = '24px';
  toast.style.right = '24px';
  toast.style.padding = '0.75rem 1.25rem';
  toast.style.borderRadius = '14px';
  toast.style.background = type === 'success' ? 'rgba(74, 222, 128, 0.95)' : type === 'error' ? 'rgba(248, 113, 113, 0.95)' : 'rgba(96, 165, 250, 0.95)';
  toast.style.color = '#0f172a';
  toast.style.fontWeight = '600';
  toast.style.zIndex = '9999';
  toast.style.boxShadow = '0 12px 40px rgba(15, 23, 42, 0.4)';
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
loadSettings();
refreshJobs();
setInterval(refreshJobs, 5000);
