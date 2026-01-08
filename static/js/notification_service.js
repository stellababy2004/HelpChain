/**
 * HelpChain Notification Service
 * Handles browser push notifications, email, and SMS notifications
 */

class HelpChainNotificationService {
  constructor() {
    this.pushSupported = "Notification" in window;
    this.pushPermission = null;
    this.swRegistration = null;
    this.settings = this.loadSettings();
    this.eventListeners = {};
    this.pushAvailable = true; // Tracks whether server-side push configuration is ready
    this.hasShownPushFallbackAlert = false;
  }

  /**
   * Initialize the notification service
   */
  async initialize() {
    if (this.pushSupported) {
      this.pushPermission = await Notification.requestPermission();
      await this.registerServiceWorker();
      this.updateUI();
    }

    // Listen for messages from service worker
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.addEventListener(
        "message",
        this.handleServiceWorkerMessage.bind(this),
      );
    }

    // Listen for visibility changes to show pending notifications
    document.addEventListener(
      "visibilitychange",
      this.handleVisibilityChange.bind(this),
    );

    console.log("HelpChain Notification Service initialized");
  }

  /**
   * Register service worker for push notifications
   */
  async registerServiceWorker() {
    if ("serviceWorker" in navigator) {
      try {
        this.swRegistration = await navigator.serviceWorker.register("/sw.js");
        console.log("Service Worker registered successfully");

        // Handle push subscription
        if (this.pushAvailable) {
          await this.subscribeToPush();
        }
      } catch (error) {
        console.error("Service Worker registration failed:", error);
      }
    }
  }

  /**
   * Subscribe to push notifications
   */
  async subscribeToPush() {
    if (!this.swRegistration) return;

    // Check if permission is granted before attempting subscription
    if (this.pushPermission !== "granted") {
      console.log("Push permission not granted, skipping subscription");
      return;
    }

    try {
      // Get VAPID public key from server
      const vapidResponse = await fetch("/api/notification/vapid-public-key");

      if (!vapidResponse.ok) {
        console.warn(
          "Push notifications disabled: VAPID endpoint returned",
          vapidResponse.status,
        );
        this.handlePushUnavailable("missing-vapid-endpoint");
        return;
      }

      const vapidData = await vapidResponse.json();

      if (!vapidData.success || !vapidData.publicKey) {
        console.warn("Push notifications disabled: VAPID key not configured");
        this.handlePushUnavailable("missing-vapid-key");
        return;
      }

      // Convert VAPID public key to Uint8Array
      const applicationServerKey = this.urlB64ToUint8Array(vapidData.publicKey);

      // Subscribe to push notifications
      const subscription = await this.swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey,
      });

      // Get subscription details
      const p256dhKey = this.arrayBufferToBase64(subscription.getKey("p256dh"));
      const authKey = this.arrayBufferToBase64(subscription.getKey("auth"));

      // Send subscription to server
      const response = await fetch("/api/notification/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          endpoint: subscription.endpoint,
          p256dh: p256dhKey,
          auth: authKey,
          userAgent: navigator.userAgent,
        }),
      });

      if (response.ok) {
        console.log("Push subscription successful");
        this.settings.pushEnabled = true;
        localStorage.setItem(
          "helpchain_notifications",
          JSON.stringify(this.settings),
        );
      } else {
        console.error("Push subscription failed:", response.statusText);
        this.handlePushUnavailable("subscription-response-error");
      }
    } catch (error) {
      console.error("Push subscription failed:", error);
      this.handlePushUnavailable("subscription-exception");
    }
  }

  /**
   * Convert VAPID key to Uint8Array
   */
  urlB64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, "+")
      .replace(/_/g, "/");

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  /**
   * Convert ArrayBuffer to base64 string
   */
  arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }

  /**
   * Request push notification permission
   */
  async requestPushPermission() {
    if (!this.pushSupported) {
      this.showAlert(
        "Votre navigateur ne prend pas en charge les notifications push.",
        "warning",
      );
      return false;
    }

    try {
      this.pushPermission = await Notification.requestPermission();

      if (this.pushPermission === "granted") {
        this.showAlert("Les notifications push sont activées !", "success");
        await this.registerServiceWorker();
        this.updateUI();
        this.showTestNotification();
        return true;
      } else {
        this.showAlert("Les notifications push ont été refusées.", "warning");
        return false;
      }
    } catch (error) {
      console.error("Error requesting push permission:", error);
      this.showAlert(
        "Une erreur s'est produite lors de la demande d'autorisation.",
        "error",
      );
      return false;
    }
  }

  /**
   * Show a test push notification
   */
  showTestNotification() {
    if (this.pushPermission !== "granted") return;

    const notification = new Notification("HelpChain - Test", {
      body: "Ceci est une notification de test. Les notifications push fonctionnent !",
      icon: "/static/favicon.ico",
      badge: "/static/favicon.ico",
      tag: "test-notification",
      requireInteraction: false,
      silent: false,
    });

    notification.onclick = () => {
      window.focus();
      notification.close();
    };

    // Auto close after 4 seconds
    setTimeout(() => notification.close(), 4000);
  }

  /**
   * Show notification for new help request
   */
  showNewRequestNotification(request) {
    if (
      this.pushPermission !== "granted" ||
      !this.settings.pushEnabled ||
      !this.settings.notifyNewRequests
    ) {
      return;
    }

    const notification = new Notification("Nouvelle demande d'aide", {
      body: `${request.category} - ${request.distance}km de vous`,
      icon: "/static/favicon.ico",
      badge: "/static/favicon.ico",
      tag: `request-${request.id}`,
      requireInteraction: true,
      data: { requestId: request.id, type: "new_request" },
    });

    notification.onclick = () => {
      window.open(`/request/${request.id}`, "_blank");
      notification.close();
    };

    // Track notification shown
    this.trackEvent("notification_shown", "new_request", request.id);
  }

  /**
   * Show urgent request notification
   */
  showUrgentNotification(request) {
    if (
      this.pushPermission !== "granted" ||
      !this.settings.pushEnabled ||
      !this.settings.notifyUrgentRequests
    ) {
      return;
    }

    const notification = new Notification("Demande URGENTE !", {
      body: `${request.category} - Besoin d'aide immédiate !`,
      icon: "/static/favicon.ico",
      badge: "/static/favicon.ico",
      tag: `urgent-${request.id}`,
      requireInteraction: true,
      silent: false,
      data: { requestId: request.id, type: "urgent_request" },
    });

    notification.onclick = () => {
      window.open(`/request/${request.id}`, "_blank");
      notification.close();
    };

    // Track urgent notification
    this.trackEvent("notification_shown", "urgent_request", request.id);
  }

  /**
   * Show message notification
   */
  showMessageNotification(message) {
    if (
      this.pushPermission !== "granted" ||
      !this.settings.pushEnabled ||
      !this.settings.notifyMessages
    ) {
      return;
    }

    const notification = new Notification(
      `Nouveau message de ${message.sender}`,
      {
        body:
          message.content.substring(0, 100) +
          (message.content.length > 100 ? "..." : ""),
        icon: "/static/favicon.ico",
        badge: "/static/favicon.ico",
        tag: `chat-${message.chatId}`,
        data: { chatId: message.chatId, type: "message" },
      },
    );

    notification.onclick = () => {
      window.open(`/chat/${message.chatId}`, "_blank");
      notification.close();
    };

    // Track message notification
    this.trackEvent("notification_shown", "message", message.chatId);
  }

  /**
   * Show task update notification
   */
  showTaskUpdateNotification(task) {
    if (
      this.pushPermission !== "granted" ||
      !this.settings.pushEnabled ||
      !this.settings.notifyTaskUpdates
    ) {
      return;
    }

    const notification = new Notification("Mise à jour de la tâche", {
      body: `Tâche "${task.title}" - ${task.status}`,
      icon: "/static/favicon.ico",
      badge: "/static/favicon.ico",
      tag: `task-${task.id}`,
      data: { taskId: task.id, type: "task_update" },
    });

    notification.onclick = () => {
      window.open(`/task/${task.id}`, "_blank");
      notification.close();
    };
  }

  /**
   * Send test email
   */
  async sendTestEmail() {
    try {
      this.showLoading("Envoi de l'e-mail de test...");

      const response = await fetch("/api/notification/test-email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      this.hideLoading();

      if (response.ok) {
        this.showAlert(
          "L'e-mail de test a été envoyé avec succès !",
          "success",
        );
      } else {
        throw new Error("Failed to send test email");
      }
    } catch (error) {
      this.hideLoading();
      console.error("Error sending test email:", error);
      this.showAlert("Erreur lors de l'envoi de l'e-mail de test.", "error");
    }
  }

  /**
   * Send test SMS
   */
  async sendTestSMS() {
    try {
      this.showLoading("Envoi du SMS de test...");

      const response = await fetch("/api/notification/test-sms", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      this.hideLoading();

      if (response.ok) {
        this.showAlert("Le SMS de test a été envoyé avec succès !", "success");
      } else {
        throw new Error("Failed to send test SMS");
      }
    } catch (error) {
      this.hideLoading();
      console.error("Error sending test SMS:", error);
      this.showAlert("Erreur lors de l'envoi du SMS de test.", "error");
    }
  }

  /**
   * Save notification settings
   */
  async saveSettings(settings) {
    try {
      this.showLoading("Enregistrement des paramètres...");

      const response = await fetch("/api/notification/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(settings),
      });

      this.hideLoading();

      if (response.ok) {
        this.settings = settings;
        localStorage.setItem(
          "helpchain_notifications",
          JSON.stringify(settings),
        );
        this.showAlert(
          "Les paramètres ont été enregistrés avec succès !",
          "success",
        );
        this.updateUI();
        return true;
      } else {
        throw new Error("Failed to save settings");
      }
    } catch (error) {
      this.hideLoading();
      console.error("Error saving settings:", error);
      this.showAlert(
        "Erreur lors de l'enregistrement des paramètres.",
        "error",
      );
      return false;
    }
  }

  /**
   * Load notification settings
   */
  loadSettings() {
    const defaultSettings = {
      pushEnabled: false,
      emailEnabled: true,
      smsEnabled: false,
      notifyNewRequests: true,
      notifyUrgentRequests: true,
      notifyMessages: true,
      notifyTaskUpdates: true,
      notifyVolunteerFound: true,
      notifyTaskProgress: true,
      notifyCompletion: true,
      notifyFeedback: true,
    };

    try {
      const saved = localStorage.getItem("helpchain_notifications");
      return saved
        ? { ...defaultSettings, ...JSON.parse(saved) }
        : defaultSettings;
    } catch (error) {
      console.error("Error loading settings:", error);
      return defaultSettings;
    }
  }

  /**
   * Update UI elements based on current state
   */
  updateUI() {
    // Update push notification UI
    const pushBadge = document.getElementById("pushPermissionBadge");
    const pushCheckbox = document.getElementById("pushNotifications");

    if (pushBadge && pushCheckbox) {
      if (!this.pushAvailable) {
        pushBadge.className = "badge badge-denied";
        pushBadge.textContent = "Indisponible";
        pushCheckbox.disabled = true;
        pushCheckbox.checked = false;
      } else if (this.pushPermission === "granted") {
        pushBadge.className = "badge badge-permission";
        pushBadge.textContent = "Autorisées";
        pushCheckbox.disabled = false;
        pushCheckbox.checked = this.settings.pushEnabled;
      } else if (this.pushPermission === "denied") {
        pushBadge.className = "badge badge-denied";
        pushBadge.textContent = "Bloquées";
        pushCheckbox.disabled = true;
        pushCheckbox.checked = false;
      } else {
        pushBadge.className = "badge badge-denied";
        pushBadge.textContent = "Non autorisées";
        pushCheckbox.disabled = true;
        pushCheckbox.checked = false;
      }
    }

    // Update email and SMS checkboxes
    const emailCheckbox = document.getElementById("emailNotifications");
    const smsCheckbox = document.getElementById("smsNotifications");

    if (emailCheckbox) emailCheckbox.checked = this.settings.emailEnabled;
    if (smsCheckbox) smsCheckbox.checked = this.settings.smsEnabled;

    // Update notification type checkboxes
    const checkboxes = [
      "notifyNewRequests",
      "notifyUrgentRequests",
      "notifyMessages",
      "notifyTaskUpdates",
      "notifyVolunteerFound",
      "notifyTaskProgress",
      "notifyCompletion",
      "notifyFeedback",
    ];

    checkboxes.forEach((id) => {
      const checkbox = document.getElementById(id);
      if (checkbox) {
        checkbox.checked = this.settings[id];
      }
    });
  }

  /**
   * Gracefully disable push features when server configuration is missing
   */
  handlePushUnavailable(reason) {
    this.pushAvailable = false;
    this.settings.pushEnabled = false;
    try {
      localStorage.setItem(
        "helpchain_notifications",
        JSON.stringify(this.settings),
      );
    } catch (storageError) {
      console.warn("Unable to persist notification settings:", storageError);
    }

    this.updateUI();

    if (!this.hasShownPushFallbackAlert) {
      const messageMap = {
        "missing-vapid-endpoint":
          "Les notifications push sont temporairement désactivées (configuration serveur manquante).",
        "missing-vapid-key":
          "Les notifications push sont temporairement désactivées car la clé VAPID n'est pas configurée.",
        "subscription-response-error":
          "Les notifications push sont temporairement désactivées en raison d'une erreur d'abonnement.",
        "subscription-exception":
          "Les notifications push sont temporairement désactivées. Vérifiez la configuration et réessayez.",
      };
      this.showAlert(
        messageMap[reason] ||
          "Les notifications push ne sont pas disponibles actuellement.",
        "warning",
      );
      this.hasShownPushFallbackAlert = true;
    }
  }

  /**
   * Handle service worker messages
   */
  handleServiceWorkerMessage(event) {
    const data = event.data;

    switch (data.type) {
      case "notification_click":
        this.handleNotificationClick(data.payload);
        break;
      case "push_received":
        this.handlePushReceived(data.payload);
        break;
    }
  }

  /**
   * Handle notification click from service worker
   */
  handleNotificationClick(payload) {
    switch (payload.type) {
      case "new_request":
        window.open(`/request/${payload.requestId}`, "_blank");
        break;
      case "urgent_request":
        window.open(`/request/${payload.requestId}`, "_blank");
        break;
      case "message":
        window.open(`/chat/${payload.chatId}`, "_blank");
        break;
      case "task_update":
        window.open(`/task/${payload.taskId}`, "_blank");
        break;
    }
  }

  /**
   * Handle push notification received
   */
  handlePushReceived(payload) {
    // Show notification if page is not visible
    if (document.hidden) {
      switch (payload.type) {
        case "new_request":
          this.showNewRequestNotification(payload.data);
          break;
        case "urgent_request":
          this.showUrgentNotification(payload.data);
          break;
        case "message":
          this.showMessageNotification(payload.data);
          break;
        case "task_update":
          this.showTaskUpdateNotification(payload.data);
          break;
      }
    }
  }

  /**
   * Handle visibility change
   */
  handleVisibilityChange() {
    if (!document.hidden) {
      // Page became visible, could refresh data or hide notifications
      console.log("Page became visible");
    }
  }

  /**
   * Track analytics event
   */
  trackEvent(eventType, eventCategory, eventLabel = null) {
    // Send to analytics service if available
    if (window.analyticsService) {
      window.analyticsService.trackEvent(eventType, eventCategory, eventLabel);
    }
  }

  /**
   * Show loading indicator
   */
  showLoading(message = "Зареждане...") {
    // Create or update loading indicator
    let loader = document.getElementById("notification-loader");
    if (!loader) {
      loader = document.createElement("div");
      loader.id = "notification-loader";
      loader.className = "notification-loader";
      loader.innerHTML = `
                <div class="loader-backdrop"></div>
                <div class="loader-content">
                    <div class="spinner"></div>
                    <p>${message}</p>
                </div>
            `;
      document.body.appendChild(loader);
    } else {
      loader.querySelector("p").textContent = message;
      loader.style.display = "flex";
    }
  }

  /**
   * Hide loading indicator
   */
  hideLoading() {
    const loader = document.getElementById("notification-loader");
    if (loader) {
      loader.style.display = "none";
    }
  }

  /**
   * Show alert message
   */
  showAlert(message, type = "info") {
    // Create alert element
    const alert = document.createElement("div");
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

    // Add to page
    const container = document.querySelector(".container") || document.body;
    container.insertBefore(alert, container.firstChild);

    // Auto remove after 5 seconds
    setTimeout(() => {
      if (alert.parentNode) {
        alert.remove();
      }
    }, 5000);
  }

  /**
   * Add event listener
   */
  addEventListener(event, callback) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback);
  }

  /**
   * Remove event listener
   */
  removeEventListener(event, callback) {
    if (this.eventListeners[event]) {
      const index = this.eventListeners[event].indexOf(callback);
      if (index > -1) {
        this.eventListeners[event].splice(index, 1);
      }
    }
  }

  /**
   * Emit event
   */
  emit(event, data) {
    if (this.eventListeners[event]) {
      this.eventListeners[event].forEach((callback) => callback(data));
    }
  }
}

// Global notification service instance
const notificationService = new HelpChainNotificationService();

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () =>
    notificationService.initialize(),
  );
} else {
  notificationService.initialize();
}

// Export for global access
window.HelpChainNotificationService = HelpChainNotificationService;
window.notificationService = notificationService;
