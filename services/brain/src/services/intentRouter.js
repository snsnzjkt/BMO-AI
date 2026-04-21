const { generate } = require('./ollamaClient');

const VALID_INTENTS = ['chat', 'rag', 'vision', 'camera', 'web'];

function buildClassificationPrompt(text) {
  const labels = VALID_INTENTS.join(', ');
  return (
    `Classify the following message into exactly one of: ${labels}.\n` +
    `Reply with only that single word — no punctuation, no explanation.\n\n` +
    `Message: "${text}"`
  );
}

async function classifyIntent(text) {
  const raw = await generate(
    process.env.LLM_MODEL || 'gemma3',
    buildClassificationPrompt(text),
    ''
  );
  const intent = raw.trim().toLowerCase();
  return VALID_INTENTS.includes(intent) ? intent : 'chat';
}

module.exports = { classifyIntent };
