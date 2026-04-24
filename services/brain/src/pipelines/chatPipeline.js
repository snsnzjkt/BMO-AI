const path = require('path');
const fs = require('fs');
const { chat, chatStream } = require('../services/ollamaClient');

const SYSTEM_PROMPT_PATH = path.resolve(
  __dirname,
  '../../../../packages/prompts/systemPrompt.txt'
);

const FALLBACK_PROMPT = 'You are Beemo, a cheerful and playful AI assistant.';
const MAX_HISTORY = 20;

let messages = [];

function loadSystemPrompt() {
  try {
    return fs.readFileSync(SYSTEM_PROMPT_PATH, 'utf8').trim();
  } catch {
    return FALLBACK_PROMPT;
  }
}

const SYSTEM_PROMPT = loadSystemPrompt();

async function runChatPipeline(text) {
  const candidate = [...messages, { role: 'user', content: text }];
  const trimmed = candidate.length > MAX_HISTORY ? candidate.slice(-MAX_HISTORY) : candidate;
  const fullMessages = [{ role: 'system', content: SYSTEM_PROMPT }, ...trimmed];

  const response = await chat(process.env.LLM_MODEL || 'gemma3', fullMessages);

  messages = [...trimmed, { role: 'assistant', content: response }];
  return response;
}

async function* streamChatPipeline(text) {
  const candidate = [...messages, { role: 'user', content: text }];
  const trimmed = candidate.length > MAX_HISTORY ? candidate.slice(-MAX_HISTORY) : candidate;
  const fullMessages = [{ role: 'system', content: SYSTEM_PROMPT }, ...trimmed];

  let tokenBuffer = '';
  const sentences = [];

  for await (const token of chatStream(process.env.LLM_MODEL || 'gemma3', fullMessages)) {
    tokenBuffer += token;
    const match = tokenBuffer.match(/^(.*?[.!?])\s+([\s\S]*)$/);
    if (match) {
      const sentence = match[1].trim();
      sentences.push(sentence);
      tokenBuffer = match[2];
      yield sentence;
    }
  }

  if (tokenBuffer.trim()) {
    sentences.push(tokenBuffer.trim());
    yield tokenBuffer.trim();
  }

  if (sentences.length > 0) {
    const fullResponse = sentences.join(' ');
    messages = [...trimmed, { role: 'assistant', content: fullResponse }];
  }
}

function _resetHistory() {
  messages = [];
}

module.exports = { runChatPipeline, streamChatPipeline, _resetHistory };
