const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');
const fs = require('fs');

/** @type {cp.ChildProcess | null} */
let serverProcess = null;
/** @type {vscode.DiagnosticCollection | null} */
let diagnosticCollection = null;
/** @type {vscode.OutputChannel | null} */
let outputChannel = null;
/** @type {vscode.StatusBarItem | null} */
let statusBarItem = null;

let requestId = 1;
const pendingRequests = new Map();

function log(message, verbose = false) {
    if (!outputChannel) return;
    const config = vscode.workspace.getConfiguration('nova.lsp');
    const trace = config.get('trace', 'off');
    if (verbose && trace !== 'verbose') return;
    if (trace === 'off' && !message.startsWith('[ERROR]') && !message.startsWith('[INFO]')) return;
    outputChannel.appendLine(`[${new Date().toISOString()}] ${message}`);
}

function findExecutable(candidate) {
    if (!candidate) return null;
    if (fs.existsSync(candidate)) return candidate;
    if (process.platform === 'win32' && !candidate.endsWith('.exe')) {
        const withExe = candidate + '.exe';
        if (fs.existsSync(withExe)) return withExe;
    }
    return null;
}

function resolveLspBinary() {
    const config = vscode.workspace.getConfiguration('nova.lsp');
    const customPath = config.get('path');
    if (customPath && customPath.trim().length > 0) {
        const found = findExecutable(customPath.trim());
        if (found) return found;
    }

    if (process.env.NOVA_LSP_PATH) {
        const found = findExecutable(process.env.NOVA_LSP_PATH);
        if (found) return found;
    }

    // Check workspace folders and surrounding nova directory
    const folders = vscode.workspace.workspaceFolders || [];
    for (const folder of folders) {
        const wsPath = folder.uri.fsPath;
        const candidates = [
            path.join(wsPath, 'novalsp.exe'),
            path.join(wsPath, 'nova', 'novalsp.exe'),
            path.join(wsPath, '..', 'nova', 'novalsp.exe'),
            path.join(wsPath, 'novalsp'),
            path.join(wsPath, 'nova', 'novalsp')
        ];
        for (const candidate of candidates) {
            const found = findExecutable(candidate);
            if (found) return found;
        }
    }

    // Check relative to extension itself
    const extCandidates = [
        path.join(__dirname, '..', '..', 'novalsp.exe'),
        path.join(__dirname, '..', '..', 'novalsp')
    ];
    for (const candidate of extCandidates) {
        const found = findExecutable(candidate);
        if (found) return found;
    }

    // Default to 'novalsp' on PATH
    return process.platform === 'win32' ? 'novalsp.exe' : 'novalsp';
}

function sendLspMessage(msg) {
    if (!serverProcess || !serverProcess.stdin.writable) return;
    const body = JSON.stringify(msg);
    const byteLen = Buffer.byteLength(body, 'utf8');
    const header = `Content-Length: ${byteLen}\r\n\r\n`;
    log(`--> ${msg.method || ('response ' + msg.id)}`, true);
    serverProcess.stdin.write(header + body);
}

function sendNotification(method, params) {
    sendLspMessage({
        jsonrpc: '2.0',
        method: method,
        params: params
    });
}

function sendRequest(method, params) {
    const id = requestId++;
    return new Promise((resolve, reject) => {
        pendingRequests.set(id, { resolve, reject });
        sendLspMessage({
            jsonrpc: '2.0',
            id: id,
            method: method,
            params: params
        });
    });
}

function sendDidOpen(doc) {
    if (doc.languageId !== 'nova') return;
    sendNotification('textDocument/didOpen', {
        textDocument: {
            uri: doc.uri.toString(),
            languageId: 'nova',
            version: doc.version,
            text: doc.getText()
        }
    });
}

function sendDidChange(doc) {
    if (doc.languageId !== 'nova') return;
    sendNotification('textDocument/didChange', {
        textDocument: {
            uri: doc.uri.toString(),
            version: doc.version
        },
        contentChanges: [
            { text: doc.getText() }
        ]
    });
}

function sendDidSave(doc) {
    if (doc.languageId !== 'nova') return;
    sendNotification('textDocument/didSave', {
        textDocument: {
            uri: doc.uri.toString()
        },
        text: doc.getText()
    });
}

function sendDidClose(doc) {
    if (doc.languageId !== 'nova') return;
    sendNotification('textDocument/didClose', {
        textDocument: {
            uri: doc.uri.toString()
        }
    });
    if (diagnosticCollection) {
        diagnosticCollection.delete(doc.uri);
    }
}

function handlePublishDiagnostics(params) {
    if (!diagnosticCollection || !params || !params.uri) return;
    const uri = vscode.Uri.parse(params.uri);
    const diags = [];

    if (Array.isArray(params.diagnostics)) {
        for (const d of params.diagnostics) {
            const startLine = Math.max(0, d.range?.start?.line ?? 0);
            const startChar = Math.max(0, d.range?.start?.character ?? 0);
            const endLine = Math.max(0, d.range?.end?.line ?? startLine);
            const endChar = Math.max(startChar + 1, d.range?.end?.character ?? (startChar + 1));

            const range = new vscode.Range(startLine, startChar, endLine, endChar);
            const severity = d.severity === 2
                ? vscode.DiagnosticSeverity.Warning
                : vscode.DiagnosticSeverity.Error;

            const diag = new vscode.Diagnostic(range, d.message || 'Diagnostic', severity);
            diag.source = d.source || 'nova';
            if (d.code) diag.code = d.code;
            diags.push(diag);
        }
    }
    diagnosticCollection.set(uri, diags);
}

