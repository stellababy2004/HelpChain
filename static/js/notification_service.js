/**
 * HelpChain Push Notification Service
 * Handles browser push notification subscriptions and permissions
 */

class NotificationService {
  constructor() {
    this.registration = null;
    this.vapidPublicKey = null;
    this.isSubscribed = false;
    this.subscription = null;
  }

  /**
   * Initialize the notification service
   */
  async init() {
    try {
      // Check if the page is served over HTTPS or localhost
      const isSecureContext =
        window.location.protocol === "https:" ||
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1";

      if (!isSecureContext) {
        console.warn(
          "Push notifications require HTTPS. Skipping initialization.",
        );
        return false;
      }

      // Check if service workers are supported
      if (!("serviceWorker" in navigator)) {
        console.warn("Service workers not supported");
        return false;
      }

      // Check if push messaging is supported
      if (!("PushManager" in window)) {
        console.warn("Push messaging not supported");
        return false;
      }

      // Register service worker
      this.registration =
        await navigator.serviceWorker.register("/static/js/sw.js");
      console.log("Service Worker registered successfully");

      // Get VAPID public key
      await this.getVapidPublicKey();

      // Check current subscription status
      await this.checkSubscription();

      return true;
    } catch (error) {
      console.error("Failed to initialize notification service:", error);
      return false;
    }
  }

  /**
   * Get VAPID public key from server
   */
  async getVapidPublicKey() {
    try {
      const response = await fetch("/api/notification/vapid-public-key");
      const data = await response.json();

      if (data.success) {
        this.vapidPublicKey = data.publicKey;
        console.log("VAPID public key retrieved");
      } else {
        throw new Error(data.message || "Failed to get VAPID key");
      }
    } catch (error) {
      console.error("Failed to get VAPID public key:", error);
      throw error;
    }
  }

  /**
   * Check current subscription status
   */
  async checkSubscription() {
    try {
      const subscription =
        await this.registration.pushManager.getSubscription();
      this.isSubscribed = subscription !== null;
      this.subscription = subscription;

      if (this.isSubscribed) {
        console.log("User is already subscribed to push notifications");
      } else {
        console.log("User is not subscribed to push notifications");
      }
    } catch (error) {
      console.error("Failed to check subscription:", error);
    }
  }

  /**
   * Request notification permission and subscribe
   */
  async subscribe() {
    try {
      // Check if the page is served over HTTPS or localhost
      const isSecureContext =
        window.location.protocol === "https:" ||
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1";

      if (!isSecureContext) {
        throw new Error(
          "Push notifications require HTTPS. Please access the site over a secure connection.",
        );
      }

      // Request permission
      const permission = await Notification.requestPermission();

      if (permission !== "granted") {
        throw new Error("Notification permission denied");
      }

      // Subscribe to push notifications
      const subscription = await this.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlBase64ToUint8Array(this.vapidPublicKey),
      });

      this.subscription = subscription;
      this.isSubscribed = true;

      // Send subscription to server
      await this.sendSubscriptionToServer(subscription);

      console.log("Successfully subscribed to push notifications");
      return true;
    } catch (error) {
      console.error("Failed to subscribe:", error);
      throw error;
    }
  }

  /**
   * Unsubscribe from push notifications
   */
  async unsubscribe() {
    try {
      if (!this.subscription) {
        throw new Error("No active subscription");
      }

      const result = await this.subscription.unsubscribe();
      this.isSubscribed = false;
      this.subscription = null;

      // Notify server
      await this.sendUnsubscriptionToServer();

      console.log("Successfully unsubscribed from push notifications");
      return result;
    } catch (error) {
      console.error("Failed to unsubscribe:", error);
      throw error;
    }
  }

  /**
   * Send subscription to server
   */
  async sendSubscriptionToServer(subscription) {
    try {
      const response = await fetch("/api/notification/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          endpoint: subscription.endpoint,
          p256dh: this.arrayBufferToBase64(subscription.getKey("p256dh")),
          auth: this.arrayBufferToBase64(subscription.getKey("auth")),
          userAgent: navigator.userAgent,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.message || "Failed to save subscription");
      }

      return data;
    } catch (error) {
      console.error("Failed to send subscription to server:", error);
      throw error;
    }
  }

  /**
   * Send unsubscription to server
   */
  async sendUnsubscriptionToServer() {
    try {
      const response = await fetch("/api/notification/unsubscribe-push", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          endpoint: this.subscription.endpoint,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.message || "Failed to remove subscription");
      }

      return data;
    } catch (error) {
      console.error("Failed to send unsubscription to server:", error);
      throw error;
    }
  }

  /**
   * Show notification (for testing)
   */
  showNotification(title, body, icon = "/static/img/logo.png") {
    if (this.registration) {
      this.registration.showNotification(title, {
        body: body,
        icon: icon,
        badge: "/static/img/badge.png",
      });
    }
  }

  /**
   * Utility: Convert VAPID key
   */
  urlBase64ToUint8Array(base64String) {
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
   * Utility: Convert ArrayBuffer to base64
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
   * Get subscription status
   */
  getStatus() {
    return {
      isSubscribed: this.isSubscribed,
      hasPermission: Notification.permission === "granted",
      subscription: this.subscription,
    };
  }
}

// Global instance
const notificationService = new NotificationService();

// Export for use in other scripts
window.NotificationService = NotificationService;
window.notificationService = notificationService;
