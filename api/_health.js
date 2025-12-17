export default function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  res.status(200).type('text/plain').send('ok');
}
