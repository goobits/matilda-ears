class STTDashboard {
    constructor() {
        this.apiBaseUrl = window.location.origin;
        this.websocketUrl = `ws://${window.location.hostname}:8769`;
        this.currentQRCode = null;
        this.mediaRecorder = null;
        this.recordingChunks = [];
        
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadServerStatus();
        await this.loadActiveClients();
        this.startStatusPolling();
    }

    bindEvents() {
        // QR Code generation
        document.getElementById('generateQR').addEventListener('click', () => this.generateQRCode());
        document.getElementById('downloadQR').addEventListener('click', () => this.downloadQRCode());
        
        // Client management
        document.getElementById('refreshClients').addEventListener('click', () => this.loadActiveClients());
        
        // Test transcription
        document.getElementById('recordTest').addEventListener('click', () => this.toggleRecording());
        document.getElementById('uploadBtn').addEventListener('click', () => document.getElementById('uploadFile').click());
        document.getElementById('uploadFile').addEventListener('change', (e) => this.handleFileUpload(e));
        
        // Settings
        document.getElementById('saveSettings').addEventListener('click', () => this.saveSettings());
    }

    async loadServerStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/status`);
            const status = await response.json();
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
        const whisperModel = document.getElementById('whisperModel');
        const gpuStatus = document.getElementById('gpuStatus');
        const clientCount = document.getElementById('clientCount');
        const uptime = document.getElementById('uptime');

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
            serverStatusText.textContent = '⚠️ Starting...';
            serverStatusText.className = 'status-warning';
        }

        whisperModel.textContent = status.model || '-';
        gpuStatus.textContent = status.gpu_available ? '✅ Enabled' : '❌ CPU Only';
        clientCount.textContent = status.clients || 0;
        uptime.textContent = this.formatUptime(status.uptime || 0);
    }

    formatUptime(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
        return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
    }

    async generateQRCode() {
        const clientName = document.getElementById('clientName').value.trim();
        const expirationDays = parseInt(document.getElementById('expirationDays').value);
        const oneTimeUse = document.getElementById('oneTimeUse').checked;

        if (!clientName) {
            alert('Please enter a client name');
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/api/generate-token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    client_name: clientName,
                    expiration_days: expirationDays,
                    one_time_use: oneTimeUse
                })
            });

            const tokenData = await response.json();
            if (!response.ok) {
                throw new Error(tokenData.error || 'Failed to generate token');
            }

            // Create QR code data
            const qrData = {
                server_url: `wss://${window.location.hostname}:8769/ws`,
                token: tokenData.token,
                name: `${window.location.hostname} STT Server`,
                expires: tokenData.expires,
                encryption_enabled: true,
                client_name: clientName
            };

            // Generate QR code
            const qrCodeDiv = document.getElementById('qrCode');
            qrCodeDiv.innerHTML = '';
            
            const qr = new QRCode(qrCodeDiv, {
                text: JSON.stringify(qrData),
                width: 200,
                height: 200,
                colorDark: '#000000',
                colorLight: '#ffffff',
                correctLevel: QRCode.CorrectLevel.M
            });

            this.currentQRCode = qr;

            // Update QR display info
            document.getElementById('qrClientName').textContent = clientName;
            document.getElementById('qrExpiration').textContent = new Date(tokenData.expires).toLocaleDateString();
            
            // Update one-time use indicator
            const encryptionInfo = document.querySelector('#qrDisplay .qr-info p:nth-child(3)');
            if (encryptionInfo) {
                if (tokenData.one_time_use) {
                    encryptionInfo.innerHTML = '<strong>Type:</strong> ⚠️ One-time use • <strong>Encryption:</strong> ✅ End-to-end enabled';
                } else {
                    encryptionInfo.innerHTML = '<strong>Type:</strong> 🔄 Reusable • <strong>Encryption:</strong> ✅ End-to-end enabled';
                }
            }
            
            document.getElementById('qrDisplay').style.display = 'block';

            // Clear form
            document.getElementById('clientName').value = '';
            document.getElementById('oneTimeUse').checked = false;

        } catch (error) {
            console.error('Failed to generate QR code:', error);
            alert(`Failed to generate QR code: ${error.message}`);
        }
    }

    downloadQRCode() {
        if (!this.currentQRCode) {
            alert('No QR code to download');
            return;
        }

        const canvas = document.querySelector('#qrCode canvas');
        if (canvas) {
            const link = document.createElement('a');
            link.download = `stt-qr-${document.getElementById('qrClientName').textContent}.png`;
            link.href = canvas.toDataURL();
            link.click();
        }
    }

    async loadActiveClients() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/clients`);
            const clients = await response.json();
            this.updateClientsList(clients);
        } catch (error) {
            console.error('Failed to load clients:', error);
            document.getElementById('clientList').innerHTML = '<div class="loading">Failed to load clients</div>';
        }
    }

    updateClientsList(clients) {
        const clientList = document.getElementById('clientList');
        
        if (!clients || clients.length === 0) {
            clientList.innerHTML = '<div class="loading">No active clients</div>';
            return;
        }

        clientList.innerHTML = clients.map(client => {
            const typeIcon = client.one_time_use ? '⚠️' : '🔄';
            const typeText = client.one_time_use ? 'One-time' : 'Reusable';
            const usedText = client.one_time_use && client.used ? ' (USED)' : '';
            const statusIcon = client.active ? '🟢' : '⚪';
            
            return `
                <div class="client-item fade-in">
                    <div>
                        <div class="client-name">${statusIcon} ${client.name}${usedText}</div>
                        <div class="client-info">
                            ${typeIcon} ${typeText} | 
                            Expires: ${new Date(client.expires).toLocaleDateString()} | 
                            Last seen: ${client.last_seen ? new Date(client.last_seen).toLocaleString() : 'Never'}
                        </div>
                    </div>
                    <div class="client-actions">
                        <button class="btn-danger" onclick="dashboard.revokeClient('${client.token_id}')">
                            Revoke
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    async revokeClient(tokenId) {
        if (!confirm('Are you sure you want to revoke this client token?')) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/api/revoke-token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ token_id: tokenId })
            });

            if (response.ok) {
                await this.loadActiveClients();
            } else {
                const error = await response.json();
                alert(`Failed to revoke token: ${error.error}`);
            }
        } catch (error) {
            console.error('Failed to revoke token:', error);
            alert('Failed to revoke token');
        }
    }

    async toggleRecording() {
        const recordBtn = document.getElementById('recordTest');
        
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            // Stop recording
            this.mediaRecorder.stop();
            recordBtn.textContent = '🎙️ Record Test';
            recordBtn.disabled = true;
        } else {
            // Start recording
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.mediaRecorder = new MediaRecorder(stream);
                this.recordingChunks = [];

                this.mediaRecorder.ondataavailable = (event) => {
                    this.recordingChunks.push(event.data);
                };

                this.mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(this.recordingChunks, { type: 'audio/wav' });
                    this.processTestAudio(audioBlob);
                    recordBtn.disabled = false;
                    
                    // Stop all tracks
                    stream.getTracks().forEach(track => track.stop());
                };

                this.mediaRecorder.start();
                recordBtn.textContent = '⏹️ Stop Recording';
                
            } catch (error) {
                console.error('Failed to start recording:', error);
                alert('Failed to access microphone');
            }
        }
    }

    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (file) {
            await this.processTestAudio(file);
        }
    }

    async processTestAudio(audioData) {
        const testResult = document.getElementById('testResult');
        const transcriptionText = document.getElementById('transcriptionText');
        const confidence = document.getElementById('confidence');
        const processingTime = document.getElementById('processingTime');

        // Show loading state
        testResult.style.display = 'block';
        transcriptionText.textContent = 'Processing...';
        confidence.textContent = '-';
        processingTime.textContent = '-';

        try {
            const formData = new FormData();
            formData.append('audio', audioData);

            const startTime = Date.now();
            const response = await fetch(`${this.apiBaseUrl}/api/transcribe`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            const processingTimeMs = Date.now() - startTime;

            if (response.ok) {
                transcriptionText.textContent = `"${result.text}"`;
                confidence.textContent = `${Math.round(result.confidence * 100)}%`;
                processingTime.textContent = `${(processingTimeMs / 1000).toFixed(1)}s`;
            } else {
                throw new Error(result.error || 'Transcription failed');
            }

        } catch (error) {
            console.error('Transcription test failed:', error);
            transcriptionText.textContent = `Error: ${error.message}`;
            confidence.textContent = '-';
            processingTime.textContent = '-';
        }
    }

    async saveSettings() {
        const settings = {
            max_clients: parseInt(document.getElementById('maxClients').value),
            default_expiration: parseInt(document.getElementById('defaultExpiration').value),
            whisper_model: document.getElementById('whisperModelSelect').value
        };

        try {
            const response = await fetch(`${this.apiBaseUrl}/api/settings`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settings)
            });

            if (response.ok) {
                alert('Settings saved successfully!');
                await this.loadServerStatus();
            } else {
                const error = await response.json();
                alert(`Failed to save settings: ${error.error}`);
            }
        } catch (error) {
            console.error('Failed to save settings:', error);
            alert('Failed to save settings');
        }
    }

    startStatusPolling() {
        // Poll server status every 30 seconds
        setInterval(() => {
            this.loadServerStatus();
        }, 30000);

        // Poll client list every 60 seconds
        setInterval(() => {
            this.loadActiveClients();
        }, 60000);
    }
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new STTDashboard();
});

// Make dashboard globally available for inline event handlers
window.dashboard = dashboard;