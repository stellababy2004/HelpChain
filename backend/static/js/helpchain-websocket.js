/**
 * HelpChain WebSocket Client Library
 * Provides easy-to-use methods for real-time communication with the HelpChain backend
 */

class HelpChainWebSocket {
    constructor(serverUrl = 'ws://localhost:5000') {
        this.serverUrl = serverUrl;
        this.socket = null;
        this.isConnected = false;
        this.eventListeners = {};
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.userId = null;
        this.userName = null;
        this.currentRoom = null;
    }

    /**
     * Connect to the WebSocket server
     * @param {Object} options - Connection options
     * @param {string} options.userId - User ID for identification
     * @param {string} options.userName - User display name
     * @param {string} options.userType - User type (admin, volunteer, requester)
     * @returns {Promise} Connection promise
     */
    connect(options = {}) {
        return new Promise((resolve, reject) => {
            try {
                this.socket = io(this.serverUrl, {
                    cors: {
                        origin: "*",
                        methods: ["GET", "POST"]
                    }
                });

                this.socket.on('connect', () => {
                    console.log('Connected to HelpChain WebSocket server');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;

                    // Store user info
                    if (options.userId) this.userId = options.userId;
                    if (options.userName) this.userName = options.userName;

                    // Emit connected event
                    this.emit('connected', { status: 'success', sid: this.socket.id });

                    resolve();
                });

                this.socket.on('disconnect', () => {
                    console.log('Disconnected from HelpChain WebSocket server');
                    this.isConnected = false;
                    this._handleReconnect();
                });

                this.socket.on('connect_error', (error) => {
                    console.error('WebSocket connection error:', error);
                    reject(error);
                });

                // Set up default event listeners
                this._setupDefaultListeners();

            } catch (error) {
                console.error('Failed to connect to WebSocket server:', error);
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
     * Set up default event listeners
     * @private
     */
    _setupDefaultListeners() {
        // Handle connection status
        this.socket.on('connected', (data) => {
            this._triggerEvent('connected', data);
        });

        // Handle errors
        this.socket.on('message_error', (data) => {
            this._triggerEvent('error', data);
        });

        // Handle user status changes
        this.socket.on('user_status_change', (data) => {
            this._triggerEvent('user_status_change', data);
        });

        // Handle user presence changes
        this.socket.on('user_presence_changed', (data) => {
            this._triggerEvent('user_presence_changed', data);
        });
    }

    /**
     * Handle reconnection logic
     * @private
     */
    _handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(() => {
                this.connect({
                    userId: this.userId,
                    userName: this.userName
                }).catch(() => {
                    this._handleReconnect();
                });
            }, this.reconnectDelay * this.reconnectAttempts);
        } else {
            console.error('Max reconnection attempts reached');
            this._triggerEvent('reconnect_failed');
        }
    }

    // ===== CHAT FUNCTIONALITY =====

    /**
     * Join a chat room
     * @param {string} roomId - Room ID to join
     * @returns {Promise}
     */
    joinChatRoom(roomId) {
        return new Promise((resolve, reject) => {
            if (!this.isConnected) {
                reject(new Error('Not connected to WebSocket server'));
                return;
            }

            this.socket.emit('join_chat_room', {
                room_id: roomId,
                user_id: this.userId,
                user_name: this.userName
            });

            // Set up room-specific listeners
            this._setupChatRoomListeners(roomId);

            // Wait for confirmation
            const timeout = setTimeout(() => {
                reject(new Error('Join room timeout'));
            }, 5000);

            this.socket.once('joined_room', (data) => {
                clearTimeout(timeout);
                this.currentRoom = roomId;
                resolve(data);
            });
        });
    }

    /**
     * Leave the current chat room
     * @returns {Promise}
     */
    leaveChatRoom() {
        return new Promise((resolve, reject) => {
            if (!this.currentRoom) {
                resolve();
                return;
            }

            this.socket.emit('leave_chat_room', {
                room_id: this.currentRoom,
                user_id: this.userId,
                user_name: this.userName
            });

            this.currentRoom = null;
            resolve();
        });
    }

    /**
     * Send a chat message
     * @param {string} message - Message text
     * @param {string} messageType - Message type (text, image, file, etc.)
     * @returns {Promise}
     */
    sendMessage(message, messageType = 'text') {
        return new Promise((resolve, reject) => {
            if (!this.isConnected || !this.currentRoom) {
                reject(new Error('Not connected or not in a room'));
                return;
            }

            this.socket.emit('send_message', {
                room_id: this.currentRoom,
                user_id: this.userId,
                user_name: this.userName,
                message: message,
                message_type: messageType
            });

            // Wait for confirmation or error
            const timeout = setTimeout(() => {
                reject(new Error('Send message timeout'));
            }, 5000);

            const handleNewMessage = (data) => {
                if (data.sender_id === this.userId) {
                    clearTimeout(timeout);
                    this.socket.off('new_message', handleNewMessage);
                    resolve(data);
                }
            };

            const handleError = (data) => {
                clearTimeout(timeout);
                this.socket.off('message_error', handleError);
                reject(new Error(data.error || 'Failed to send message'));
            };

            this.socket.on('new_message', handleNewMessage);
            this.socket.on('message_error', handleError);
        });
    }

    /**
     * Start typing indicator
     */
    startTyping() {
        if (this.isConnected && this.currentRoom) {
            this.socket.emit('typing_start', {
                room_id: this.currentRoom,
                user_id: this.userId,
                user_name: this.userName
            });
        }
    }

    /**
     * Stop typing indicator
     */
    stopTyping() {
        if (this.isConnected && this.currentRoom) {
            this.socket.emit('typing_stop', {
                room_id: this.currentRoom,
                user_id: this.userId,
                user_name: this.userName
            });
        }
    }

    /**
     * Mark messages as read
     * @param {Array} messageIds - Array of message IDs to mark as read
     */
    markMessagesRead(messageIds) {
        if (this.isConnected && this.currentRoom) {
            this.socket.emit('mark_message_read', {
                room_id: this.currentRoom,
                user_id: this.userId,
                message_ids: messageIds
            });
        }
    }

    /**
     * Set up chat room event listeners
     * @param {string} roomId - Room ID
     * @private
     */
    _setupChatRoomListeners(roomId) {
        // Listen for new messages
        this.socket.on('new_message', (data) => {
            this._triggerEvent('new_message', data);
        });

        // Listen for user join/leave events
        this.socket.on('user_joined', (data) => {
            this._triggerEvent('user_joined', data);
        });

        this.socket.on('user_left', (data) => {
            this._triggerEvent('user_left', data);
        });

        // Listen for typing indicators
        this.socket.on('user_typing', (data) => {
            this._triggerEvent('user_typing', data);
        });

        // Listen for read receipts
        this.socket.on('messages_read', (data) => {
            this._triggerEvent('messages_read', data);
        });
    }

    // ===== ANALYTICS FUNCTIONALITY =====

    /**
     * Join analytics room for real-time updates
     * @param {string} room - Analytics room name (default: 'analytics')
     */
    joinAnalyticsRoom(room = 'analytics') {
        if (this.isConnected) {
            this.socket.emit('join_analytics', { room: room });
        }
    }

    /**
     * Leave analytics room
     * @param {string} room - Analytics room name
     */
    leaveAnalyticsRoom(room = 'analytics') {
        if (this.isConnected) {
            this.socket.emit('leave_analytics', { room: room });
        }
    }

    /**
     * Request analytics update
     */
    requestAnalyticsUpdate() {
        if (this.isConnected) {
            this.socket.emit('request_analytics_update');
        }
    }

    /**
     * Subscribe to personalized analytics updates
     * @param {Array} metrics - Array of metric names to subscribe to
     */
    subscribeAnalytics(metrics = []) {
        if (this.isConnected && this.userId) {
            this.socket.emit('subscribe_analytics', {
                user_id: this.userId,
                metrics: metrics
            });
        }
    }

    /**
     * Unsubscribe from analytics updates
     */
    unsubscribeAnalytics() {
        if (this.isConnected && this.userId) {
            this.socket.emit('unsubscribe_analytics', {
                user_id: this.userId
            });
        }
    }

    /**
     * Request live metrics update
     */
    requestLiveMetrics() {
        if (this.isConnected) {
            this.socket.emit('request_live_metrics');
        }
    }

    // ===== REQUEST MANAGEMENT FUNCTIONALITY =====

    /**
     * Join requests room for real-time updates
     * @param {string} userType - User type (admin, volunteer, requester)
     */
    joinRequestsRoom(userType = 'volunteer') {
        if (this.isConnected) {
            this.socket.emit('join_requests', { user_type: userType });
        }
    }

    /**
     * Leave requests room
     * @param {string} userType - User type
     */
    leaveRequestsRoom(userType = 'volunteer') {
        if (this.isConnected) {
            this.socket.emit('leave_requests', { user_type: userType });
        }
    }

    /**
     * Update request status (admin only)
     * @param {string} requestId - Request ID
     * @param {string} status - New status
     */
    updateRequestStatus(requestId, status) {
        if (this.isConnected) {
            this.socket.emit('request_status_update', {
                request_id: requestId,
                status: status
            });
        }
    }

    /**
     * Assign volunteer to request (admin only)
     * @param {string} requestId - Request ID
     * @param {string} volunteerId - Volunteer ID
     */
    assignVolunteer(requestId, volunteerId) {
        if (this.isConnected) {
            this.socket.emit('volunteer_assigned', {
                request_id: requestId,
                volunteer_id: volunteerId
            });
        }
    }

    // ===== VOLUNTEER STATUS FUNCTIONALITY =====

    /**
     * Update volunteer status
     * @param {string} status - Status (available, busy, offline)
     * @param {Object} location - Optional location data {lat, lng}
     */
    updateVolunteerStatus(status, location = null) {
        if (this.isConnected) {
            this.socket.emit('volunteer_status_update', {
                volunteer_id: this.userId,
                status: status,
                location: location
            });
        }
    }

    /**
     * Request volunteer location
     * @param {string} volunteerId - Volunteer ID to request location from
     */
    requestVolunteerLocation(volunteerId) {
        if (this.isConnected) {
            this.socket.emit('request_volunteer_location', {
                volunteer_id: volunteerId,
                requester_id: this.userId
            });
        }
    }

    /**
     * Update volunteer location
     * @param {Object} location - Location data {lat, lng}
     */
    updateVolunteerLocation(location) {
        if (this.isConnected) {
            this.socket.emit('volunteer_location_update', {
                volunteer_id: this.userId,
                location: location
            });
        }
    }

    // ===== USER PRESENCE FUNCTIONALITY =====

    /**
     * Update user presence status
     * @param {string} status - Presence status (online, away, busy, offline)
     */
    updatePresence(status) {
        if (this.isConnected) {
            this.socket.emit('user_presence_update', {
                user_id: this.userId,
                status: status,
                user_name: this.userName
            });
        }
    }

    /**
     * Get list of online users
     */
    getOnlineUsers() {
        if (this.isConnected) {
            this.socket.emit('get_online_users');
        }
    }

    // ===== EVENT MANAGEMENT =====

    /**
     * Listen for events
     * @param {string} event - Event name
     * @param {Function} callback - Event callback function
     */
    on(event, callback) {
        if (!this.eventListeners[event]) {
            this.eventListeners[event] = [];
        }
        this.eventListeners[event].push(callback);

        // Set up WebSocket listener for server events
        if (this.socket && !this.socket.hasListeners(event)) {
            this.socket.on(event, (data) => {
                this._triggerEvent(event, data);
            });
        }
    }

    /**
     * Remove event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function to remove
     */
    off(event, callback) {
        if (this.eventListeners[event]) {
            const index = this.eventListeners[event].indexOf(callback);
            if (index > -1) {
                this.eventListeners[event].splice(index, 1);
            }
        }
    }

    /**
     * Emit custom event to server
     * @param {string} event - Event name
     * @param {Object} data - Event data
     */
    emit(event, data) {
        if (this.socket) {
            this.socket.emit(event, data);
        }
    }

    /**
     * Trigger local event
     * @param {string} event - Event name
     * @param {Object} data - Event data
     * @private
     */
    _triggerEvent(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in event listener for ${event}:`, error);
                }
            });
        }
    }

    // ===== UTILITY METHODS =====

    /**
     * Check if connected to server
     * @returns {boolean}
     */
    isConnected() {
        return this.isConnected;
    }

    /**
     * Get current user ID
     * @returns {string}
     */
    getUserId() {
        return this.userId;
    }

    /**
     * Get current room
     * @returns {string}
     */
    getCurrentRoom() {
        return this.currentRoom;
    }

    /**
     * Get connection status
     * @returns {Object}
     */
    getStatus() {
        return {
            connected: this.isConnected,
            userId: this.userId,
            userName: this.userName,
            currentRoom: this.currentRoom,
            serverUrl: this.serverUrl
        };
    }
}

// Export for different module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HelpChainWebSocket;
} else if (typeof define === 'function' && define.amd) {
    define([], function() { return HelpChainWebSocket; });
} else if (typeof window !== 'undefined') {
    window.HelpChainWebSocket = HelpChainWebSocket;
}
