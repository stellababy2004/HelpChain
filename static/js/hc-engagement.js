(function () {
  "use strict";

  if (window.__HC_ENGAGEMENT_TRACKING__) {
    return;
  }

  window.__HC_ENGAGEMENT_TRACKING__ = true;

  var startedAt = Date.now();
  var maxScroll = 0;
  var sent = false;

  function send(eventType, payload) {
    try {
      var body = JSON.stringify({
        event: eventType,
        event_type: eventType,
        event_category: "engagement",
        event_action: "engagement",
        page_url: window.location.pathname,
        metadata: payload || {}
      });

      if (navigator.sendBeacon) {
        navigator.sendBeacon("/events", new Blob([body], {
          type: "application/json"
        }));
        return;
      }

      fetch("/events", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: body,
        keepalive: true
      }).catch(function () {});
    } catch (e) {}
  }

  function computeScrollDepth() {
    var scrollTop = window.scrollY || window.pageYOffset || 0;
    var docHeight = Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight
    );
    var winHeight = window.innerHeight || 1;

    var percent = Math.min(
      100,
      Math.round(((scrollTop + winHeight) / docHeight) * 100)
    );

    if (percent > maxScroll) {
      maxScroll = percent;
    }
  }

  window.addEventListener("scroll", computeScrollDepth, {
    passive: true
  });

  window.addEventListener("beforeunload", function () {
    if (sent) return;
    sent = true;

    var seconds = Math.round((Date.now() - startedAt) / 1000);

    var score = 0;

    if (seconds >= 10) score += 5;
    if (seconds >= 30) score += 10;
    if (seconds >= 60) score += 20;

    if (maxScroll >= 25) score += 5;
    if (maxScroll >= 50) score += 10;
    if (maxScroll >= 75) score += 20;

    var intent = "low";

    if (score >= 15) intent = "medium";
    if (score >= 35) intent = "high";
    if (score >= 55) intent = "very_high";

    send("page_engagement", {
      seconds_on_page: seconds,
      max_scroll_percent: maxScroll,
      page: window.location.pathname,
      engagement_score: score,
      engagement_intent: intent
    });
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "hidden") {
      return;
    }

    if (sent) return;
    sent = true;

    var seconds = Math.round((Date.now() - startedAt) / 1000);

    var score = 0;

    if (seconds >= 10) score += 5;
    if (seconds >= 30) score += 10;
    if (seconds >= 60) score += 20;

    if (maxScroll >= 25) score += 5;
    if (maxScroll >= 50) score += 10;
    if (maxScroll >= 75) score += 20;

    var intent = "low";

    if (score >= 15) intent = "medium";
    if (score >= 35) intent = "high";
    if (score >= 55) intent = "very_high";

    send("page_engagement", {
      seconds_on_page: seconds,
      max_scroll_percent: maxScroll,
      page: window.location.pathname,
      engagement_score: score,
      engagement_intent: intent
    });
  });
})();

