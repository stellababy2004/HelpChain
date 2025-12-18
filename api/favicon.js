module.exports = function (req, res) {
  try {
    // Return a tiny 1x1 transparent PNG for any favicon.* requests.
    // Keeps things simple and avoids hitting Python for assets.
    const pngBase64 =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAuMB9D7rWqkAAAAASUVORK5CYII=";
    const buf = Buffer.from(pngBase64, 'base64');
    res.statusCode = 200;
    res.setHeader('Content-Type', 'image/png');
    res.setHeader('Cache-Control', 'public, max-age=3600');
    res.setHeader('Content-Length', Buffer.byteLength(buf).toString());
    res.end(buf);
  } catch (e) {
    try {
      res.statusCode = 204;
      res.setHeader('Cache-Control', 'no-store');
      res.end();
    } catch (_) {}
  }
}
