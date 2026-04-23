const { Router } = require('express');
const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline } = require('../pipelines/chatPipeline');

const router = Router();

// Maps intent labels to pipeline functions.
// Phase 2+: register new pipelines here alongside their route files.
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

module.exports = router;
