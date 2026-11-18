/* preview.js — client-side webview logic (loaded with CSP nonce).
   - receives rendered HCORTEX body + badges via postMessage
   - scroll sync: scrollToSection (ext→view), header click (view→ext)
   - copy full SHA-256 to clipboard via extension
   - inline table edit emitter: edits a data cell, rebuilds the HCORTEX
     source line and emits applyHcortexEdit for the SEC-06 gate */
(function () {
  const vscode = acquireVsCodeApi();
  let hcortexSource = '';

  const bodyEl = document.getElementById('hc-body');
  const badgeState = document.getElementById('badge-state');
  const badgeCanon = document.getElementById('badge-canon');
  const badgeHash = document.getElementById('badge-hash');
  const hashShort = document.getElementById('hash-short');
  const copyBtn = document.getElementById('copy-hash');
  const badgeLoss = document.getElementById('badge-loss');
  const badgeRuntime = document.getElementById('badge-runtime');
  const editResult = document.getElementById('edit-result');
  const filterEl = document.getElementById('hc-filter');
  const gotoEl = document.getElementById('hc-goto');

  let lastHash = '';

  window.addEventListener('message', (event) => {
    const msg = event.data;
    switch (msg.type) {
      case 'update':
        applyUpdate(msg);
        break;
      case 'scrollToSection': {
        revealElement(document.getElementById(msg.section));
        break;
      }
      case 'active': {
        markActive(msg.sec, msg.sigil);
        break;
      }
      case 'editResult': {
        editResult.hidden = false;
        editResult.textContent = msg.detail;
        editResult.className = msg.ok ? 'ok' : 'err';
        break;
      }
    }
  });

  /** Open every ancestor <details> then scroll the element into view. */
  function revealElement(el) {
    if (!el) { return; }
    let node = el.parentElement;
    while (node) {
      if (node.tagName === 'DETAILS') { node.open = true; }
      node = node.parentElement;
    }
    el.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  /** Cursor-follow highlight: card of the sigil under cursor + its §N. */
  function markActive(sec, sigil) {
    bodyEl.querySelectorAll('.active').forEach((e) => e.classList.remove('active'));
    if (sigil) {
      const card = bodyEl.querySelector(
        '.hc-card[data-sigil="' + String(sigil).replace(/"/g, '') + '"]');
      if (card) {
        card.classList.add('active');
        let node = card.parentElement;
        while (node) {
          if (node.tagName === 'DETAILS') { node.open = true; }
          node = node.parentElement;
        }
      }
    }
    if (sec) {
      const h = document.getElementById('sec-' + sec);
      if (h) { h.classList.add('active'); }
    }
  }

  function applyUpdate(msg) {
    const b = msg.badges || {};
    hcortexSource = msg.hcortex || '';
    bodyEl.innerHTML = msg.bodyHtml || '';

    badgeState.textContent = 'Estado: ' + (b.valid ? 'VALID' : 'INVALID');
    badgeState.className = 'badge ' + (b.valid ? 'valid' : 'invalid');

    badgeCanon.textContent = 'Canon: ' + (b.canon || 'C14N-1.0');

    lastHash = b.hashFull || '';
    hashShort.textContent = b.hashShort || '—';
    badgeHash.title = lastHash ? 'sha256:' + lastHash : 'SHA-256 canónico';

    const n = b.lossCount;
    badgeLoss.textContent = 'Loss-Report: ' +
      (n === -1 || n === undefined ? '—' : n + ' pérdida(s)');
    badgeLoss.className = 'badge ' + (n > 0 ? 'loss-warn' : 'loss-ok');

    badgeRuntime.textContent = 'Runtime: ' + (b.runtime || '—');

    wireInteractions();
    populateGoto();
    applyFilter(filterEl.value);
  }

  /** Rebuild the §N jump dropdown from the rendered chapter anchors. */
  function populateGoto() {
    const prev = gotoEl.value;
    gotoEl.innerHTML = '<option value="">§ Ir a…</option>';
    bodyEl.querySelectorAll('.hc-sec[data-sec]').forEach((h) => {
      const opt = document.createElement('option');
      opt.value = h.dataset.sec;
      opt.textContent = '§' + h.dataset.sec + ' ' +
        h.textContent.replace(/^§\d+(?:\.\d+)?\s*[:·]?\s*/, '');
      gotoEl.appendChild(opt);
    });
    if ([...gotoEl.options].some((o) => o.value === prev)) {
      gotoEl.value = prev;
    }
  }

  gotoEl.addEventListener('change', () => {
    if (!gotoEl.value) { return; }
    revealElement(document.getElementById('sec-' + gotoEl.value));
    gotoEl.value = '';
  });

  filterEl.addEventListener('input', () => applyFilter(filterEl.value));

  /** Show only cards/chips/glossary rows matching the query. */
  function applyFilter(q) {
    const needle = String(q || '').trim().toLowerCase();
    const match = (el) => !needle ||
      el.textContent.toLowerCase().includes(needle);
    bodyEl.querySelectorAll('.hc-card, .g-chip').forEach((el) => {
      el.hidden = !match(el);
    });
    bodyEl.querySelectorAll('.g-sigils tbody tr').forEach((tr) => {
      tr.hidden = !match(tr);
    });
  }

  copyBtn.addEventListener('click', () => {
    if (lastHash) {
      vscode.postMessage({ type: 'copyHash', hash: lastHash });
    }
  });

  function wireInteractions() {
    // view → ext scroll sync: click a §N header to reveal the editor line.
    bodyEl.querySelectorAll('.hc-sec').forEach((h) => {
      h.addEventListener('click', () => {
        vscode.postMessage({ type: 'revealSection', section: h.dataset.sec });
      });
    });

    // inline table edit emitter — double-click a data cell to edit.
    // Schema tables only: the glossary panel (.g-sigils) is read-only.
    bodyEl.querySelectorAll('table:not(.g-sigils)').forEach((table, tableIdx) => {
      const rows = table.querySelectorAll('tr');
      // rows[0] is the header row; data rows follow.
      rows.forEach((tr, rowIdx) => {
        if (rowIdx === 0) { return; }
        const dataRow = rowIdx - 1;
        tr.querySelectorAll('td').forEach((td, colIdx) => {
          td.addEventListener('dblclick', () => {
            beginCellEdit(td, tableIdx, dataRow, colIdx);
          });
        });
      });
    });
  }

  function beginCellEdit(td, tableIdx, dataRow, colIdx) {
    if (td.classList.contains('editing')) { return; }
    const original = td.textContent;
    td.classList.add('editing');
    // Hide the cell text without collapsing the row: transparent color
    // keeps the text's box model so the table layout never shifts.
    td.style.color = 'transparent';
    // Textarea (not input): cortex values run to hundreds of chars — a
    // single-line box truncates them unreadably. The editor is a FIXED
    // OVERLAY on document.body, not a cell child: an in-flow editor widens
    // its column and pushes the whole table past the card boundary.
    // It FOLLOWS the cell on scroll so the edit anchor never detaches.
    const reposition = () => {
      const r = td.getBoundingClientRect();
      area.style.left = r.left + 'px';
      area.style.top = r.top + 'px';
    };
    const area = document.createElement('textarea');
    area.value = original;
    area.wrap = 'soft';
    area.spellcheck = false;
    area.setAttribute('aria-label', 'cell editor');

    const card = td.closest('.hc-card');
    const avail = card
      ? card.clientWidth - 36 // borders + padding
      : document.documentElement.clientWidth - 48;
    const maxW = Math.max(160, Math.min(1400, avail));

    const autoSize = () => {
      const wantW = Math.min(maxW, Math.max(160, area.value.length * 7 + 48));
      area.style.width = wantW + 'px';
      area.style.height = 'auto';
      area.style.height = area.scrollHeight + 'px';
    };

    area.style.position = 'fixed';
    area.style.zIndex = '100';
    area.style.boxSizing = 'border-box';
    area.style.padding = '4px 10px';
    area.style.font = 'inherit';
    area.style.fontFamily = 'var(--vscode-editor-font-family, monospace)';
    area.style.color = 'var(--vscode-foreground)';
    area.style.background = 'var(--vscode-input-background)';
    area.style.border = '2px solid var(--vscode-focusBorder)';
    area.style.borderRadius = '4px';
    area.style.resize = 'none';
    area.style.overflow = 'hidden';
    area.style.whiteSpace = 'pre-wrap';
    area.style.overflowWrap = 'break-word';
    area.style.lineHeight = '1.4';
    area.style.boxShadow = '0 4px 16px rgba(0,0,0,0.35)';
    document.body.appendChild(area);

    reposition();
    autoSize();
    // Follow the cell through scroll/resize — capture phase catches
    // scrolls on any inner container, not just window.
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    area.addEventListener('input', autoSize);
    area.focus();
    area.setSelectionRange(area.value.length, area.value.length);

    let done = false;
    const finish = (commitEdit) => {
      if (done) { return; }
      done = true;
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
      td.classList.remove('editing');
      td.style.color = '';
      area.remove();
      const raw = area.value;
      if (commitEdit) {
        const value = raw;
        td.textContent = value;
        if (value !== original) {
          emitTableEdit(tableIdx, dataRow, colIdx, sanitizeCellValue(value));
        }
      } else {
        td.textContent = original;
      }
    };
    area.addEventListener('blur', () => finish(true));
    area.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); finish(false); }
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); finish(true); }
    });
  }

  /**
   * Markdown table cells are single-line `|`-delimited. A pasted/typed
   * newline or pipe would corrupt the row structure — escape both so the
   * rebuilt HCORTEX stays parseable (the extension validates downstream).
   */
  function sanitizeCellValue(v) {
    return v.replace(/\|/g, '\\|').replace(/\r?\n/g, '\\n');
  }

  /**
   * Rebuild the HCORTEX source: locate the `tableIdx`-th markdown table,
   * rewrite cell `colIdx` of data row `dataRow`, then emit the whole
   * updated source so the extension can run from-hcortex + validate +
   * loss-report before touching the editor buffer (SEC-06).
   */
  function emitTableEdit(tableIdx, dataRow, colIdx, newValue) {
    const lines = hcortexSource.split('\n');
    let table = -1;
    let row = -1;
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (!/^\s*\|/.test(l)) { row = -1; continue; }
      if (/^\s*\|[\s:|-]+\|\s*$/.test(l)) { continue; } // separator
      if (row === -1) { table++; row = 0; continue; } // header row
      if (table === tableIdx && row === dataRow) {
        const cells = l.split('|');
        // cells[0] and cells[cells.length-1] are the outer margins.
        const inner = cells.slice(1, -1);
        if (colIdx < inner.length) {
          inner[colIdx] = ' ' + newValue.trim() + ' ';
          lines[i] = '|' + inner.join('|') + '|';
          vscode.postMessage({
            type: 'applyHcortexEdit',
            hcortex: lines.join('\n'),
          });
        }
        return;
      }
      row++;
    }
  }

  vscode.postMessage({ type: 'ready' });
})();
