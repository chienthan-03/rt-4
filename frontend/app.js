const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const uploadCard = document.getElementById('uploadCard');
const statusCard = document.getElementById('statusCard');
const statusLabel = document.getElementById('statusLabel');
const progressBar = document.getElementById('progressBar');
const resultCard = document.getElementById('resultCard');
const resultSub = document.getElementById('resultSub');
const downloadBtn = document.getElementById('downloadBtn');
const errorCard = document.getElementById('errorCard');
const errorMsg = document.getElementById('errorMsg');

const enableBackgroundCheckbox = document.getElementById('enableBackgroundCheckbox');
const bgVolumeSlider = document.getElementById('bgVolumeSlider');

const getEnableBackground = () => enableBackgroundCheckbox?.checked ?? true;

const syncBgVolumeDisabled = () => {
  if (!bgVolumeSlider) return;
  const enabled = getEnableBackground();
  bgVolumeSlider.disabled = !enabled;
  bgVolumeSlider.setAttribute('aria-disabled', String(!enabled));
  bgVolumeSlider.closest('.volume-control')?.classList.toggle('is-disabled', !enabled);
};

enableBackgroundCheckbox?.addEventListener('change', syncBgVolumeDisabled);
syncBgVolumeDisabled();

const STEPS = [
  'extracting',
  'transcribing',
  'analyzing_signals',
  'detecting_highlights',
  'selecting_sounds',
  'placing_sounds',
  'rendering',
];

const STEP_LABELS = {
  extracting:          '🎬 Đang trích xuất audio và frames…',
  transcribing:        '🎤 Đang nhận dạng giọng nói…',
  analyzing_signals:   '📊 Đang phân tích tín hiệu âm thanh…',
  detecting_highlights:'🔍 Đang phát hiện khoảnh khắc hay…',
  selecting_sounds:    '🎵 Đang chọn meme sounds phù hợp…',
  placing_sounds:      '⏱️ Đang tính thời điểm chèn…',
  rendering:           '🎞️ Đang render video cuối cùng…',
};

const getSliderVolume = (getterName, sliderId, fallback) => {
  if (typeof window[getterName] === 'function') {
    return window[getterName]();
  }
  const slider = document.getElementById(sliderId);
  return slider ? Number(slider.value) / 100 : fallback;
};

const getMajorVolume = () => getSliderVolume('getMajorVolume', 'majorVolumeSlider', 0.5);
const getMinorVolume = () => getSliderVolume('getMinorVolume', 'minorVolumeSlider', 0.35);
const getBgVolume = () => getSliderVolume('getBgVolume', 'bgVolumeSlider', 0.15);

const getNiche = () => {
  if (typeof window.getNiche === 'function') {
    return window.getNiche();
  }
  const active = document.querySelector('.niche-option.active');
  return active?.dataset.niche || 'entertainment';
};

// Drag-and-drop
uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});
uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

// Reset buttons
document.getElementById('resetBtn').addEventListener('click', reset);
document.getElementById('errorResetBtn').addEventListener('click', reset);

function reset() {
  uploadCard.style.display = 'block';
  statusCard.style.display = 'none';
  resultCard.style.display = 'none';
  errorCard.style.display = 'none';
  fileInput.value = '';
  // reset steps
  STEPS.forEach(s => {
    const el = document.getElementById(`step-${s}`);
    if (el) { el.className = 'step'; }
  });
  progressBar.style.width = '10%';
}

async function handleFile(file) {
  uploadCard.style.display = 'none';
  statusCard.style.display = 'block';
  resultCard.style.display = 'none';
  errorCard.style.display = 'none';

  statusLabel.textContent = '⬆️ Đang upload video…';
  progressBar.style.width = '5%';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('major_volume', String(getMajorVolume()));
  formData.append('minor_volume', String(getMinorVolume()));
  formData.append('bg_volume', String(getBgVolume()));
  formData.append('niche', getNiche());
  formData.append('enable_background', getEnableBackground() ? 'true' : 'false');

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt);
    }
    const { task_id, job_id } = await res.json();
    statusLabel.textContent = '✅ Upload xong! Đang xử lý…';
    progressBar.style.width = '10%';
    pollStatus(task_id, job_id);
  } catch (err) {
    showError(err.message);
  }
}

