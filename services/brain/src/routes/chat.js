const { Router } = require('express');
const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline, streamChatPipeline } = require('../pipelines/chatPipeline');

const router = Router();

const PIPELINES = {
  chat: runChatPipeline,
};

router.post('/', async (req, res) => {
  const { text } = req.body ?? {};

  if (!text || typeof text !== 'string' || text.trim() === '') {
    return res.status(400).json({ error: 'Beemo needs something to think about!' });
  }

  try {
    const intent = await classifyIntent(text);
    const pipeline = PIPELINES[intent] ?? runChatPipeline;
    const responseText = await pipeline(text);
    res.json({ text: responseText, intent, model: process.env.LLM_MODEL || 'gemma3' });
  } catch (err) {
    console.error('[chat route] pipeline error:', err);
    res.status(503).json({ error: "Beemo's brain is sleeping... try again!" });
  }
});

router.post('/stream', async (req, res) => {
  const { text } = req.body ?? {};

  if (!text || typeof text !== 'string' || text.trim() === '') {
    return res.status(400).json({ error: 'Beemo needs something to think about!' });
  }

  try {
    const generator = streamChatPipeline(text);
    res.setHeader('Content-Type', 'application/x-ndjson');
    res.setHeader('Transfer-Encoding', 'chunked');

    for await (const sentence of generator) {
      res.write(JSON.stringify({ sentence }) + '\n');
    }
    res.write(JSON.stringify({ done: true }) + '\n');
  } catch (err) {
    console.error('[chat/stream] pipeline error:', err);
    if (!res.headersSent) {
      res.removeHeader('Transfer-Encoding');
      res.removeHeader('Content-Type');
      return res.status(503).json({ error: "Beemo's brain is sleeping... try again!" });
    }
    res.write(JSON.stringify({ error: "Beemo's brain is sleeping... try again!" }) + '\n');
  }
  res.end();
});

module.exports = router;
