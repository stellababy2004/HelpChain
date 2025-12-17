export default function handler(req, res) {
  try {
    res.statusCode = 200;
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.end('ok');
  } catch (e) {
    // Always return a safe 200 even if something unexpected happens
    try {
      res.statusCode = 200;
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      res.setHeader('Cache-Control', 'no-store');
      res.end('ok');
    } catch (_) {}
  }
}
