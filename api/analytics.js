module.exports = function (req, res) {
  try {
    const body = JSON.stringify({ status: 'ok', source: 'api-node' });
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Length', Buffer.byteLength(body).toString());
    res.end(body);
  } catch (e) {
    try {
      const body = JSON.stringify({ status: 'ok' });
      res.statusCode = 200;
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.setHeader('Cache-Control', 'no-store');
      res.setHeader('Content-Length', Buffer.byteLength(body).toString());
      res.end(body);
    } catch (_) {}
  }
}
