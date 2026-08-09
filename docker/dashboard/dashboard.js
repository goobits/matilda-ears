class MatildaDashboard {
    constructor() {
        this.apiBaseUrl = window.location.origin;
        this.adminToken = this.loadAdminToken();
        this.websocketUrl = null;
        this.currentQRCode = null;
        this.mediaRecorder = null;
        this.recordingChunks = [];
        this.init();
    }

    loadAdminToken() {
        const fragment = new URLSearchParams(window.location.hash.slice(1));
        const fragmentToken = fragment.get('token');
        if (fragmentToken) {
            sessionStorage.setItem('matilda_admin_token', fragmentToken);
            window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
            return fragmentToken;
        }
        return sessionStorage.getItem('matilda_admin_token');
    }

    async apiFetch(path, options = {}) {
        if (!this.adminToken) {
            throw new Error('Dashboard token required. Open this page with #token=YOUR_MATILDA_API_TOKEN.');
        }

        const headers = new Headers(options.headers || {});
        headers.set('Authorization', `Bearer ${this.adminToken}`);
        const response = await fetch(`${this.apiBaseUrl}${path}`, { ...options, headers });
        if (response.ok) {
            return response;
        }

        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `Request failed with status ${response.status}`);
    }

    async init() {
        this.bindEvents();
        await this.loadServerStatus();
        await this.loadActiveClients();
        this.startStatusPolling();
        this.startClientPolling();
    }

    bindEvents() {
        document.getElementById('generateQR').addEventListener('click', () => this.generateQRCode());
        document.getElementById('downloadQR').addEventListener('click', () => this.downloadQRCode());
        document.getElementById('refreshClients').addEventListener('click', () => this.loadActiveClients());
        document.getElementById('recordTest').addEventListener('click', () => this.toggleRecording());
        document.getElementById('uploadBtn').addEventListener('click', () => document.getElementById('uploadFile').click());
        document.getElementById('uploadFile').addEventListener('change', (event) => this.handleFileUpload(event));
    }

    async loadServerStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/status`);
            if (!response.ok) {
                throw new Error(`Status request failed with ${response.status}`);
            }
            const status = await response.json();
            const scheme = status.websocket_secure ? 'wss' : 'ws';
            this.websocketUrl = `${scheme}://${window.location.hostname}:${status.websocket_port}`;
            this.updateServerStatus(status);
        } catch (error) {
            console.error('Failed to load server status:', error);
            this.updateServerStatus({
                status: 'error',
                error: 'Connection failed',
                gpu_available: false,
                model: 'unknown',
                clients: 0,
                uptime: 0
            });
        }
    }

    updateServerStatus(status) {
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const serverStatusText = document.getElementById('serverStatusText');

        if (status.status === 'running') {
            statusIndicator.textContent = '✅';
            statusText.textContent = 'Running';
            statusText.className = 'status-running';
            serverStatusText.textContent = '✅ Running';
            serverStatusText.className = 'status-running';
        } else if (status.status === 'error') {
            statusIndicator.textContent = '❌';
            statusText.textContent = 'Error';
            statusText.className = 'status-error';
            serverStatusText.textContent = `❌ ${status.error || 'Unknown error'}`;
            serverStatusText.className = 'status-error';
        } else {
            statusIndicator.textContent = '⚠️';
            statusText.textContent = 'Starting...';
            statusText.className = 'status-warning';
            serverStatusText.textContent = '⚠️ Loading model...';
            serverStatusText.className = 'status-warning';
        }

        document.getElementById('whisperModel').textContent = status.model || '-';
        document.getElementById('gpuStatus').textContent = status.gpu_available ? '✅ Enabled' : '❌ CPU Only';
        document.getElementById('clientCount').textContent = status.clients || 0;
        document.getElementById('uptime').textContent = this.formatUptime(status.uptime || 0);
    }

    formatUptime(seconds) {
        const wholeSeconds = Math.floor(seconds);
        if (wholeSeconds < 60) return `${wholeSeconds}s`;
        if (wholeSeconds < 3600) return `${Math.floor(wholeSeconds / 60)}m`;
        if (wholeSeconds < 86400) {
            return `${Math.floor(wholeSeconds / 3600)}h ${Math.floor((wholeSeconds % 3600) / 60)}m`;
        }
        return `${Math.floor(wholeSeconds / 86400)}d ${Math.floor((wholeSeconds % 86400) / 3600)}h`;
    }

    async generateQRCode() {
        const clientName = document.getElementById('clientName').value.trim();
        const expirationDays = Number.parseInt(document.getElementById('expirationDays').value, 10);
        const oneTimeUse = document.getElementById('oneTimeUse').checked;
        if (!clientName || !this.websocketUrl) {
            alert(clientName ? 'WebSocket server is not ready yet' : 'Please enter a client name');
            return;
        }

        try {
            const response = await this.apiFetch('/api/generate-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    client_name: clientName,
                    expiration_days: expirationDays,
                    one_time_use: oneTimeUse
                })
            });
            const tokenData = await response.json();
            const serverUrl = `${this.websocketUrl}?api_token=${encodeURIComponent(tokenData.token)}`;
            const secure = this.websocketUrl.startsWith('wss://');
            const qrData = {
                server_url: serverUrl,
                token: tokenData.token,
                name: `${window.location.hostname} Matilda Ears`,
                expires: tokenData.expires,
                encryption_enabled: secure,
                client_name: clientName
            };

            const qrCodeDiv = document.getElementById('qrCode');
            qrCodeDiv.innerHTML = '';
            this.currentQRCode = new QRCode(qrCodeDiv, {
                text: JSON.stringify(qrData),
                width: 200,
                height: 200,
                colorDark: '#000000',
                colorLight: '#ffffff',
                correctLevel: QRCode.CorrectLevel.M
            });

            document.getElementById('qrClientName').textContent = clientName;
            document.getElementById('qrExpiration').textContent = new Date(tokenData.expires).toLocaleDateString();
            document.getElementById('qrSecurity').textContent = secure ? 'TLS encrypted' : 'Local network only';
            document.getElementById('qrDisplay').style.display = 'block';
            document.getElementById('clientName').value = '';
            document.getElementById('oneTimeUse').checked = false;
            await this.loadActiveClients();
        } catch (error) {
            console.error('Failed to generate QR code:', error);
            alert(error.message);
        }
    }

    downloadQRCode() {
        const canvas = document.querySelector('#qrCode canvas');
        if (!this.currentQRCode || !canvas) {
            alert('No QR code to download');
            return;
        }

        const link = document.createElement('a');
        link.download = `matilda-qr-${document.getElementById('qrClientName').textContent}.png`;
        link.href = canvas.toDataURL();
        link.click();
    }

    async loadActiveClients() {
        try {
            const response = await this.apiFetch('/api/clients');
            this.updateClientsList(await response.json());
        } catch (error) {
            console.error('Failed to load clients:', error);
            document.getElementById('clientList').innerHTML =
                `<div class="loading">${this.escapeHtml(error.message)}</div>`;
        }
    }

    updateClientsList(clients) {
        const clientList = document.getElementById('clientList');
        if (!clients || clients.length === 0) {
            clientList.innerHTML = '<div class="loading">No client tokens</div>';
            return;
        }

        clientList.innerHTML = clients.map((client) => {
            const typeIcon = client.one_time_use ? '⚠️' : '🔄';
            const typeText = client.one_time_use ? 'One-time' : 'Reusable';
            const usedText = client.one_time_use && client.used ? ' (USED)' : '';
            const statusIcon = client.active ? '🟢' : '⚪';
            const name = this.escapeHtml(client.name);
            const expires = new Date(client.expires).toLocaleDateString();
            const lastSeen = client.last_seen ? new Date(client.last_seen).toLocaleString() : 'Never';
            return `
                <div class="client-item fade-in">
                    <div>
                        <div class="client-name">${statusIcon} ${name}${usedText}</div>
                        <div class="client-info">
                            ${typeIcon} ${typeText} |
                            Expires: ${expires} |
                            Last seen: ${lastSeen}
                        </div>
                    </div>
                    <div class="client-actions">
                        <button class="btn-danger" onclick="dashboard.revokeClient('${client.token_id}')">Revoke</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    async revokeClient(tokenId) {
        if (!window.confirm('Are you sure you want to revoke this client token?')) {
            return;
        }
        try {
            await this.apiFetch('/api/revoke-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token_id: tokenId })
            });
            await this.loadActiveClients();
        } catch (error) {
            console.error('Failed to revoke token:', error);
            alert(error.message);
        }
    }

    async toggleRecording() {
        const recordButton = document.getElementById('recordTest');
        if (this.mediaRecorder?.state === 'recording') {
            this.mediaRecorder.stop();
            recordButton.textContent = '🎙️ Record Test';
            recordButton.disabled = true;
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const options = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? { mimeType: 'audio/webm;codecs=opus' }
                : {};
            this.mediaRecorder = new MediaRecorder(stream, options);
            this.recordingChunks = [];
            this.mediaRecorder.ondataavailable = (event) => this.recordingChunks.push(event.data);
            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.recordingChunks, { type: this.mediaRecorder.mimeType });
                await this.processTestAudio(audioBlob, 'dashboard-recording.webm');
                recordButton.disabled = false;
                stream.getTracks().forEach((track) => track.stop());
            };
            this.mediaRecorder.start();
            recordButton.textContent = '⏹️ Stop Recording';
        } catch (error) {
            console.error('Failed to start recording:', error);
            alert('Failed to access microphone');
        }
    }

    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (file) {
            await this.processTestAudio(file, file.name);
        }
    }

    async processTestAudio(audioData, filename) {
        const testResult = document.getElementById('testResult');
        const transcriptionText = document.getElementById('transcriptionText');
        const confidence = document.getElementById('confidence');
        const processingTime = document.getElementById('processingTime');
        testResult.style.display = 'block';
        transcriptionText.textContent = 'Processing...';
        confidence.textContent = '-';
        processingTime.textContent = '-';

        try {
            const formData = new FormData();
            formData.append('audio', audioData, filename);
            const response = await this.apiFetch('/api/transcribe', { method: 'POST', body: formData });
            const result = await response.json();
            transcriptionText.textContent = `"${result.text}"`;
            confidence.textContent = `${Math.round(result.confidence * 100)}%`;
            processingTime.textContent = `${result.processing_time.toFixed(1)}s`;
        } catch (error) {
            console.error('Transcription test failed:', error);
            transcriptionText.textContent = `Error: ${error.message}`;
        }
    }

    escapeHtml(value) {
        const element = document.createElement('div');
        element.textContent = String(value);
        return element.innerHTML;
    }

    startStatusPolling() {
        window.setInterval(() => this.loadServerStatus(), 30000);
    }

    startClientPolling() {
        window.setInterval(() => this.loadActiveClients(), 15000);
    }
}

let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new MatildaDashboard();
    window.dashboard = dashboard;
});
