/**
 * HelpChain Video Chat JavaScript
 * WebRTC implementation for peer-to-peer video communication
 */

class VideoChatManager {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.peerConnection = null;
    this.localStream = null;
    this.remoteStream = null;
    this.isInitiator = false;
    this.isConnected = false;

    // DOM elements
    this.localVideo = document.getElementById("localVideo");
    this.remoteVideo = document.getElementById("remoteVideo");
    this.startButton = document.getElementById("startVideo");
    this.endButton = document.getElementById("endVideo");
    this.muteButton = document.getElementById("muteAudio");
    this.hideButton = document.getElementById("hideVideo");
    this.statusDiv = document.getElementById("videoStatus");

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.updateStatus("Готов за видео чат");
  }

  setupEventListeners() {
    if (this.startButton) {
      this.startButton.addEventListener("click", () => this.startVideo());
    }
    if (this.endButton) {
      this.endButton.addEventListener("click", () => this.endVideo());
    }
    if (this.muteButton) {
      this.muteButton.addEventListener("click", () => this.toggleMute());
    }
    if (this.hideButton) {
      this.hideButton.addEventListener("click", () => this.toggleVideo());
    }
  }

  async startVideo() {
    try {
      this.updateStatus("Започване на видео...");

      // Get user media
      this.localStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });

      // Display local video
      if (this.localVideo) {
        this.localVideo.srcObject = this.localStream;
      }

      // Initialize peer connection
      this.initializePeerConnection();

      this.updateStatus("Видео стартирано. Изчакване на връзка...");
    } catch (error) {
      console.error("Error starting video:", error);
      this.updateStatus("Грешка при стартиране на видео: " + error.message);
    }
  }

  initializePeerConnection() {
    // Create RTCPeerConnection with STUN servers
    const configuration = {
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        { urls: "stun:stun1.l.google.com:19302" },
      ],
    };

    this.peerConnection = new RTCPeerConnection(configuration);

    // Add local stream tracks to peer connection
    this.localStream.getTracks().forEach((track) => {
      this.peerConnection.addTrack(track, this.localStream);
    });

    // Handle remote stream
    this.peerConnection.ontrack = (event) => {
      if (this.remoteVideo && !this.remoteVideo.srcObject) {
        this.remoteVideo.srcObject = event.streams[0];
        this.remoteStream = event.streams[0];
        this.updateStatus("Свързан! Видео чат активен.");
        this.isConnected = true;
      }
    };

    // Handle ICE candidates
    this.peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignalingMessage({
          type: "ice-candidate",
          candidate: event.candidate,
        });
      }
    };

    // Handle connection state changes
    this.peerConnection.onconnectionstatechange = () => {
      console.log("Connection state:", this.peerConnection.connectionState);
      if (this.peerConnection.connectionState === "connected") {
        this.isConnected = true;
        this.updateStatus("Свързан! Видео чат активен.");
      } else if (
        this.peerConnection.connectionState === "disconnected" ||
        this.peerConnection.connectionState === "failed"
      ) {
        this.isConnected = false;
        this.updateStatus("Връзката е прекъсната.");
      }
    };
  }

  async createOffer() {
    try {
      const offer = await this.peerConnection.createOffer();
      await this.peerConnection.setLocalDescription(offer);

      this.sendSignalingMessage({
        type: "offer",
        offer: offer,
      });

      this.isInitiator = true;
    } catch (error) {
      console.error("Error creating offer:", error);
      this.updateStatus("Грешка при създаване на оферта: " + error.message);
    }
  }

  async handleOffer(offer) {
    try {
      await this.peerConnection.setRemoteDescription(
        new RTCSessionDescription(offer),
      );

      const answer = await this.peerConnection.createAnswer();
      await this.peerConnection.setLocalDescription(answer);

      this.sendSignalingMessage({
        type: "answer",
        answer: answer,
      });
    } catch (error) {
      console.error("Error handling offer:", error);
      this.updateStatus("Грешка при обработка на оферта: " + error.message);
    }
  }

  async handleAnswer(answer) {
    try {
      await this.peerConnection.setRemoteDescription(
        new RTCSessionDescription(answer),
      );
    } catch (error) {
      console.error("Error handling answer:", error);
      this.updateStatus("Грешка при обработка на отговор: " + error.message);
    }
  }

  async handleIceCandidate(candidate) {
    try {
      await this.peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (error) {
      console.error("Error handling ICE candidate:", error);
    }
  }

  sendSignalingMessage(message) {
    // Send signaling message via HTTP POST to our signaling endpoint
    fetch(`/api/video_chat/signal/${this.sessionId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(message),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Signaling message sent:", data);
      })
      .catch((error) => {
        console.error("Error sending signaling message:", error);
      });
  }

  endVideo() {
    // Stop all tracks
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => track.stop());
    }
    if (this.remoteStream) {
      this.remoteStream.getTracks().forEach((track) => track.stop());
    }

    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close();
    }

    // Clear video elements
    if (this.localVideo) {
      this.localVideo.srcObject = null;
    }
    if (this.remoteVideo) {
      this.remoteVideo.srcObject = null;
    }

    this.isConnected = false;
    this.updateStatus("Видео чат завършен.");

    // Redirect to video chat main page after a short delay
    setTimeout(() => {
      window.location.href = "/video_chat";
    }, 2000);
  }

  toggleMute() {
    if (this.localStream) {
      const audioTrack = this.localStream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        this.updateMuteButton(audioTrack.enabled);
      }
    }
  }

  toggleVideo() {
    if (this.localStream) {
      const videoTrack = this.localStream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
        this.updateVideoButton(videoTrack.enabled);
      }
    }
  }

  updateMuteButton(enabled) {
    if (this.muteButton) {
      if (enabled) {
        this.muteButton.innerHTML = '<i class="fas fa-microphone"></i> Заглуши';
        this.muteButton.classList.remove("btn-danger");
        this.muteButton.classList.add("btn-secondary");
      } else {
        this.muteButton.innerHTML =
          '<i class="fas fa-microphone-slash"></i> Включи звук';
        this.muteButton.classList.remove("btn-secondary");
        this.muteButton.classList.add("btn-danger");
      }
    }
  }

  updateVideoButton(enabled) {
    if (this.hideButton) {
      if (enabled) {
        this.hideButton.innerHTML = '<i class="fas fa-video"></i> Скрий видео';
        this.hideButton.classList.remove("btn-danger");
        this.hideButton.classList.add("btn-secondary");
      } else {
        this.hideButton.innerHTML =
          '<i class="fas fa-video-slash"></i> Покажи видео';
        this.hideButton.classList.remove("btn-secondary");
        this.hideButton.classList.add("btn-danger");
      }
    }
  }

  updateStatus(message) {
    if (this.statusDiv) {
      this.statusDiv.textContent = message;
    }
    console.log("Video chat status:", message);
  }
}

// Initialize video chat when page loads
document.addEventListener("DOMContentLoaded", function () {
  // Get session ID from URL or data attribute
  const sessionId =
    document.body.dataset.sessionId ||
    window.location.pathname.split("/").pop();

  if (sessionId && sessionId !== "video_chat") {
    window.videoChatManager = new VideoChatManager(sessionId);
  }
});
