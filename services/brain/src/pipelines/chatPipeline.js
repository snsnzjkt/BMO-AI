const path = require('path');
const fs = require('fs');
const { generate } = require('../services/ollamaClient');

const SYSTEM_PROMPT_PATH = path.resolve(
  __dirname,
  '../../../../packages/prompts/systemPrompt.txt'
);

const FALLBACK_PROMPT = 'You are Beemo, a cheerful and playful AI assistant.';

function loadSystemPrompt() {
  try {
    return fs.readFileSync(SYSTEM_PROMPT_PATH, 'utf8').trim();
  } catch {
    return FALLBACK_PROMPT;
  }
}

async function runChatPipeline(text) {
  const system = loadSystemPrompt();
  return generate(process.env.LLM_MODEL || 'gemma3', text, system);
}

module.exports = { runChatPipeline };
