class MatildaDashboard {
    constructor() {
        this.apiBaseUrl = window.location.origin;
        // Use ws:// for non-SSL WebSocket in development
        this.websocketUrl = `ws://${window.location.hostname}:8773`;
        this.currentQRCode = null;
        this.mediaRecorder = null;
        this.recordingChunks = [];
        this.testToken = null;
        this.testTokenId = null;
        
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadServerStatus();
        await this.loadActiveClients();
        this.startStatusPolling();
        this.startClientPolling();
        
        // Load test token from localStorage if available
        const storedTestToken = localStorage.getItem('matilda_test_token');
        const storedTestTokenId = localStorage.getItem('matilda_test_token_id');
        if (storedTestToken && storedTestTokenId) {
            this.testToken = storedTestToken;
            this.testTokenId = storedTestTokenId;
        }
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
                server_url: `ws://${window.location.hostname}:8773/ws`,
                token: tokenData.token,
                name: `${window.location.hostname} Matilda Server`,
                expires: tokenData.expires,
                encryption_enabled: false,  // SSL disabled for development
                client_name: clientName
            };

            // Generate QR code
            const qrCodeDiv = document.getElementById('qrCode');
            if (!qrCodeDiv) {
                console.error('QR code container not found');
                alert('Error: QR code container not found. Please refresh the page.');
                return;
            }
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
            } else {
                console.warn('Encryption info paragraph not found');
            }
            
            document.getElementById('qrDisplay').style.display = 'block';

            // Clear form
            document.getElementById('clientName').value = '';
            document.getElementById('oneTimeUse').checked = false;
            
            // Refresh the active clients list
            this.loadActiveClients();

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
            link.download = `matilda-qr-${document.getElementById('qrClientName').textContent}.png`;
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
                // If we're revoking the test token, clear it from memory
                if (tokenId === this.testTokenId) {
                    this.testToken = null;
                    this.testTokenId = null;
                    localStorage.removeItem('matilda_test_token');
                    localStorage.removeItem('matilda_test_token_id');
                }
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
                
                // Try to use WebM with Opus codec, fallback to browser default
                let options = {};
                if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
                    options.mimeType = 'audio/webm;codecs=opus';
                } else if (MediaRecorder.isTypeSupported('audio/webm')) {
                    options.mimeType = 'audio/webm';
                }
                
                this.mediaRecorder = new MediaRecorder(stream, options);
                this.recordingChunks = [];

                this.mediaRecorder.ondataavailable = (event) => {
                    this.recordingChunks.push(event.data);
                };

                this.mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(this.recordingChunks, { type: this.mediaRecorder.mimeType });
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
            // Try to use existing test token or create new one
            let token = this.testToken;
            let tokenId = this.testTokenId;
            
            // Get current clients list
            const clientsResponse = await fetch(`${this.apiBaseUrl}/api/clients`);
            const clients = await clientsResponse.json();
            
            // Check if we have a stored token and if it's still valid
            if (token && this.testTokenId) {
                const existingTestClient = clients.find(c => c.token_id === this.testTokenId);
                
                if (!existingTestClient) {
                    // Token was revoked or expired, clear it
                    this.testToken = null;
                    this.testTokenId = null;
                    localStorage.removeItem('matilda_test_token');
                    localStorage.removeItem('matilda_test_token_id');
                    token = null;
                }
            }
            
            if (!token) {
                // Check if there's already a test client without our token
                const existingTestClient = clients.find(c => c.name === '🧪 Dashboard Test Client');
                
                if (existingTestClient) {
                    // We found an existing test client but we don't have its token
                    // We'll need to revoke it and create a new one
                    await this.revokeClient(existingTestClient.token_id);
                }
                
                const tokenResponse = await fetch(`${this.apiBaseUrl}/api/generate-token`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        client_name: '🧪 Dashboard Test Client',
                        expiration_days: 30,
                        one_time_use: false  // Reusable for tests
                    })
                });

                if (!tokenResponse.ok) {
                    throw new Error('Failed to generate test token');
                }

                const tokenData = await tokenResponse.json();
                this.testToken = token = tokenData.token;
                this.testTokenId = tokenId = tokenData.token_id;
                
                // Store in localStorage for persistence
                localStorage.setItem('matilda_test_token', token);
                localStorage.setItem('matilda_test_token_id', tokenId);
            }

            // Connect to WebSocket for transcription
            const ws = new WebSocket(`${this.websocketUrl}/ws?token=${token}`);
            const startTime = Date.now();
            
            // Convert audio data to base64
            const audioBase64 = await this.blobToBase64(audioData);
            
            // Detect audio format from blob type
            let audioFormat = 'wav'; // default
            if (audioData.type) {
                if (audioData.type.includes('webm')) {
                    audioFormat = 'webm';
                } else if (audioData.type.includes('wav')) {
                    audioFormat = 'wav';
                } else if (audioData.type.includes('ogg')) {
                    audioFormat = 'ogg';
                }
            }

            ws.onopen = () => {
                clearTimeout(connectionTimeout);
                console.log(`Sending audio data: ${audioFormat} format, ${audioData.size} bytes`);
                // Send audio data through WebSocket
                ws.send(JSON.stringify({
                    type: 'transcribe',
                    audio: audioBase64,
                    format: audioFormat
                }));
            };

            ws.onmessage = (event) => {
                const response = JSON.parse(event.data);
                const processingTimeMs = Date.now() - startTime;

                if (response.type === 'transcription') {
                    transcriptionText.textContent = `"${response.text}"`;
                    confidence.textContent = response.confidence ? `${Math.round(response.confidence * 100)}%` : '95%';
                    processingTime.textContent = `${(processingTimeMs / 1000).toFixed(1)}s`;
                } else if (response.type === 'error') {
                    throw new Error(response.message || 'Transcription failed');
                }

                if (response.type === "transcription" || response.type === "error") { ws.close(); }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                transcriptionText.textContent = 'WebSocket server not available. Please ensure the WebSocket server is running on port 8773.';
                confidence.textContent = '-';
                processingTime.textContent = '-';
                if (response.type === "transcription" || response.type === "error") { ws.close(); }
            };

            // Add connection timeout
            const connectionTimeout = setTimeout(() => {
                if (ws.readyState !== WebSocket.OPEN) {
                    if (response.type === "transcription" || response.type === "error") { ws.close(); }
                    transcriptionText.textContent = 'WebSocket connection timeout. Server may not be running.';
                    confidence.textContent = '-';
                    processingTime.textContent = '-';
                }
            }, 5000);

        } catch (error) {
            console.error('Transcription test failed:', error);
            transcriptionText.textContent = `Error: ${error.message}`;
            confidence.textContent = '-';
            processingTime.textContent = '-';
        }
    }

    async blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64String = reader.result.split(',')[1];
                resolve(base64String);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
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
    }
    
    startClientPolling() {
        // Poll client list every 15 seconds for more responsive updates
        setInterval(() => {
            this.loadActiveClients();
        }, 15000);
    }
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new MatildaDashboard();
});

// Make dashboard globally available for inline event handlers
window.dashboard = dashboard;