function handleLspMessage(msg) {
    if (msg.id !== undefined && pendingRequests.has(msg.id)) {
        const handler = pendingRequests.get(msg.id);
        pendingRequests.delete(msg.id);
        if (msg.error) {
            handler.reject(new Error(msg.error.message || 'LSP error'));
        } else {
            handler.resolve(msg.result);
        }
        return;
    }

    if (msg.method === 'textDocument/publishDiagnostics') {
        handlePublishDiagnostics(msg.params);
    }
}

function startServer(context) {
    const config = vscode.workspace.getConfiguration('nova.lsp');
    if (!config.get('enable', true)) {
        log('[INFO] Nova LSP is disabled in configuration.');
        return;
    }

    stopServer();

    const binaryPath = resolveLspBinary();
    log(`[INFO] Starting novalsp binary: ${binaryPath}`);

    let spawnDir = process.cwd();
    const ws = vscode.workspace.workspaceFolders;
    if (ws && ws.length > 0) {
        spawnDir = ws[0].uri.fsPath;
    }

    try {
        serverProcess = cp.spawn(binaryPath, ['--stdio'], {
            cwd: spawnDir,
            windowsHide: true
        });
    } catch (err) {
        log(`[ERROR] Failed to spawn novalsp: ${err.message}`);
        vscode.window.showErrorMessage(`Failed to start Nova Language Server: ${err.message}`);
        return;
    }

    if (statusBarItem) {
        statusBarItem.text = '$(sync~spin) Nova LSP: Starting';
        statusBarItem.show();
    }

    let buffer = Buffer.alloc(0);

    serverProcess.stdout.on('data', chunk => {
        buffer = Buffer.concat([buffer, chunk]);
        while (true) {
            const headerEnd = buffer.indexOf('\r\n\r\n');
            if (headerEnd === -1) break;

            const headerText = buffer.slice(0, headerEnd).toString('ascii');
            let contentLength = null;
            for (const line of headerText.split('\r\n')) {
                const match = line.match(/^Content-Length:\s*(\d+)$/i);
                if (match) {
                    contentLength = parseInt(match[1], 10);
                    break;
                }
            }

            if (contentLength === null) {
                // Invalid header, discard up to header end
                buffer = buffer.slice(headerEnd + 4);
                continue;
            }

            const totalMsgLength = headerEnd + 4 + contentLength;
            if (buffer.length < totalMsgLength) {
                // Wait for the full message payload to arrive
                break;
            }

            const bodyBuf = buffer.slice(headerEnd + 4, totalMsgLength);
            buffer = buffer.slice(totalMsgLength);

            try {
                const json = JSON.parse(bodyBuf.toString('utf8'));
                log(`<-- ${json.method || ('response ' + json.id)}`, true);
                handleLspMessage(json);
            } catch (err) {
                log(`[ERROR] Failed to parse LSP JSON: ${err.message}`);
            }
        }
    });

    serverProcess.stderr.on('data', chunk => {
        log(`[novalsp stderr] ${chunk.toString('utf8').trim()}`);
    });

    serverProcess.on('error', err => {
        log(`[ERROR] novalsp process error: ${err.message}`);
        if (statusBarItem) {
            statusBarItem.text = '$(error) Nova LSP: Error';
        }
    });

    serverProcess.on('exit', (code, signal) => {
        log(`[INFO] novalsp exited with code ${code}, signal ${signal}`);
        serverProcess = null;
        if (statusBarItem) {
            statusBarItem.text = '$(circle-slash) Nova LSP: Stopped';
        }
    });

    // Send LSP initialization handshake
    sendRequest('initialize', {
        processId: process.pid,
        rootUri: ws && ws.length > 0 ? ws[0].uri.toString() : null,
        capabilities: {
            textDocument: {
                synchronization: {
                    openClose: true,
                    change: 1, // Full document sync
                    save: { includeText: true }
                },
                publishDiagnostics: {
                    relatedInformation: false
                }
            }
        }
    }).then(result => {
        log(`[INFO] Initialized novalsp: ${JSON.stringify(result)}`);
        sendNotification('initialized', {});
        if (statusBarItem) {
            statusBarItem.text = '$(check) Nova LSP: Ready';
        }

        // Send open notifications for already opened documents
        for (const doc of vscode.workspace.textDocuments) {
            if (doc.languageId === 'nova') {
                sendDidOpen(doc);
            }
        }
    }).catch(err => {
        log(`[ERROR] initialize handshake failed: ${err.message}`);
    });
}

function stopServer() {
    if (!serverProcess) return;
    try {
        sendRequest('shutdown', null)
            .then(() => sendNotification('exit', null))
            .catch(() => {})
            .finally(() => {
                if (serverProcess) {
                    serverProcess.kill();
                    serverProcess = null;
                }
            });
    } catch (e) {
        if (serverProcess) {
            serverProcess.kill();
            serverProcess = null;
        }
    }
}

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    outputChannel = vscode.window.createOutputChannel('Nova Language Server');
    diagnosticCollection = vscode.languages.createDiagnosticCollection('nova');
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);

    context.subscriptions.push(outputChannel);
    context.subscriptions.push(diagnosticCollection);
    context.subscriptions.push(statusBarItem);

    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand('nova.restartServer', () => {
        log('[INFO] Manual restart requested.');
        startServer(context);
    }));

    // Register document sync events
    context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(doc => sendDidOpen(doc)));
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument(event => sendDidChange(event.document)));
    context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(doc => sendDidSave(doc)));
    context.subscriptions.push(vscode.workspace.onDidCloseTextDocument(doc => sendDidClose(doc)));

    // Re-check when configurations change
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('nova.lsp')) {
            startServer(context);
        }
    }));

    startServer(context);
}

function deactivate() {
    stopServer();
    if (diagnosticCollection) {
        diagnosticCollection.clear();
        diagnosticCollection.dispose();
    }
}

module.exports = {
    activate,
    deactivate
};

