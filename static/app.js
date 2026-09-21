/* ============================================================
   Viral Clip Agent — Frontend Logic
   ============================================================ */

const API_BASE = (function() {
  var raw = "__PORT_5000__";
  if (raw.startsWith("__")) {
    return "http://localhost:5000";
  }
  var path = window.location.pathname;
  var proxyBase = path.split("/web/")[0];
  return window.location.origin + proxyBase + "/" + raw;
})();

// --- State ---
let currentJobId = null;
let pollInterval = null;
let isDemoMode = false;

// --- Theme ---
(function() {
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = 'dark';
  root.setAttribute('data-theme', theme);
  toggle && toggle.addEventListener('click', () => {
    theme = theme === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', theme);
    toggle.innerHTML = theme === 'dark'
      ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'
      : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
  });
})();

// --- Upload Zone ---
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');

uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', (e) => {
  if (e.target.files.length) handleFile(e.target.files[0]);
});

function handleFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('sample', 'true');
  startJob(formData);
}

// --- Demo Button ---
document.getElementById('demoBtn').addEventListener('click', () => {
  if (typeof DEMO_DATA === 'undefined') {
    alert('Demo data not loaded. Please refresh the page.');
    return;
  }
  
  isDemoMode = true;
  document.getElementById('demoBtn').disabled = true;
  document.getElementById('demoBtn').innerHTML = '<span class="status-dot"></span> Running demo...';
  
  showPipeline();
  runDemoPipeline();
});

function runDemoPipeline() {
  // Animate pipeline stages client-side
  const stages = DEMO_DATA.stages || [];
  let stageIdx = 0;
  
  function nextStage() {
    if (stageIdx >= stages.length) {
      // All stages done — render results
      setTimeout(() => {
        updateStatus('Complete');
        document.getElementById('statusBadge').classList.add('complete');
        renderResults(DEMO_DATA, true);
      }, 500);
      return;
    }
    
    // Skip duplicate "running" entries (each stage has a running + complete entry)
    const stage = stages[stageIdx];
    if (stage.status === 'running') {
      updateStage(stage.name, 'running', '');
      stageIdx++;
      setTimeout(nextStage, 600);
    } else if (stage.status === 'complete') {
      updateStage(stage.name, 'complete', stage.detail);
      stageIdx++;
      setTimeout(nextStage, 800);
    } else {
      stageIdx++;
      setTimeout(nextStage, 100);
    }
  }
  
  nextStage();
}

// --- Start Job (real upload) ---
function startJob(formData) {
  isDemoMode = false;
  document.getElementById('heroSection').style.display = 'none';
  showPipeline();
  
  fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      startPolling(data.job_id);
    })
    .catch(err => {
      console.error(err);
      alert('Upload failed. The backend server may not be running. Try the demo instead.');
      location.reload();
    });
}

// --- Pipeline Visualization ---
function showPipeline() {
  document.getElementById('heroSection').style.display = 'none';
  document.getElementById('pipelineSection').style.display = 'block';
  document.getElementById('statusBadge').style.display = 'flex';
  updateStatus('Processing...');
}

function updateStatus(text) {
  document.getElementById('statusText').textContent = text;
}

function updateStage(stageName, status, detail) {
  const stageMap = {
    'Ingest': 'ingest',
    'Transcription': 'transcription',
    'Clip Scout': 'scout',
    'Edit Agent': 'edit',
    'Packaging Agent': 'packaging',
  };
  
  const stageKey = stageMap[stageName];
  if (!stageKey) return;
  
  const card = document.querySelector(`[data-stage="${stageKey}"]`);
  if (!card) return;
  
  card.classList.remove('running', 'complete');
  if (status === 'running') {
    card.classList.add('running');
    card.querySelector('.stage-status').textContent = 'Running...';
  } else if (status === 'complete') {
    card.classList.add('complete');
    card.querySelector('.stage-status').textContent = detail || 'Done';
  }
}

