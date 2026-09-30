// One step on screen at a time. The step is in the URL (#tokens), so a link or a reload lands on
// it. Read mode shows everything; Practise mode hides code and answers until you ask for them.
(function () {
  const KEY = 'lldwb:' + SLUG + ':';
  const store = {
    get(k, d) { try { const v = localStorage.getItem(KEY + k); return v === null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(KEY + k, v); } catch (e) { /* private window: fine */ } },
  };
  const steps = Array.from(document.querySelectorAll('section.step'));
  const links = Array.from(document.querySelectorAll('nav.side a[data-step]'));
  const byId = Object.fromEntries(steps.map((s, i) => [s.id, i]));
  const prevBtn = document.getElementById('prev');
  const nextBtn = document.getElementById('next');
  const pos = document.getElementById('pos');
  let cur = -1;
  let seen = new Set((store.get('seen', '') || '').split(',').filter(Boolean));

  function title(i) { return steps[i].dataset.nav; }

  function show(i, keepScroll) {
    if (i < 0 || i >= steps.length) return;
    if (cur >= 0) steps[cur].classList.remove('on');
    cur = i;
    const s = steps[i];
    s.classList.add('on');
    links.forEach((a, k) => a.classList.toggle('on', k === i));
    seen.add(s.id);
    store.set('seen', Array.from(seen).join(','));
    links.forEach(a => a.classList.toggle('seen', seen.has(a.dataset.step)));
    pos.textContent = (i + 1) + ' / ' + steps.length;
    prevBtn.disabled = i === 0;
    nextBtn.disabled = i === steps.length - 1;
    const pn = s.querySelector('.pnav');
    if (pn) {
      pn.innerHTML = '';
      if (i > 0) pn.appendChild(navLink(i - 1, 'prev', '← previous'));
      if (i < steps.length - 1) pn.appendChild(navLink(i + 1, 'next', 'next →'));
    }
    store.set('step', s.id);
    if (location.hash !== '#' + s.id) history.replaceState(null, '', '#' + s.id);
    document.title = title(i) + ' · ' + document.body.dataset.name;
    if (!keepScroll) window.scrollTo(0, 0);
    document.body.classList.remove('navopen');
    const on = links[i];
    if (on && on.scrollIntoViewIfNeeded) on.scrollIntoViewIfNeeded(false);
  }

  function navLink(i, cls, label) {
    const a = document.createElement('a');
    a.href = '#' + steps[i].id;
    a.className = cls;
    a.innerHTML = '<small>' + label + '</small>';
    a.appendChild(document.createTextNode(title(i)));
    return a;
  }

  function fromHash() {
    const id = decodeURIComponent(location.hash.slice(1));
    if (id in byId) { show(byId[id]); return true; }
    // a link to something inside a step: open that step, then scroll to it
    const el = id && document.getElementById(id);
    if (el) {
      const st = el.closest('section.step');
      if (st) { show(byId[st.id], true); el.scrollIntoView(); return true; }
    }
    return false;
  }

  window.addEventListener('hashchange', fromHash);
  prevBtn.addEventListener('click', () => show(cur - 1));
  nextBtn.addEventListener('click', () => show(cur + 1));
  document.addEventListener('keydown', e => {
    const t = e.target;
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
    if (e.key === 'ArrowRight') { show(cur + 1); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { show(cur - 1); e.preventDefault(); }
  });
  document.querySelector('.navtoggle').addEventListener('click', () => document.body.classList.toggle('navopen'));
  document.getElementById('main').addEventListener('click', () => document.body.classList.remove('navopen'));

  // ---- Read / Practise
  const modeBtns = Array.from(document.querySelectorAll('.modes button'));
  function setMode(m) {
    document.body.classList.toggle('practise', m === 'practise');
    modeBtns.forEach(b => b.classList.toggle('on', b.dataset.mode === m));
    store.set('mode', m);
  }
  modeBtns.forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
  setMode(store.get('mode', 'read'));

  document.addEventListener('click', e => {
    const rv = e.target.closest('button.reveal');
    if (rv) { const box = rv.closest('.solbox'); if (box) box.classList.add('shown'); return; }
    const dm = e.target.closest('.delmark');
    if (dm) { const code = dm.closest('.code'); if (code) code.classList.toggle('showdel'); return; }
    const qa = e.target.closest('.qa');
    if (qa && document.body.classList.contains('practise')) qa.classList.toggle('open');
  });

  // ---- copy buttons: the text is kept verbatim in a <script type="text/plain" class="raw">
  function copyText(text, btn) {
    const done = () => {
      const old = btn.textContent;
      btn.textContent = 'copied';
      btn.classList.add('done');
      setTimeout(() => { btn.textContent = old; btn.classList.remove('done'); }, 1400);
    };
    const fallback = () => {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); done(); } catch (err) { /* nothing more to try */ }
      ta.remove();
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  }
  document.querySelectorAll('button.copy').forEach(btn => {
    btn.addEventListener('click', () => {
      const holder = btn.closest('.code, .copybox');
      const raw = holder && holder.querySelector('script.raw');
      if (raw) copyText(raw.textContent.replace(/<\\\//g, '</'), btn);
    });
  });

  // ---- timers: click to start or pause; when time is up, click to reset
  document.querySelectorAll('button.timer').forEach(btn => {
    const total = parseInt(btn.dataset.min, 10) * 60;
    let left = total, handle = null;
    const tv = btn.querySelector('.tv');
    const label = btn.querySelector('.tl');
    const paint = () => {
      const m = Math.floor(left / 60), s = left % 60;
      tv.textContent = m + ':' + String(s).padStart(2, '0');
    };
    btn.addEventListener('click', () => {
      if (left <= 0) {
        left = total; btn.classList.remove('over'); label.textContent = 'start'; paint(); return;
      }
      if (handle) {
        clearInterval(handle); handle = null; btn.classList.remove('running'); label.textContent = 'resume'; return;
      }
      btn.classList.add('running');
      label.textContent = 'pause';
      handle = setInterval(() => {
        left -= 1; paint();
        if (left <= 0) {
          clearInterval(handle); handle = null;
          btn.classList.remove('running'); btn.classList.add('over'); label.textContent = 'time — reset';
        }
      }, 1000);
    });
  });

  // ---- things you write on the page are kept in this browser
  document.querySelectorAll('textarea[data-key]').forEach(ta => {
    ta.value = store.get('note:' + ta.dataset.key, '');
    ta.addEventListener('input', () => store.set('note:' + ta.dataset.key, ta.value));
  });
  document.querySelectorAll('input[type=checkbox][data-key]').forEach(cb => {
    cb.checked = store.get('cb:' + cb.dataset.key, '') === '1';
    cb.addEventListener('change', () => store.set('cb:' + cb.dataset.key, cb.checked ? '1' : ''));
  });

  if (!fromHash()) {
    const last = store.get('step', '');
    show(last in byId ? byId[last] : 0);
  }
})();
