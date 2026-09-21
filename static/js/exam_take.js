(function () {
  const submitButton = document.getElementById('submit-exam');
  const examTimer = document.getElementById('exam-timer');
  const DURATION_SECONDS = window.examData ? (window.examData.durationSeconds || 300) : 300;
  let remainingSeconds = DURATION_SECONDS;
  let timerId = null;

  function formatTime(seconds) {
    const mins = String(Math.floor(seconds / 60)).padStart(2, '0');
    const secs = String(seconds % 60).padStart(2, '0');
    return `${mins}:${secs}`;
  }

  function updateTimer() {
    remainingSeconds -= 1;
    if (examTimer) examTimer.textContent = formatTime(remainingSeconds);
    if (remainingSeconds <= 0) {
      clearInterval(timerId);
      alert('Time is up. Your exam will be submitted automatically.');
      submitExam();
    }
  }

  function startTimer() {
    if (examTimer) examTimer.textContent = formatTime(remainingSeconds);
    timerId = setInterval(updateTimer, 1000);
  }

  const monitorVideo = document.getElementById('monitor-video');
  const monitorCanvas = document.getElementById('monitor-canvas');
  const monitorStatusText = document.getElementById('monitor-status-text');
  const monitorEventLog = document.getElementById('monitor-event-log');
  const faceAbsentCount = document.getElementById('face-absent-count');
  const focusLossCount = document.getElementById('focus-loss-count');
  const tabSwitchCount = document.getElementById('tab-switch-count');
  const suspicionBadge = document.getElementById('suspicion-level-badge');
  const multiFaceCountEl = document.getElementById('multi-face-count');

  const MONITOR_INTERVAL_MS = 2500;
  let monitorStream = null;
  let monitorTimerId = null;
  let lastFocusTime = Date.now();
  let lastTabSwitchTime = 0;
  let focusCount = 0;
  let tabSwitchCountValue = 0;
  let faceAbsentCountValue = 0;
  let faceAbsentTotalSeconds = 0;
  let multiFaceCountValue = 0;
  let isMultiFaceActive = false;
  let unauthorizedActionsCountValue = 0;
  let monitorEvents = [];
  let unsyncedEvents = [];
  let lastFaceAbsentTimestamp = null;
  let currentSuspicionLevel = 'LOW';

  function formatMonitorTime(seconds) {
    return `${Math.round(seconds)}s`;
  }

  function pushMonitorEvent(type, details, severity) {
    const event = {
      timestamp: Date.now(),
      type,
      details: details || '',
      severity: severity || 'WARNING',
    };
    monitorEvents.unshift(event);
    if (monitorEvents.length > 30) monitorEvents.pop();
    unsyncedEvents.push(event);
    renderMonitorEvents();
    sendMonitorEvents();
  }

  function renderMonitorEvents() {
    if (!monitorEventLog) return;
    monitorEventLog.innerHTML = monitorEvents
      .slice(0, 7)
      .map((event) => {
        const timeStr = new Date(event.timestamp).toLocaleTimeString();
        let badgeClass = 'event-info';
        if (event.severity === 'WARNING') badgeClass = 'event-warning';
        if (event.severity === 'CRITICAL') badgeClass = 'event-critical';
        return `<li class="${badgeClass}"><span class="event-time">${timeStr}</span> <strong>${event.type}</strong>: ${event.details}</li>`;
      })
      .join('');
  }

  function setMonitorStatus(message, isWarning) {
    if (monitorStatusText) {
      monitorStatusText.textContent = message;
      if (isWarning) {
        monitorStatusText.classList.add('warning-text');
      } else {
        monitorStatusText.classList.remove('warning-text');
      }
    }
  }

  function updateSummary() {
    let currentTotalSecs = faceAbsentTotalSeconds;
    if (lastFaceAbsentTimestamp !== null) {
      currentTotalSecs += (Date.now() - lastFaceAbsentTimestamp) / 1000;
    }

    if (faceAbsentCount) {
      faceAbsentCount.textContent = `${faceAbsentCountValue} times (${formatMonitorTime(currentTotalSecs)})`;
    }
    if (focusLossCount) focusLossCount.textContent = focusCount;
    if (tabSwitchCount) tabSwitchCount.textContent = tabSwitchCountValue;
    if (multiFaceCountEl) multiFaceCountEl.textContent = multiFaceCountValue;
    if (suspicionBadge) {
      suspicionBadge.textContent = currentSuspicionLevel;
      suspicionBadge.className = `badge badge-${currentSuspicionLevel.toLowerCase()}`;
    }
  }

  async function startMonitorCamera() {
    if (!monitorVideo || !monitorCanvas) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setMonitorStatus('Webcam capture unsupported on this browser.', true);
      alert("CAMERA ERROR: Webcam access is disabled by your browser. This usually happens if you are accessing the page via an IP address (e.g., http://192.168.x.x) instead of http://localhost:5000 or HTTPS. Please use localhost if you are on the same machine, or set up HTTPS.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      monitorStream = stream;
      monitorVideo.srcObject = stream;
      monitorVideo.play().catch(() => {});
      setMonitorStatus('Webcam active. Face & event monitoring engaged.', false);
      if (monitorTimerId) clearInterval(monitorTimerId);
      monitorTimerId = setInterval(captureFaceFrame, MONITOR_INTERVAL_MS);
      pushMonitorEvent('monitoring_started', 'Camera initialized', 'INFO');
    } catch (error) {
      console.error('Failed to start webcam', error);
      setMonitorStatus('Camera permission denied or unavailable.', true);
      alert("CAMERA ERROR: Could not access the webcam. Please ensure your browser has permission to access the camera, and no other app is using it. Error: " + error.message);
    }
  }

  function stopMonitorCamera() {
    if (monitorTimerId) {
      clearInterval(monitorTimerId);
      monitorTimerId = null;
    }
    if (monitorStream) {
      monitorStream.getTracks().forEach((track) => track.stop());
      monitorStream = null;
    }
    if (monitorVideo) {
      monitorVideo.srcObject = null;
    }
  }

  async function sendMonitorEvents() {
    const eventsToSend = [...unsyncedEvents];
    unsyncedEvents = [];

    try {
      let currentTotalSecs = faceAbsentTotalSeconds;
      if (lastFaceAbsentTimestamp !== null) {
        currentTotalSecs += (Date.now() - lastFaceAbsentTimestamp) / 1000;
      }

      const resp = await fetch('/exam/monitor/log-events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: window.examData.email,
          course: window.examData.courseId,
          session_id: window.examData.sessionId,
          events: eventsToSend,
          summary: {
            focusLossCount: focusCount,
            tabSwitchCount: tabSwitchCountValue,
            faceAbsentCount: faceAbsentCountValue,
            faceAbsentTotalSeconds: currentTotalSecs,
            multiFaceCount: multiFaceCountValue,
            unauthorizedActionsCount: unauthorizedActionsCountValue,
          },
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.suspicion_level) {
          currentSuspicionLevel = data.suspicion_level;
          updateSummary();
        }
      } else {
        // Re-queue unsynced events on failure
        unsyncedEvents.push(...eventsToSend);
      }
    } catch (err) {
      console.warn('Event log failed', err);
      unsyncedEvents.push(...eventsToSend);
    }
  }

  async function captureFaceFrame() {
    if (!monitorVideo || !monitorCanvas || monitorVideo.readyState < 2) return;

    const ctx = monitorCanvas.getContext('2d');
    ctx.drawImage(monitorVideo, 0, 0, monitorCanvas.width, monitorCanvas.height);
    const imageData = monitorCanvas.toDataURL('image/jpeg', 0.7);

    try {
      const response = await fetch('/exam/monitor/face-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: window.examData.email,
          course: window.examData.courseId,
          session_id: window.examData.sessionId,
          image_data: imageData,
        }),
      });
      const data = await response.json();

      if (data.face_present) {
        if (data.is_multi_face) {
          if (!isMultiFaceActive) {
            multiFaceCountValue += 1;
            isMultiFaceActive = true;
            pushMonitorEvent('multi_face_detected', `${data.face_count} faces present`, 'CRITICAL');
          }
          setMonitorStatus(`WARNING: ${data.face_count} faces detected!`, true);
        } else {
          isMultiFaceActive = false;
          setMonitorStatus('Face verified. Monitoring normal.', false);
        }

        if (lastFaceAbsentTimestamp !== null) {
          const absentSecs = Math.round((Date.now() - lastFaceAbsentTimestamp) / 1000);
          faceAbsentTotalSeconds += absentSecs;
          lastFaceAbsentTimestamp = null;
          pushMonitorEvent('face_returned', `Returned after ${absentSecs}s`, 'INFO');
        }
      } else {
        setMonitorStatus('WARNING: Face absent from camera frame!', true);
        if (lastFaceAbsentTimestamp === null) {
          lastFaceAbsentTimestamp = Date.now();
          faceAbsentCountValue += 1;
          pushMonitorEvent('face_absent_started', `Face disappeared (Absence #${faceAbsentCountValue})`, 'WARNING');
        }
      }
      updateSummary();
    } catch (err) {
      console.warn('Face capture error', err);
    }
  }

  // Event Listeners for Browser Activity & Interactions
  function trackVisibility() {
    const now = Date.now();
    if (document.hidden || document.visibilityState === 'hidden') {
      lastTabSwitchTime = now;
      tabSwitchCountValue += 1;
      pushMonitorEvent('tab_switch', `Switch #${tabSwitchCountValue}`, 'WARNING');
    } else {
      pushMonitorEvent('tab_returned', 'Focus back on exam tab', 'INFO');
    }
    updateSummary();
  }

  function trackBlur() {
    const now = Date.now();
    // Avoid double counting if visibilitychange already fired for tab switch
    if (now - lastTabSwitchTime > 500) {
      focusCount += 1;
      pushMonitorEvent('focus_loss', `Window lost focus #${focusCount}`, 'WARNING');
      updateSummary();
    }
  }

  function trackFocus() {
    const now = Date.now();
    if (now - lastFocusTime > 800) {
      pushMonitorEvent('window_focus', 'Window focus regained', 'INFO');
      lastFocusTime = now;
      updateSummary();
    }
  }

  function trackMouseLeave() {
    pushMonitorEvent('mouse_leave', 'Cursor left browser window viewport', 'WARNING');
  }

  function trackContextMenu(e) {
    e.preventDefault();
    unauthorizedActionsCountValue += 1;
    pushMonitorEvent('context_menu', 'Right-click attempt blocked', 'WARNING');
    updateSummary();
  }

  function trackCopyPaste(e) {
    unauthorizedActionsCountValue += 1;
    pushMonitorEvent('copy_paste', `Clipboard action: ${e.type}`, 'WARNING');
    updateSummary();
  }

  function trackKeyDown(e) {
    // Detect forbidden keys (F12, Ctrl+Shift+I)
    if (e.key === 'F12' || (e.ctrlKey && e.shiftKey && e.key === 'I')) {
      e.preventDefault();
      unauthorizedActionsCountValue += 1;
      pushMonitorEvent('shortcut_key', 'DevTools attempt blocked', 'CRITICAL');
    }
    // Note: Alt+Tab is already tracked via visibilitychange, no duplicate count
    updateSummary();
  }

  function collectAnswers() {
    const answers = [];
    const questionCards = document.querySelectorAll('.question-card');
    questionCards.forEach((card) => {
      const selected = card.querySelector('input[type="radio"]:checked');
      answers.push(selected ? selected.value : '');
    });
    return answers;
  }

  async function submitExam() {
    stopMonitorCamera();

    // Add current open absence duration if applicable
    if (lastFaceAbsentTimestamp !== null) {
      faceAbsentTotalSeconds += (Date.now() - lastFaceAbsentTimestamp) / 1000;
      lastFaceAbsentTimestamp = null;
    }

    const payload = {
      course: window.examData.courseId,
      session_id: window.examData.sessionId,
      name: window.examData.name,
      email: window.examData.email,
      answers: collectAnswers(),
      monitorSummary: {
        faceAbsentTotalSeconds,
        faceAbsentCount: faceAbsentCountValue,
        focusLossCount: focusCount,
        tabSwitchCount: tabSwitchCountValue,
        multiFaceCount: multiFaceCountValue,
        unauthorizedActionsCount: unauthorizedActionsCountValue,
      },
      events: monitorEvents,
    };

    try {
      const response = await fetch('/exam/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error(`Server status ${response.status}`);
      const data = await response.json();

      if (data.status === 'ok') {
        window.location = `/exam/report/${data.session_id}`;
      } else {
        alert('Failed to submit exam. Please try again.');
      }
    } catch (error) {
      console.error('Submit error:', error);
      alert('Submit failed. Check connection and try again.');
    }
  }

  if (submitButton) {
    submitButton.addEventListener('click', (event) => {
      event.preventDefault();
      if (confirm('Are you sure you want to submit your exam now?')) {
        if (timerId) clearInterval(timerId);
        submitExam();
      }
    });
  }

  // Pagination logic
  const questionCards = document.querySelectorAll('.question-card');
  const navBtns = document.querySelectorAll('.question-nav-btn');
  const prevBtn = document.getElementById('prev-question');
  const nextBtn = document.getElementById('next-question');
  let currentQuestionIndex = 0;

  function showQuestion(index) {
    if (index < 0 || index >= questionCards.length) return;
    
    questionCards.forEach((card, i) => {
      if (i === index) {
        card.style.display = 'block';
      } else {
        card.style.display = 'none';
      }
    });

    navBtns.forEach((btn) => btn.classList.remove('active'));
    if (navBtns[index]) {
      navBtns[index].classList.add('active');
    }

    currentQuestionIndex = index;
  }

  if (questionCards.length > 0) {
    showQuestion(0);
  }

  navBtns.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const targetIdx = parseInt(e.target.getAttribute('data-target'), 10);
      showQuestion(targetIdx);
    });
  });

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentQuestionIndex > 0) showQuestion(currentQuestionIndex - 1);
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (currentQuestionIndex < questionCards.length - 1) showQuestion(currentQuestionIndex + 1);
    });
  }

  // Register browser activity event listeners
  document.addEventListener('visibilitychange', trackVisibility);
  window.addEventListener('blur', trackBlur);
  window.addEventListener('focus', trackFocus);
  document.addEventListener('mouseleave', trackMouseLeave);
  document.addEventListener('contextmenu', trackContextMenu);
  document.addEventListener('copy', trackCopyPaste);
  document.addEventListener('paste', trackCopyPaste);
  document.addEventListener('keydown', trackKeyDown);

  if (monitorVideo) {
    startMonitorCamera();
  }

  startTimer();
})();