// --- Polling (for real uploads) ---
function startPolling(jobId) {
  currentJobId = jobId;
  
  if (pollInterval) clearInterval(pollInterval);
  
  pollInterval = setInterval(() => {
    fetch(`${API_BASE}/api/job/${jobId}`)
      .then(r => r.json())
      .then(data => {
        if (data.status === 'complete') {
          clearInterval(pollInterval);
          updateStatus('Complete');
          document.getElementById('statusBadge').classList.add('complete');
          renderResults(data.result, false);
        } else if (data.status === 'error') {
          clearInterval(pollInterval);
          updateStatus('Error');
          alert('Pipeline error: ' + (data.error || 'Unknown'));
        } else {
          updateStatus('Processing...');
          if (data.result && data.result.stages) {
            for (const stage of data.result.stages) {
              updateStage(stage.name, stage.status, stage.detail);
            }
          }
        }
      })
      .catch(err => console.error('Polling error:', err));
  }, 1500);
}

// --- Results Rendering ---
function renderResults(result, demo) {
  document.getElementById('pipelineSection').style.display = 'none';
  document.getElementById('resultsSection').style.display = 'block';
  
  const clips = result.clips || [];
  document.getElementById('resultCount').textContent = `— ${clips.length} clips found`;
  
  // Highlight agent roster
  document.querySelectorAll('.agent-chip').forEach((chip, i) => {
    setTimeout(() => chip.classList.add('active'), i * 100);
  });
  
  const grid = document.getElementById('clipsGrid');
  grid.innerHTML = '';
  
  clips.forEach((clip, index) => {
    const card = createClipCard(clip, index, result.job_id, demo);
    grid.appendChild(card);
  });
}

