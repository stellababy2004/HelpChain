/**
 * HelpChain WebSocket Client
 * Provides real-time communication for analytics, notifications, and chat
 */
class HelpChainWebSocket {
    constructor(serverUrl) {
        this.logClientVersion();
        this.serverUrl = serverUrl;
        this.socket = null;
        this.eventListeners = {};
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.supportsNativeWebSocket = typeof window.WebSocket === 'function';
        this.forcePolling = this.shouldForcePolling();
        this.defaultTransports = this.forcePolling ? ['polling'] : ['websocket', 'polling'];
        this.lastUserInfo = {};
        this.hasDowngradedToPolling = this.forcePolling;

        if (!Array.isArray(window.HELPCHAIN_SOCKET_TRANSPORTS)) {
            window.HELPCHAIN_SOCKET_TRANSPORTS = [...this.defaultTransports];
        }
    }

    logClientVersion() {
        if (!window.__HELPCHAIN_WS_VERSION_LOGGED__) {
            console.info('HelpChain WebSocket client version: 20251028a');
            window.__HELPCHAIN_WS_VERSION_LOGGED__ = true;
        }
    }

    shouldForcePolling() {
        if (window.HELPCHAIN_FORCE_POLLING === true) {
            return true;
        }

        const dataset = document?.body?.dataset;
        if (dataset?.forcePolling === 'true') {
            return true;
        }

        return false;
    }

    // Normalize transport list while respecting explicit overrides
    sanitizeTransportList(transports = []) {
        const normalized = transports
            .map((value) => (typeof value === 'string' ? value.trim().toLowerCase() : ''))
            .filter(Boolean);

        const unique = Array.from(new Set(normalized));

        if (this.forcePolling || !this.supportsNativeWebSocket) {
            const filtered = unique.filter((value) => value !== 'websocket');
            if (!filtered.includes('polling')) {
                filtered.push('polling');
            }
            window.HELPCHAIN_SOCKET_TRANSPORTS = filtered;
            return filtered;
        }

        if (!unique.includes('websocket')) {
            unique.unshift('websocket');
        }
        if (!unique.includes('polling')) {
            unique.push('polling');
        }

        window.HELPCHAIN_SOCKET_TRANSPORTS = unique;
        return unique;
    }

    isInvalidTransportError(error) {
        const status = error?.context?.status || error?.description?.status;
        if (status === 400) {
            return true;
        }

        const message = error?.message || error?.description || '';
        if (typeof message !== 'string') {
            return false;
        }
        const normalized = message.toLowerCase();
        return (
            normalized.includes('transport unknown') ||
            normalized.includes('invalid transport') ||
            normalized.includes('websocket error')
        );
    }

    /**
     * Determine which transports the server actually supports.
     * Falls back to the Socket.IO defaults if nothing is provided.
     * @returns {Array<string>} ordered transport list
     */
    getConfiguredTransports() {
        if (
            Array.isArray(window.HELPCHAIN_SOCKET_TRANSPORTS) &&
            window.HELPCHAIN_SOCKET_TRANSPORTS.length
        ) {
            return this.sanitizeTransportList(window.HELPCHAIN_SOCKET_TRANSPORTS);
        }

        const dataset = document?.body?.dataset;
        if (dataset?.socketTransports) {
            console.debug('Detected socket transports from dataset:', dataset.socketTransports);
            const parsed = dataset.socketTransports
                .split(',')
                .map((value) => value.trim())
                .filter(Boolean);
            if (parsed.length) {
                return this.sanitizeTransportList(parsed);
            }
        }

        return this.sanitizeTransportList(this.defaultTransports);
    }

