'use strict';

(function () {
  const form        = document.getElementById('submit-form');
  const submitBtn   = document.getElementById('submit-btn');
  const btnLabel    = submitBtn.querySelector('.btn-label');
  const btnLoading  = submitBtn.querySelector('.btn-loading');
  const successEl   = document.getElementById('success-state');
  const fillEl      = document.getElementById('progress-fill');
  const labelEl     = document.getElementById('progress-label');

  // ── Utilities ────────────────────────────────────────
  function clearErrors() {
    form.querySelectorAll('.field-error').forEach(el => (el.textContent = ''));
    form.querySelectorAll('input').forEach(el => el.classList.remove('input-error'));
  }

  function showFieldError(name, msg) {
    const errEl = document.getElementById(name + '-error');
    const inp   = document.getElementById(name);
    if (errEl) errEl.textContent = msg;
    if (inp)   inp.classList.add('input-error');
  }

  function setLoading(on) {
    submitBtn.disabled = on;
    btnLabel.hidden    = on;
    btnLoading.hidden  = !on;
  }

  // ── Form submission ───────────────────────────────────
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    clearErrors();
    setLoading(true);

    const fd   = new FormData(form);
    const csrf = fd.get('csrfmiddlewaretoken');

    let data;
    try {
      const res = await fetch('/submit/', {
        method:  'POST',
        body:    fd,
        headers: { 'X-CSRFToken': csrf },
      });
      data = await res.json();
    } catch (_) {
      showFieldError('instagram_url', 'Network error — please try again.');
      setLoading(false);
      return;
    }

    if (data.success) {
      // Slide to success state
      form.hidden      = true;
      successEl.hidden = false;
      startCountdown(9 * 60);
      pollStatus(data.submission_id);
    } else {
      const errors = data.errors || {};
      Object.entries(errors).forEach(([k, v]) => showFieldError(k, v));
      setLoading(false);
    }
  });

  // ── Countdown progress bar ───────────────────────────
  function startCountdown(totalSecs) {
    let remaining = totalSecs;

    (function tick() {
      const ratio = remaining / totalSecs;
      fillEl.style.transform = 'scaleX(' + ratio + ')';

      if (remaining > 0) {
        const m = Math.floor(remaining / 60);
        const s = remaining % 60;
        labelEl.textContent = m + ':' + String(s).padStart(2, '0') + ' remaining';
        remaining -= 1;
        setTimeout(tick, 1000);
      } else {
        fillEl.style.transform  = 'scaleX(0)';
        labelEl.textContent     = 'Analysis complete — check your inbox.';
      }
    })();
  }

  // ── Status polling (every 10 s, up to 12 min) ────────
  function pollStatus(id) {
    let attempts = 0;

    const t = setInterval(async function () {
      if (++attempts > 72) { clearInterval(t); return; }

      let data;
      try {
        const res = await fetch('/status/' + id + '/');
        data = await res.json();
      } catch (_) { return; }

      if (data.status === 'matched' || data.status === 'waiting') {
        clearInterval(t);
        fillEl.style.transform = 'scaleX(0)';
        labelEl.textContent    = 'Done — check your inbox now.';
      } else if (data.status === 'failed') {
        clearInterval(t);
        labelEl.textContent = 'Something went wrong. Please try again later.';
      }
    }, 10_000);
  }
})();
