'use strict';

(function () {
  const form        = document.getElementById('submit-form');
  const submitBtn   = document.getElementById('submit-btn');
  const btnText     = submitBtn.querySelector('.btn-text');
  const btnLoader   = submitBtn.querySelector('.btn-loader');
  const successEl   = document.getElementById('success-state');
  const barEl       = document.getElementById('countdown-bar');
  const labelEl     = document.getElementById('countdown-label');

  // ── Helpers ──────────────────────────────────────────────────
  function clearErrors() {
    document.querySelectorAll('.field-error').forEach(el => (el.textContent = ''));
    document.querySelectorAll('input').forEach(el => el.classList.remove('input-error'));
  }

  function showError(fieldName, message) {
    const errEl = document.getElementById(fieldName + '-error');
    const input = document.getElementById(fieldName);
    if (errEl) errEl.textContent = message;
    if (input) input.classList.add('input-error');
  }

  function setLoading(on) {
    submitBtn.disabled = on;
    btnText.hidden = on;
    btnLoader.hidden = !on;
  }

  // ── Form submit ───────────────────────────────────────────────
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    clearErrors();
    setLoading(true);

    const formData = new FormData(form);
    const csrfToken = formData.get('csrfmiddlewaretoken');

    let data;
    try {
      const res = await fetch('/submit/', {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRFToken': csrfToken },
      });
      data = await res.json();
    } catch (_) {
      showError('instagram_url', 'Network error — please try again.');
      setLoading(false);
      return;
    }

    if (data.success) {
      form.hidden = true;
      successEl.hidden = false;
      startCountdown(9 * 60);
      pollStatus(data.submission_id);
    } else {
      const errors = data.errors || {};
      Object.entries(errors).forEach(([field, msg]) => showError(field, msg));
      setLoading(false);
    }
  });

  // ── Countdown ─────────────────────────────────────────────────
  function startCountdown(totalSeconds) {
    let remaining = totalSeconds;

    function tick() {
      const progress = remaining / totalSeconds;
      // bar shrinks left-to-right as time runs out
      barEl.style.transform = 'scaleX(' + progress + ')';

      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      labelEl.textContent =
        remaining > 0
          ? m + ':' + String(s).padStart(2, '0') + ' remaining'
          : 'Analysis complete — check your inbox!';

      if (remaining > 0) {
        remaining -= 1;
        setTimeout(tick, 1000);
      }
    }

    tick();
  }

  // ── Status polling ────────────────────────────────────────────
  function pollStatus(submissionId) {
    let attempts = 0;
    const MAX_ATTEMPTS = 60; // 10 minutes at 10s intervals

    const timer = setInterval(async function () {
      attempts += 1;
      if (attempts > MAX_ATTEMPTS) {
        clearInterval(timer);
        return;
      }

      let data;
      try {
        const res = await fetch('/status/' + submissionId + '/');
        data = await res.json();
      } catch (_) {
        return; // network blip — keep polling
      }

      const done = ['matched', 'waiting', 'failed'];
      if (done.includes(data.status)) {
        clearInterval(timer);
        if (data.status === 'matched' || data.status === 'waiting') {
          labelEl.textContent = 'Done! Check your inbox now.';
          barEl.style.transform = 'scaleX(0)';
        } else {
          labelEl.textContent = 'Something went wrong — please try again later.';
        }
      }
    }, 10000);
  }
})();
