/**
 * previewPanel.ts — WebviewPanel manager for the HCORTEX preview.
 *
 * Owns the panel lifecycle, strict-CSP HTML shell (SEC-02), the
 * postMessage bridge, and edit-message routing back to the extension.
 */
import * as vscode from 'vscode';
import { BadgeState, buildHtmlShell, generateNonce } from './webviewKit';

export interface RenderPayload {
  bodyHtml: string;
  hcortex: string;
  badges: BadgeState;
}

export interface PreviewCallbacks {
  onCopyHash(hash: string): void;
  onRevealSection(sectionId: string): void;
  onApplyHcortexEdit(newHcortex: string): void;
}

export class PreviewPanel {
  private static current: PreviewPanel | undefined;
  private readonly panel: vscode.WebviewPanel;
  private readonly disposables: vscode.Disposable[] = [];
  private lastPayload: RenderPayload | null = null;

  static createOrShow(
    extensionUri: vscode.Uri,
    document: vscode.TextDocument,
    column: vscode.ViewColumn,
    callbacks: PreviewCallbacks
  ): PreviewPanel {
    if (PreviewPanel.current) {
      PreviewPanel.current.panel.reveal(column);
      return PreviewPanel.current;
    }
    const panel = vscode.window.createWebviewPanel(
      'cortexHcortexPreview',
      `HCORTEX: ${basename(document.fileName)}`,
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')],
      }
    );
    PreviewPanel.current = new PreviewPanel(panel, extensionUri, callbacks);
    return PreviewPanel.current;
  }

  static get instance(): PreviewPanel | undefined {
    return PreviewPanel.current;
  }

  private constructor(
    panel: vscode.WebviewPanel,
    extensionUri: vscode.Uri,
    callbacks: PreviewCallbacks
  ) {
    this.panel = panel;

    const nonce = generateNonce();
    const webview = panel.webview;
    this.panel.webview.html = buildHtmlShell({
      nonce,
      cspSource: webview.cspSource,
      cssUri: webview.asWebviewUri(
        vscode.Uri.joinPath(extensionUri, 'media', 'preview.css')
      ).toString(),
      jsUri: webview.asWebviewUri(
        vscode.Uri.joinPath(extensionUri, 'media', 'preview.js')
      ).toString(),
    });

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    this.panel.webview.onDidReceiveMessage(
      (msg) => {
        switch (msg?.type) {
          case 'copyHash':
            callbacks.onCopyHash(String(msg.hash ?? ''));
            break;
          case 'revealSection':
            callbacks.onRevealSection(String(msg.section ?? ''));
            break;
          case 'applyHcortexEdit':
            callbacks.onApplyHcortexEdit(String(msg.hcortex ?? ''));
            break;
          case 'ready':
            if (this.lastPayload) { this.postUpdate(this.lastPayload); }
            break;
        }
      },
      null,
      this.disposables
    );
  }

  /** Push a fresh render into the webview (badges + body + source copy). */
  update(payload: RenderPayload): void {
    this.lastPayload = payload;
    this.postUpdate(payload);
  }

  private postUpdate(payload: RenderPayload): void {
    void this.panel.webview.postMessage({
      type: 'update',
      bodyHtml: payload.bodyHtml,
      hcortex: payload.hcortex,
      badges: payload.badges,
    });
  }

  /** Track the document the preview is currently showing. */
  setDocumentTitle(fileName: string): void {
    this.panel.title = `HCORTEX: ${basename(fileName)}`;
  }

  /** UI-03: ask the webview to scroll to a `§N` section anchor. */
  scrollToSection(sectionId: string): void {
    void this.panel.webview.postMessage({
      type: 'scrollToSection',
      section: `sec-${sectionId}`,
    });
  }

  /** Cursor-follow: highlight the §N chapter + sigil card under cursor. */
  setActive(sectionId: string, sigil: string): void {
    void this.panel.webview.postMessage({
      type: 'active',
      sec: sectionId,
      sigil,
    });
  }

  /** Report the outcome of a bidirectional edit back to the preview. */
  reportEditResult(ok: boolean, detail: string): void {
    void this.panel.webview.postMessage({ type: 'editResult', ok, detail });
  }

  dispose(): void {
    PreviewPanel.current = undefined;
    this.panel.dispose();
    for (const d of this.disposables) { d.dispose(); }
  }
}

function basename(p: string): string {
  return p.split(/[\\/]/).pop() ?? p;
}
