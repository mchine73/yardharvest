/* ===================================================================
   YardHarvest bespoke dialogs (vanilla JS) — server-rendered pages
   -------------------------------------------------------------------
   The mirror of the React SPA's dialog system, for the Jinja-rendered
   CRM (and legacy dev templates). Replaces window.alert/confirm/prompt
   with animated in-app toasts + modal.

   Public API (window.YHDialog):
     toast(message, { type, duration })          -> id
     confirm({ message, title, confirmText,
               cancelText, danger })              -> Promise<boolean>
     prompt({ message, title, defaultValue,
              placeholder, inputType,
              confirmText, cancelText })          -> Promise<string|null>

   Declarative retrofit (no inline JS needed — CSP friendly):
     <form data-confirm="Delete X?">...</form>
        intercepts submit, asks, submits on OK.
     <a data-confirm="..."> / <button type=button data-confirm="...">
        intercepts click, follows href / re-clicks on OK.
     <form data-prompt="Reason?" data-prompt-target="reason"
           [data-prompt-optional]>
        intercepts submit, asks for text, writes it into the named
        field, then submits. Cancel aborts (unless optional + empty).
   =================================================================== */
(function () {
  'use strict';
  if (window.YHDialog) return;

  // ---- Inject styles once ----
  var CSS = `
  .yh-toast-stack{position:fixed;top:1rem;right:1rem;z-index:20000;display:flex;flex-direction:column;gap:.6rem;max-width:min(92vw,380px);pointer-events:none}
  .yh-toast{pointer-events:auto;display:flex;align-items:flex-start;gap:.65rem;padding:.85rem 1rem;border-radius:12px;background:#fff;color:#1a2e25;box-shadow:0 10px 30px rgba(0,0,0,.18);border-left:5px solid #2d6a4f;font-size:.92rem;line-height:1.35;animation:yh-toast-in .32s cubic-bezier(.18,.89,.32,1.28) both}
  .yh-toast.leaving{animation:yh-toast-out .25s ease forwards}
  .yh-toast .yh-toast-icon{font-size:1.15rem;line-height:1.2;flex-shrink:0}
  .yh-toast .yh-toast-msg{flex:1;word-break:break-word}
  .yh-toast .yh-toast-close{background:none;border:none;color:inherit;opacity:.5;cursor:pointer;font-size:1rem;padding:0;line-height:1;flex-shrink:0}
  .yh-toast .yh-toast-close:hover{opacity:1}
  .yh-toast.success{border-left-color:#2d6a4f}.yh-toast.success .yh-toast-icon{color:#2d6a4f}
  .yh-toast.error{border-left-color:#dc3545}.yh-toast.error .yh-toast-icon{color:#dc3545}
  .yh-toast.info{border-left-color:#1b6ec2}.yh-toast.info .yh-toast-icon{color:#1b6ec2}
  .yh-toast.warning{border-left-color:#e6a700}.yh-toast.warning .yh-toast-icon{color:#e6a700}
  @keyframes yh-toast-in{from{opacity:0;transform:translateX(120%) scale(.95)}to{opacity:1;transform:translateX(0) scale(1)}}
  @keyframes yh-toast-out{from{opacity:1;transform:translateX(0)}to{opacity:0;transform:translateX(120%)}}
  .yh-modal-backdrop{position:fixed;inset:0;z-index:19000;background:rgba(15,30,24,.55);backdrop-filter:blur(2px);display:flex;align-items:center;justify-content:center;padding:1rem;animation:yh-backdrop-in .2s ease both}
  .yh-modal-backdrop.leaving{animation:yh-backdrop-out .18s ease forwards}
  .yh-modal{background:#fff;border-radius:16px;max-width:440px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.35);overflow:hidden;animation:yh-modal-in .34s cubic-bezier(.18,.89,.32,1.28) both}
  .yh-modal-backdrop.leaving .yh-modal{animation:yh-modal-out .18s ease forwards}
  .yh-modal-body{padding:1.6rem 1.6rem .4rem;text-align:center}
  .yh-modal-icon{width:58px;height:58px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:1.7rem;margin-bottom:.85rem;background:#e9f5ee;color:#2d6a4f;animation:yh-icon-pop .4s cubic-bezier(.18,.89,.32,1.28) .08s both}
  .yh-modal.danger .yh-modal-icon{background:#fdecee;color:#dc3545}
  .yh-modal-title{font-weight:700;font-size:1.18rem;color:#1a2e25;margin-bottom:.4rem}
  .yh-modal-message{color:#4a5d54;font-size:.97rem;line-height:1.45;margin-bottom:1rem;white-space:pre-wrap}
  .yh-modal-input{width:100%;padding:.6rem .8rem;border:1.5px solid #cde3d6;border-radius:10px;font-size:.97rem;margin-bottom:.5rem;outline:none;transition:border-color .15s,box-shadow .15s}
  .yh-modal-input:focus{border-color:#2d6a4f;box-shadow:0 0 0 3px rgba(45,106,79,.15)}
  .yh-modal-actions{display:flex;gap:.6rem;padding:1rem 1.6rem 1.5rem}
  .yh-modal-actions .yh-btn{flex:1;padding:.6rem 1rem;border-radius:10px;font-weight:600;font-size:.95rem;border:none;cursor:pointer;transition:transform .08s,filter .15s}
  .yh-modal-actions .yh-btn:active{transform:translateY(1px)}
  .yh-btn-cancel{background:#eef2f0;color:#3a4a42}.yh-btn-cancel:hover{filter:brightness(.96)}
  .yh-btn-confirm{background:#2d6a4f;color:#fff}.yh-btn-confirm:hover{filter:brightness(1.08)}
  .yh-modal.danger .yh-btn-confirm{background:#dc3545}
  @keyframes yh-backdrop-in{from{opacity:0}to{opacity:1}}@keyframes yh-backdrop-out{from{opacity:1}to{opacity:0}}
  @keyframes yh-modal-in{from{opacity:0;transform:translateY(18px) scale(.94)}to{opacity:1;transform:translateY(0) scale(1)}}
  @keyframes yh-modal-out{from{opacity:1;transform:scale(1)}to{opacity:0;transform:scale(.96)}}
  @keyframes yh-icon-pop{from{transform:scale(0)}to{transform:scale(1)}}
  @media (prefers-reduced-motion:reduce){.yh-toast,.yh-modal,.yh-modal-backdrop,.yh-modal-icon{animation:none!important}}
  `;
  var styleEl = document.createElement('style');
  styleEl.textContent = CSS;
  document.head.appendChild(styleEl);

  var TOAST_ICON = {
    success: 'bi-check-circle-fill',
    error: 'bi-x-circle-fill',
    warning: 'bi-exclamation-triangle-fill',
    info: 'bi-info-circle-fill',
  };

  // ---- Toast ----
  var stack = null;
  function ensureStack() {
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'yh-toast-stack';
      stack.setAttribute('role', 'region');
      stack.setAttribute('aria-label', 'Notifications');
      document.body.appendChild(stack);
    }
    return stack;
  }

  function toast(message, opts) {
    opts = opts || {};
    if (message == null || message === '') return;
    var type = opts.type || 'info';
    var duration = opts.duration == null ? 4500 : opts.duration;
    var el = document.createElement('div');
    el.className = 'yh-toast ' + type;
    el.setAttribute('role', 'alert');
    var icon = document.createElement('i');
    icon.className = 'bi ' + (TOAST_ICON[type] || TOAST_ICON.info) + ' yh-toast-icon';
    var msg = document.createElement('span');
    msg.className = 'yh-toast-msg';
    msg.textContent = String(message);
    var close = document.createElement('button');
    close.className = 'yh-toast-close';
    close.setAttribute('aria-label', 'Dismiss');
    close.innerHTML = '<i class="bi bi-x-lg"></i>';
    var remove = function () {
      el.classList.add('leaving');
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 250);
    };
    close.addEventListener('click', remove);
    el.appendChild(icon); el.appendChild(msg); el.appendChild(close);
    ensureStack().appendChild(el);
    if (duration) setTimeout(remove, duration);
  }

  // ---- Modal (confirm / prompt) ----
  function openModal(kind, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var isPrompt = kind === 'prompt';
      var danger = !!opts.danger;
      var backdrop = document.createElement('div');
      backdrop.className = 'yh-modal-backdrop';

      var icon = opts.icon || (isPrompt ? 'bi-pencil-square' : (danger ? 'bi-exclamation-triangle' : 'bi-question-circle'));
      var title = opts.title || (isPrompt ? 'Enter a value' : 'Please confirm');
      var confirmText = opts.confirmText || (isPrompt ? 'OK' : 'Confirm');
      var cancelText = opts.cancelText || 'Cancel';

      var modal = document.createElement('div');
      modal.className = 'yh-modal' + (danger ? ' danger' : '');
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');

      var body = document.createElement('div');
      body.className = 'yh-modal-body';
      body.innerHTML =
        '<div class="yh-modal-icon"><i class="bi ' + icon + '"></i></div>' +
        '<div class="yh-modal-title"></div>' +
        (opts.message ? '<div class="yh-modal-message"></div>' : '');
      body.querySelector('.yh-modal-title').textContent = title;
      if (opts.message) body.querySelector('.yh-modal-message').textContent = opts.message;

      var input = null;
      if (isPrompt) {
        input = document.createElement('input');
        input.type = opts.inputType || 'text';
        input.className = 'yh-modal-input';
        input.value = opts.defaultValue != null ? String(opts.defaultValue) : '';
        if (opts.placeholder) input.placeholder = opts.placeholder;
        body.appendChild(input);
      }

      var actions = document.createElement('div');
      actions.className = 'yh-modal-actions';
      var cancelBtn = document.createElement('button');
      cancelBtn.className = 'yh-btn yh-btn-cancel';
      cancelBtn.textContent = cancelText;
      var confirmBtn = document.createElement('button');
      confirmBtn.className = 'yh-btn yh-btn-confirm';
      confirmBtn.textContent = confirmText;
      actions.appendChild(cancelBtn); actions.appendChild(confirmBtn);

      modal.appendChild(body); modal.appendChild(actions);
      backdrop.appendChild(modal);
      document.body.appendChild(backdrop);

      if (input) { input.focus(); input.select(); }

      function done(result) {
        backdrop.classList.add('leaving');
        document.removeEventListener('keydown', onKey, true);
        setTimeout(function () {
          if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
          resolve(result);
        }, 170);
      }
      function onConfirm() { done(isPrompt ? input.value : true); }
      function onCancel() { done(isPrompt ? null : false); }
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
        else if (e.key === 'Enter') { e.preventDefault(); onConfirm(); }
      }

      confirmBtn.addEventListener('click', onConfirm);
      cancelBtn.addEventListener('click', onCancel);
      backdrop.addEventListener('mousedown', function (e) { if (e.target === backdrop) onCancel(); });
      document.addEventListener('keydown', onKey, true);
    });
  }

  window.YHDialog = {
    toast: toast,
    confirm: function (opts) {
      if (typeof opts === 'string') opts = { message: opts };
      return openModal('confirm', opts);
    },
    prompt: function (opts) {
      if (typeof opts === 'string') opts = { message: opts };
      return openModal('prompt', opts);
    },
  };

  // ---- Declarative interceptors (data-confirm / data-prompt) ----
  var SUBMIT_GUARD = '__yhDialogOk';

  function resubmit(form, submitter) {
    form[SUBMIT_GUARD] = true;
    if (form.requestSubmit) form.requestSubmit(submitter && submitter.tagName !== 'FORM' ? submitter : undefined);
    else form.submit();
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form[SUBMIT_GUARD]) { form[SUBMIT_GUARD] = false; return; }

    // Attributes may sit on the form, or on the specific submit button that
    // triggered the submit (e.submitter) — e.g. a form with both a "Preview"
    // and a "Send" button where only "Send" should confirm.
    var sm = e.submitter;
    var src = (sm && (sm.hasAttribute('data-prompt') || sm.hasAttribute('data-confirm'))) ? sm : form;

    var promptMsg = src.getAttribute('data-prompt');
    if (promptMsg != null) {
      e.preventDefault();
      var targetName = src.getAttribute('data-prompt-target');
      var optional = src.hasAttribute('data-prompt-optional');
      YHDialog.prompt({
        message: promptMsg,
        title: src.getAttribute('data-prompt-title') || 'Enter a value',
        defaultValue: src.getAttribute('data-prompt-default') || '',
      }).then(function (val) {
        if (val === null) return;            // cancelled
        if (!optional && val.trim() === '') return;
        if (targetName && form.elements[targetName]) form.elements[targetName].value = val;
        resubmit(form, sm);
      });
      return;
    }

    var confirmMsg = src.getAttribute('data-confirm');
    if (confirmMsg != null) {
      e.preventDefault();
      YHDialog.confirm({
        message: confirmMsg,
        danger: !src.hasAttribute('data-confirm-safe'),
        title: src.getAttribute('data-confirm-title') || 'Please confirm',
        confirmText: src.getAttribute('data-confirm-ok') || 'Confirm',
      }).then(function (ok) {
        if (!ok) return;
        resubmit(form, sm);
      });
    }
  }, true);

  // Links / standalone buttons that carry data-confirm (not form submits).
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-confirm]');
    if (!el || el.tagName === 'FORM') return;
    if (el.closest('form') && (el.type === 'submit' || el.tagName === 'BUTTON')) return; // handled on submit
    if (el[SUBMIT_GUARD]) { el[SUBMIT_GUARD] = false; return; }
    e.preventDefault();
    YHDialog.confirm({
      message: el.getAttribute('data-confirm'),
      danger: !el.hasAttribute('data-confirm-safe'),
      confirmText: el.getAttribute('data-confirm-ok') || 'Confirm',
    }).then(function (ok) {
      if (!ok) return;
      if (el.href) { window.location.href = el.href; }
      else { el[SUBMIT_GUARD] = true; el.click(); }
    });
  }, true);
})();
