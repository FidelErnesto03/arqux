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

  let lastHash = '';

  window.addEventListener('message', (event) => {
    const msg = event.data;
    switch (msg.type) {
      case 'update':
        applyUpdate(msg);
        break;
      case 'scrollToSection': {
        const el = document.getElementById(msg.section);
        if (el) { el.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
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
    td.textContent = '';
    const input = document.createElement('input');
    input.value = original;
    td.appendChild(input);
    input.focus();
    input.select();

    const commit = () => {
      td.classList.remove('editing');
      const value = input.value;
      td.textContent = value;
      if (value !== original) {
        emitTableEdit(tableIdx, dataRow, colIdx, value);
      }
    };
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { input.blur(); }
      if (e.key === 'Escape') { input.value = original; input.blur(); }
    });
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
