const { Router } = require('express');
const store = require('../state');

const router = Router();

router.post('/', (req, res) => {
  const { state } = req.body ?? {};
  if (!state || typeof state !== 'string') {
    return res.status(400).json({ error: 'state must be a non-empty string' });
  }
  store.setState(state);
  res.sendStatus(204);
});

router.get('/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.flushHeaders();

  res.write(`data: ${JSON.stringify({ state: store.currentState })}\n\n`);
  store.clients.push(res);

  req.on('close', () => {
    const i = store.clients.indexOf(res);
    if (i !== -1) store.clients.splice(i, 1);
  });
});

module.exports = router;
