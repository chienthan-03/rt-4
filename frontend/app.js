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
          downloadBtn.href = `/download/${jobId}`;
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