function setStep(currentStep) {
  const idx = STEPS.indexOf(currentStep);
  STEPS.forEach((s, i) => {
    const el = document.getElementById(`step-${s}`);
    if (!el) return;
    if (i < idx) { el.className = 'step done'; }
    else if (i === idx) { el.className = 'step active'; }
    else { el.className = 'step'; }
  });
  // Progress: map step index to 10–90%
  const pct = 10 + Math.round((idx / (STEPS.length - 1)) * 80);
  progressBar.style.width = `${pct}%`;
  statusLabel.textContent = STEP_LABELS[currentStep] || '⚙️ Đang xử lý…';
}

function pollStatus(taskId, jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/status/${taskId}`);
      const data = await res.json();

      if (data.status === 'PROGRESS') {
        setStep(data.step);
      } else if (data.status === 'SUCCESS') {
        clearInterval(interval);
        // Mark all steps done
        STEPS.forEach(s => {
          const el = document.getElementById(`step-${s}`);
          if (el) el.className = 'step done';
        });
        progressBar.style.width = '100%';
        statusLabel.textContent = '✅ Hoàn thành!';

        window.currentJobId = jobId;
        window.currentPlacements = data.result?.placements || [];
        window.feedbackActions = [];
        if (typeof renderPlacements === 'function') renderPlacements();
        const editorUI = document.getElementById('editorUI');
        if (editorUI) editorUI.style.display = 'block';
        const previewVideo = document.getElementById('previewVideo');
        if (previewVideo) {
          previewVideo.src = `/download/${jobId}`;
          previewVideo.load();
        }

        setTimeout(() => {
          statusCard.style.display = 'none';
          resultCard.style.display = 'block';
          const soundsAdded = data.result?.sounds_added ?? 0;
          const uniqueSounds = data.result?.unique_sounds ?? soundsAdded;
          const majorSounds = data.result?.major_sounds;
          const minorSounds = data.result?.minor_sounds;
          const nicheLabels = {
            entertainment: 'giải trí',
            edu: 'giáo dục',
            lifestyle: 'lifestyle',
          };
          const nicheKey = data.result?.niche || getNiche();
          const nicheLabel = nicheLabels[nicheKey] || nicheKey;
          let msg = `AI đã chèn ${soundsAdded} sound (chế độ ${nicheLabel})`;
          if (majorSounds != null && minorSounds != null) {
            msg += ` — ${majorSounds} meme chính + ${minorSounds} hiệu ứng nhẹ`;
          } else {
            msg += ` — ${uniqueSounds} loại sound khác nhau`;
          }
          msg += '. 🎉';
          if (data.result?.transcript_note) {
            msg += ` (${data.result.transcript_note})`;
          }
          resultSub.textContent = msg;
          // downloadBtn is now handled by custom logic
        }, 600);
      } else if (data.status === 'FAILURE') {
        clearInterval(interval);
        showError(data.error || 'Có lỗi không xác định xảy ra.');
      }
    } catch (err) {
      clearInterval(interval);
      showError(err.message);
    }
  }, 2000);
}

function showError(msg) {
  statusCard.style.display = 'none';
  uploadCard.style.display = 'none';
  errorCard.style.display = 'block';
  errorMsg.textContent = `❌ Lỗi: ${msg}`;
}

// Editor Logic
window.currentPlacements = [];
window.feedbackActions = [];
window.currentJobId = null;
window.currentReplaceId = null;

function renderPlacements() {
  const list = document.getElementById('placementsList');
  if (!list) return;
  list.innerHTML = '';
  window.currentPlacements.forEach(p => {
    if (p.track === "background") return; // skip bg track for now
    const div = document.createElement('div');
    div.className = 'placement-item';
    const time = (p.insert_ms / 1000).toFixed(1) + 's';
    div.innerHTML = `
      <span>[${time}] ${p.name || 'Sound'}</span>
      <div class="placement-actions">
        <button class="replace-btn" onclick="openReplaceModal('${p.placement_id}', '${p.highlight_context || ''}')">Đổi</button>
        <button class="delete-btn" onclick="deletePlacement('${p.placement_id}')">Xóa</button>
      </div>
    `;
    list.appendChild(div);
  });
}

window.deletePlacement = function(pid) {
  const pIndex = window.currentPlacements.findIndex(x => x.placement_id === pid);
  if (pIndex < 0) return;
  const p = window.currentPlacements[pIndex];
  window.feedbackActions.push({ sound_id: p.name, status: 'delete' });
  window.currentPlacements.splice(pIndex, 1);
  renderPlacements();
};

const modal = document.getElementById('replaceModal');
const closeBtn = document.getElementById('closeModal');
const searchInput = document.getElementById('soundSearchInput');
const suggestDiv = document.getElementById('suggestedSounds');
const searchDiv = document.getElementById('searchResults');

if (closeBtn) {
  closeBtn.onclick = () => modal.style.display = 'none';
}

window.openReplaceModal = async function(pid, context) {
  window.currentReplaceId = pid;
  modal.style.display = 'flex';
  suggestDiv.innerHTML = 'Đang tải gợi ý...';
  searchDiv.innerHTML = '';
  searchInput.value = '';
  
  try {
    const res = await fetch(`/sounds/suggest?context=${encodeURIComponent(context)}`);
    const data = await res.json();
    renderSoundOptions(data.results, suggestDiv);
  } catch (e) {
    suggestDiv.innerHTML = 'Lỗi tải gợi ý.';
  }
};

if (searchInput) {
  searchInput.addEventListener('input', async (e) => {
    const q = e.target.value;
    if (q.length < 2) {
      searchDiv.innerHTML = '';
      return;
    }
    const res = await fetch(`/sounds/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderSoundOptions(data.results, searchDiv);
  });
}

