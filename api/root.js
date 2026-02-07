module.exports = function (req, res) {
  try {
    const body = [
      '<!doctype html>\n',
      '<html lang="bg">\n',
      '<head><meta charset="UTF-8"/>',
      '<meta name="viewport" content="width=device-width, initial-scale=1.0"/>',
      '<title>HelpChain Preview</title>',
      '<style>body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:0;padding:24px} .wrap{max-width:760px;margin:0 auto} a{color:#4f46e5;text-decoration:none} a:hover{text-decoration:underline} .ok{color:#16a34a} .muted{color:#6b7280} .card{border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;margin:12px 0}</style>',
      '</head>\n',
      '<body><div class="wrap">',
      '<h1>HelpChain Preview</h1>',
      '<p class="muted">Лек статичен начален екран за прегледите (Vercel Preview).</p>',
      '<div class="card"><h3>Бързи връзки</h3><ul>',
      '<li><a href="/health">/health</a></li>',
      '<li><a href="/api/_health">/api/_health</a></li>',
      '<li><a href="/api/analytics">/api/analytics</a></li>',
      '</ul></div>',
      '<p class="muted">Ако сте виждали 500 тук, това го елиминира за прегледите. Истинският UI се сервира от Python рутовете.</p>',
      '</div></body></html>'
    ].join('');
    res.statusCode = 200;
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Content-Length', Buffer.byteLength(body).toString());
    res.end(body);
  } catch (e) {
    try {
      res.statusCode = 200;
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      res.setHeader('Cache-Control', 'no-store');
      res.end('ok');
    } catch (_) {}
  }
}