    /**
     * Connect to the WebSocket server
     * @param {Object} userInfo - User information {userId, userName, userType}
     * @returns {Promise} Connection promise
     */
    async connect(userInfo = {}) {
        return new Promise((resolve, reject) => {
            try {
                this.lastUserInfo = userInfo || {};
                const transports = this.getConfiguredTransports();
                const supportsWebSocket = !this.forcePolling && transports.includes('websocket');
                console.info('HelpChain socket transports:', transports, 'upgrade:', supportsWebSocket);

                // Initialize Socket.IO connection
                this.socket = io(this.serverUrl, {
                    transports,
                    timeout: 20000,
                    forceNew: true,
                    reconnection: true,
                    reconnectionAttempts: this.maxReconnectAttempts,
                    reconnectionDelay: this.reconnectDelay,
                    upgrade: supportsWebSocket,
                    transportOptions: {
                        polling: {
                            extraHeaders: {},
                        },
                    },
                });

                if (this.socket?.io && supportsWebSocket) {
                    this.socket.io.opts.transports = transports;
                    this.socket.io.opts.upgrade = true;
                } else if (this.socket?.io) {
                    this.socket.io.opts.transports = ['polling'];
                    this.socket.io.opts.upgrade = false;
                }

                // Set up event listeners
                this.socket.on('connect', () => {
                    console.log('WebSocket connected:', this.socket.id);
                    this.isConnected = true;
                    this.reconnectAttempts = 0;

                    // Emit user info if provided
                    if (userInfo.userId) {
                        this.socket.emit('user_connect', userInfo);
                    }

                    // Trigger custom connect event
                    this.triggerEvent('connected', { socketId: this.socket.id });

                    resolve(this.socket);
                });

                this.socket.on('disconnect', (reason) => {
                    console.log('WebSocket disconnected:', reason);
                    this.isConnected = false;
                    if (reason === 'ping timeout' && !this.hasDowngradedToPolling) {
                        console.warn('Socket ping timeout detected; forcing polling mode.');
                        this.forcePolling = true;
                        this.hasDowngradedToPolling = true;
                        window.HELPCHAIN_FORCE_POLLING = true;
                        if (this.socket?.io) {
                            this.socket.io.opts.transports = ['polling'];
                            this.socket.io.opts.upgrade = false;
                        }
                    }
                    this.triggerEvent('disconnect', { reason });
                });

                this.socket.on('connect_error', (error) => {
                    if (supportsWebSocket && !this.hasDowngradedToPolling && this.isInvalidTransportError(error)) {
                        console.warn('Server rejected websocket transport; forcing polling-only mode.');
                        this.forcePolling = true;
                        this.hasDowngradedToPolling = true;
                        window.HELPCHAIN_FORCE_POLLING = true;

                        if (this.socket?.io) {
                            this.socket.io.opts.transports = ['polling'];
                            this.socket.io.opts.upgrade = false;
                        }

                        if (this.socket) {
                            this.socket.close();
                        }

                        setTimeout(() => {
                            this.connect(this.lastUserInfo)
                                .then(resolve)
                                .catch(reject);
                        }, this.reconnectDelay);
                        return;
                    }

                    if (supportsWebSocket && !this.hasDowngradedToPolling) {
                        console.error('WebSocket connection error:', error);
                    } else {
                        console.info('Socket connection issue (polling mode):', error?.message || error);
                    }
                    this.reconnectAttempts++;
                    this.triggerEvent('connect_error', { error, attempts: this.reconnectAttempts });

                    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                        reject(new Error(`Failed to connect after ${this.maxReconnectAttempts} attempts`));
                    }
                });

                this.socket.on('reconnect', (attemptNumber) => {
                    console.log('WebSocket reconnected after', attemptNumber, 'attempts');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    this.triggerEvent('reconnected', { attempts: attemptNumber });
                });

                // Set up generic message handler
                this.socket.on('message', (data) => {
                    this.triggerEvent('message', data);
                });

            } catch (error) {
                console.error('Failed to initialize WebSocket:', error);
                reject(error);
            }
        });
    }

    /**
     * Disconnect from the WebSocket server
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.isConnected = false;
        }
    }

    /**
     * Join an analytics room for real-time updates
     * @param {string} roomName - Name of the analytics room
     */
    joinAnalyticsRoom(roomName = 'analytics') {
        if (this.socket && this.isConnected) {
            this.socket.emit('join_analytics', { room: roomName });
        }
    }

    /**
     * Subscribe to specific analytics metrics
     * @param {Array} metrics - Array of metric names to subscribe to
     */
    subscribeAnalytics(metrics = ['requests', 'volunteers', 'performance']) {
        if (this.socket && this.isConnected) {
            this.socket.emit('subscribe_analytics', { metrics });
        }
    }

    /**
     * Join a chat room
     * @param {Object} roomInfo - Room information {roomId, userId, userName}
     */
    joinChatRoom(roomInfo) {
        if (this.socket && this.isConnected) {
            this.socket.emit('join_chat_room', roomInfo);
        }
    }

    /**
     * Leave a chat room
     * @param {Object} roomInfo - Room information {roomId, userId}
     */
    leaveChatRoom(roomInfo) {
        if (this.socket && this.isConnected) {
            this.socket.emit('leave_chat_room', roomInfo);
        }
    }

    /**
     * Send a chat message
     * @param {Object} messageData - Message data {roomId, userId, userName, message, messageType}
     */
    sendMessage(messageData) {
        if (this.socket && this.isConnected) {
            this.socket.emit('send_message', messageData);
        }
    }

    /**
     * Send typing indicator
     * @param {Object} typingData - Typing data {roomId, userId, userName, typing}
     */
    sendTyping(typingData) {
        if (this.socket && this.isConnected) {
            const event = typingData.typing ? 'typing_start' : 'typing_stop';
            this.socket.emit(event, typingData);
        }
    }

    /**
     * Mark messages as read
     * @param {Object} readData - Read data {roomId, userId, messageIds}
     */
    markMessagesRead(readData) {
        if (this.socket && this.isConnected) {
            this.socket.emit('mark_message_read', readData);
        }
    }

    /**
     * Join requests room for real-time updates
     * @param {Object} userInfo - User info {userType}
     */
    joinRequestsRoom(userInfo = {}) {
        if (this.socket && this.isConnected) {
            this.socket.emit('join_requests', userInfo);
        }
    }

    /**
     * Update volunteer status
     * @param {Object} statusData - Status data {volunteerId, status, location}
     */
    updateVolunteerStatus(statusData) {
        if (this.socket && this.isConnected) {
            this.socket.emit('volunteer_status_update', statusData);
        }
    }

    /**
     * Request volunteer location
     * @param {Object} requestData - Request data {volunteerId, requesterId}
     */
    requestVolunteerLocation(requestData) {
        if (this.socket && this.isConnected) {
            this.socket.emit('request_volunteer_location', requestData);
        }
    }

    /**
     * Update volunteer location
     * @param {Object} locationData - Location data {volunteerId, location}
     */
    updateVolunteerLocation(locationData) {
        if (this.socket && this.isConnected) {
            this.socket.emit('volunteer_location_update', locationData);
        }
    }

    /**
     * Update user presence
     * @param {Object} presenceData - Presence data {userId, status, userName}
     */
    updatePresence(presenceData) {
        if (this.socket && this.isConnected) {
            this.socket.emit('user_presence_update', presenceData);
        }
    }

    /**
     * Request live metrics update
     */
    requestLiveMetrics() {
        if (this.socket && this.isConnected) {
            this.socket.emit('request_live_metrics');
        }
    }

    /**
     * Register an event listener
     * @param {string} event - Event name
     * @param {Function} callback - Event callback function
     */
    on(event, callback) {
        if (!this.eventListeners[event]) {
            this.eventListeners[event] = [];
        }
        this.eventListeners[event].push(callback);

        // If socket exists, also listen on socket
        if (this.socket) {
            this.socket.on(event, callback);
        }
    }

    /**
     * Remove an event listener
     * @param {string} event - Event name
     * @param {Function} callback - Event callback function
     */
    off(event, callback) {
        if (this.eventListeners[event]) {
            const index = this.eventListeners[event].indexOf(callback);
            if (index > -1) {
                this.eventListeners[event].splice(index, 1);
            }
        }

        if (this.socket) {
            this.socket.off(event, callback);
        }
    }

    /**
     * Trigger a custom event
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    triggerEvent(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in ${event} callback:`, error);
                }
            });
        }
    }

    /**
     * Get connection status
     * @returns {boolean} Connection status
     */
    isConnected() {
        return this.isConnected && this.socket && this.socket.connected;
    }

    /**
     * Get socket ID
     * @returns {string|null} Socket ID
     */
    getSocketId() {
        return this.socket ? this.socket.id : null;
    }

    /**
     * Send a custom event
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emit(event, data) {
        if (this.socket && this.isConnected) {
            this.socket.emit(event, data);
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HelpChainWebSocket;
}
