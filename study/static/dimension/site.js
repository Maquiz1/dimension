// Layout behaviour for the study pages (templates/dimension/base.html): sidebar, menus, page title and
// the idle-session timeout. The server also ends sessions after 30 idle minutes (SESSION_COOKIE_AGE).
(function () {
  'use strict';
  var script = document.currentScript;
  var logoutUrl = script.dataset.logoutUrl, loginUrl = script.dataset.loginUrl, csrf = script.dataset.csrf;

  // Navbar title: pages set <title>; show its first part ("Resources · DIMENSION Study" -> "Resources")
  var title = document.querySelector('.tb-title');
  if (title && !title.textContent.trim()) title.textContent = document.title.split(' · ')[0];

  // Sidebar: collapses to icons on desktop (remembered), slides in over the page on phones
  var sidebar = document.getElementById('sidebar');
  var toggle = document.getElementById('sidebarToggle');
  var mobile = function () { return window.matchMedia('(max-width: 768px)').matches; };
  try { if (!mobile() && localStorage.getItem('dimension-sidebar') === 'collapsed') sidebar.classList.add('collapsed'); } catch (e) {}
  if (toggle && sidebar) {
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      if (mobile()) { sidebar.classList.toggle('mobile-open'); return; }
      var collapsed = sidebar.classList.toggle('collapsed');
      try { localStorage.setItem('dimension-sidebar', collapsed ? 'collapsed' : 'open'); } catch (err) {}
    });
    document.addEventListener('click', function (e) {
      if (mobile() && sidebar.classList.contains('mobile-open') && !sidebar.contains(e.target)) sidebar.classList.remove('mobile-open');
    });
  }

  // Dropdown menus in the navbar (bell and profile)
  var buttons = document.querySelectorAll('[data-menu]');
  var closeAll = function (except) {
    buttons.forEach(function (b) {
      var menu = document.getElementById(b.dataset.menu);
      if (menu && menu !== except) { menu.hidden = true; b.setAttribute('aria-expanded', 'false'); }
    });
  };
  buttons.forEach(function (button) {
    var menu = document.getElementById(button.dataset.menu);
    button.addEventListener('click', function (e) {
      e.stopPropagation();
      closeAll(menu);
      menu.hidden = !menu.hidden;
      button.setAttribute('aria-expanded', String(!menu.hidden));
    });
  });
  document.addEventListener('click', function () { closeAll(null); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAll(null); });

  // Idle timeout: warn at 25 minutes, log out at 30
  var dialog = document.getElementById('sessionTimeout');
  if (!dialog || !logoutUrl) return;
  var WARN = 25 * 60 * 1000, COUNTDOWN = 300;
  var countdownEl = document.getElementById('sessionCountdown');
  var warnTimer, tick, left, warning = false;

  function logout() {
    fetch(logoutUrl, { method: 'POST', headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin' })
      .finally(function () { window.location.href = loginUrl; });
  }
  function warn() {
    warning = true; left = COUNTDOWN; countdownEl.textContent = left;
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
    tick = setInterval(function () {
      left -= 1; countdownEl.textContent = left;
      if (left <= 0) { clearInterval(tick); logout(); }
    }, 1000);
  }
  function reset() {
    if (warning) return;   // while the warning is open only its buttons count
    clearTimeout(warnTimer);
    warnTimer = setTimeout(warn, WARN);
  }
  document.getElementById('staySignedIn').addEventListener('click', function () {
    clearInterval(tick); warning = false; dialog.close();
    fetch(window.location.href, { method: 'HEAD', credentials: 'same-origin' });   // restarts the server's clock
    reset();
  });
  document.getElementById('logoutNow').addEventListener('click', logout);
  ['click', 'keydown', 'scroll', 'touchstart', 'mousemove'].forEach(function (ev) {
    document.addEventListener(ev, reset, { passive: true });
  });
  reset();
})();