function renderSoundOptions(list, container) {
  container.innerHTML = '';
  if (!list || list.length === 0) {
    container.innerHTML = '<p style="font-size:12px;color:#888;">Không có kết quả.</p>';
    return;
  }
  list.forEach(s => {
    const div = document.createElement('div');
    div.className = 'sound-option';
    div.innerHTML = `
      <div class="sound-option-info">
        <div class="sound-option-name">${s.name}</div>
        <div class="sound-option-meta">Thời lượng: ${s.duration_ms}ms</div>
      </div>
      <button onclick="replaceSound('${s.id}', '${s.name}', '${s.file_path}')">Chọn</button>
    `;
    container.appendChild(div);
  });
}

window.replaceSound = function(newId, newName, newPath) {
  const p = window.currentPlacements.find(x => x.placement_id === window.currentReplaceId);
  if (p) {
    window.feedbackActions.push({ old_sound_id: p.name, new_sound_id: newName, status: 'replace' });
    p.name = newName;
    p.sound_file = newPath;
  }
  modal.style.display = 'none';
  renderPlacements();
};

if (downloadBtn) {
  downloadBtn.onclick = async function(e) {
    e.preventDefault();
    
    window.currentPlacements.forEach(p => {
      if (p.track !== "background") {
        window.feedbackActions.push({ sound_id: p.name, status: 'keep' });
      }
    });
    
    downloadBtn.innerHTML = 'Đang xử lý...';
    downloadBtn.style.pointerEvents = 'none';
    
    const payload = {
      job_id: window.currentJobId,
      actions: window.feedbackActions,
      final_placements: window.currentPlacements,
      bg_volume: getBgVolume()
    };
    
    try {
      const res = await fetch('/finalize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'ready') {
        window.location.href = data.url;
        downloadBtn.innerHTML = '<span>⬇️</span> Chốt & Tải Video';
        downloadBtn.style.pointerEvents = 'auto';
      } else if (data.status === 'processing') {
        pollReRender(data.task_id);
      }
    } catch (err) {
      showError(err.message);
    }
  };
}

function pollReRender(taskId) {
  statusLabel.textContent = '🎞️ Đang render lại video...';
  progressBar.style.width = '50%';
  resultCard.style.display = 'none';
  statusCard.style.display = 'block';
  STEPS.forEach(s => {
    const el = document.getElementById(`step-${s}`);
    if (el) el.className = (s === 'rendering') ? 'step active' : 'step done';
  });
  
  const interval = setInterval(async () => {
    const res = await fetch(`/status/${taskId}`);
    const data = await res.json();
    if (data.status === 'SUCCESS') {
      clearInterval(interval);
      window.location.href = `/download/${window.currentJobId}`;
      reset();
      downloadBtn.innerHTML = '<span>⬇️</span> Chốt & Tải Video';
      downloadBtn.style.pointerEvents = 'auto';
    } else if (data.status === 'FAILURE') {
      clearInterval(interval);
      showError('Lỗi render lại video');
    }
  }, 2000);
}
