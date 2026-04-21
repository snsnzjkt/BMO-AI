const { Router } = require('express');
const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline } = require('../pipelines/chatPipeline');

const router = Router();

router.post('/', async (req, res) => {
  const { text } = req.body;

  if (!text || typeof text !== 'string' || text.trim() === '') {
    return res.status(400).json({ error: 'BMO needs something to think about!' });
  }

  try {
    const intent = await classifyIntent(text);
    const responseText = await runChatPipeline(text);
    res.json({ text: responseText, intent, model: process.env.LLM_MODEL || 'gemma3' });
  } catch {
    res.status(503).json({ error: "BMO's brain is sleeping... try again!" });
  }
});

module.exports = router;