function createClipCard(clip, index, jobId, demo) {
  const card = document.createElement('div');
  card.className = 'clip-card';
  card.style.animationDelay = `${index * 0.1}s`;
  card.style.animation = 'fadeIn 0.5s ease backwards';
  
  // Thumbnail
  const thumbWrapper = document.createElement('div');
  thumbWrapper.className = 'clip-thumb-wrapper';
  
  const rank = document.createElement('div');
  rank.className = 'clip-rank';
  rank.textContent = `#${index + 1}`;
  thumbWrapper.appendChild(rank);
  
  const scoreBadge = document.createElement('div');
  scoreBadge.className = 'clip-score-badge';
  scoreBadge.innerHTML = `⭐ ${clip.consensus_score || 0}`;
  thumbWrapper.appendChild(scoreBadge);
  
  // Agreement badge
  if (clip.agreement && clip.agreement >= 4) {
    const agreeBadge = document.createElement('div');
    agreeBadge.className = 'clip-agreement-badge';
    agreeBadge.innerHTML = `✓ ${clip.agreement}/5 agents agree`;
    thumbWrapper.appendChild(agreeBadge);
  }
  
  // Thumbnail image
  const thumbSrc = demo ? clip.thumbnail_data : `${API_BASE}/api/job/${jobId}/thumbnails/${(clip.thumbnail || '').replace('thumbnails/', '')}`;
  if (thumbSrc) {
    const img = document.createElement('img');
    img.className = 'clip-thumb';
    img.src = thumbSrc;
    img.alt = 'Clip thumbnail';
    thumbWrapper.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'clip-thumb-placeholder';
    placeholder.textContent = '🎬';
    thumbWrapper.appendChild(placeholder);
  }
  
  card.appendChild(thumbWrapper);
  
  // Body
  const body = document.createElement('div');
  body.className = 'clip-body';
  
  // Timestamp
  const ts = document.createElement('div');
  ts.className = 'clip-timestamp';
  ts.textContent = `${formatTime(clip.start)} — ${formatTime(clip.end)} (${clip.duration}s)`;
  body.appendChild(ts);
  
  // Title options
  if (clip.titles && clip.titles.length) {
    const titlesDiv = document.createElement('div');
    titlesDiv.className = 'clip-title-options';
    clip.titles.slice(0, 3).forEach((title, i) => {
      const titleEl = document.createElement('div');
      titleEl.className = 'clip-title';
      titleEl.textContent = title;
      titlesDiv.appendChild(titleEl);
    });
    body.appendChild(titlesDiv);
  }
  
  // Agent scores
  if (clip.agent_scores && clip.agent_scores.length) {
    const scoresDiv = document.createElement('div');
    scoresDiv.className = 'clip-agent-scores';
    clip.agent_scores.forEach(score => {
      const scoreEl = document.createElement('div');
      scoreEl.className = 'agent-score' + (score.score >= 6 ? ' high' : '');
      scoreEl.innerHTML = `<span class="agent-score-icon">${score.icon}</span> ${score.agent} <span class="agent-score-value">${score.score}</span>`;
      scoreEl.title = score.rationale;
      scoresDiv.appendChild(scoreEl);
    });
    body.appendChild(scoresDiv);
  }
  
  // Rationale (from top agent)
  if (clip.agent_scores && clip.agent_scores.length) {
    const topAgent = [...clip.agent_scores].sort((a, b) => b.score - a.score)[0];
    const rationale = document.createElement('div');
    rationale.className = 'clip-rationale';
    rationale.textContent = `${topAgent.icon} ${topAgent.agent}: ${topAgent.rationale}`;
    body.appendChild(rationale);
  }
  
  // Description / hashtags
  if (clip.description) {
    const desc = document.createElement('div');
    desc.className = 'clip-description';
    desc.textContent = clip.description;
    body.appendChild(desc);
  }
  
  card.appendChild(body);
  
  // Actions
  const actions = document.createElement('div');
  actions.className = 'clip-actions';
  
  if (!demo) {
    // Real upload — show download buttons
    if (clip.clip_path) {
      const dlBtn = document.createElement('a');
      dlBtn.className = 'btn-download';
      dlBtn.href = `${API_BASE}/api/job/${jobId}/clips/${clip.clip_path.replace('clips/', '')}`;
      dlBtn.download = `clip_${index + 1}.mp4`;
      dlBtn.innerHTML = '⬇ Clip (16:9)';
      actions.appendChild(dlBtn);
    }
    
    if (clip.vertical_path) {
      const vertBtn = document.createElement('a');
      vertBtn.className = 'btn-download';
      vertBtn.href = `${API_BASE}/api/job/${jobId}/clips/${clip.vertical_path.replace('clips/', '')}`;
      vertBtn.download = `clip_${index + 1}_vertical.mp4`;
      vertBtn.innerHTML = '📱 Vertical (9:16)';
      actions.appendChild(vertBtn);
    }
    
    if (clip.thumbnail) {
      const thumbBtn = document.createElement('a');
      thumbBtn.className = 'btn-download';
      thumbBtn.href = `${API_BASE}/api/job/${jobId}/thumbnails/${clip.thumbnail.replace('thumbnails/', '')}`;
      thumbBtn.download = `clip_${index + 1}_thumb.jpg`;
      thumbBtn.innerHTML = '🖼 Thumbnail';
      actions.appendChild(thumbBtn);
    }
  } else {
    // Demo mode — show thumbnail download only (data URL)
    if (clip.thumbnail_data) {
      const thumbBtn = document.createElement('a');
      thumbBtn.className = 'btn-download';
      thumbBtn.href = clip.thumbnail_data;
      thumbBtn.download = `clip_${index + 1}_thumb.jpg`;
      thumbBtn.innerHTML = '🖼 Thumbnail';
      actions.appendChild(thumbBtn);
    }
    
    // Info note for demo
    const info = document.createElement('div');
    info.className = 'demo-info';
    info.innerHTML = '💡 Upload a real video to get downloadable clips with captions';
    actions.appendChild(info);
  }
  
  card.appendChild(actions);
  
  return card;
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
