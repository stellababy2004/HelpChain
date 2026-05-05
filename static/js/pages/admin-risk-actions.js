console.log("RISK JS LOADED");

(function () {
  console.log("INIT STREAM");

  let es = null;

  function startStream() {
    if (es) {
      es.close();
    }

    es = new EventSource("/admin/api/stream");

    es.onopen = () => {
      console.log("STREAM OPEN");
    };

    es.onmessage = (event) => {
      if (!event.data) return;

      try {
        const data = JSON.parse(event.data);
        console.log("SSE EVENT:", data);

        if (data.type === "request_assigned") {
          console.log("UPDATE UI NEEDED");
          // тук ще вържем refresh логиката после
        }
      } catch (e) {
        console.log("PARSE ERROR", e);
      }
    };

    es.onerror = (err) => {
      console.log("STREAM ERROR", err);
      es.close();

      // auto reconnect след 2 сек
      setTimeout(startStream, 2000);
    };
  }

  startStream();

  window.addEventListener("beforeunload", () => {
    if (es) es.close();
  });
})();
