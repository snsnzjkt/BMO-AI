const BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
const GENERATION_OPTIONS = { num_predict: 80, temperature: 0.7 };

async function generate(model, prompt, system = '') {
  const response = await fetch(`${BASE_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, prompt, system, stream: false, options: GENERATION_OPTIONS }),
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status}`);
  }

  const data = await response.json();
  if (data.response === undefined) {
    throw new Error('Ollama response missing "response" field');
  }
  return data.response;
}

async function chat(model, messages) {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages, stream: false, options: GENERATION_OPTIONS }),
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status}`);
  }

  const data = await response.json();
  if (!data.message?.content) {
    throw new Error('Ollama response missing "message.content" field');
  }
  return data.message.content;
}

module.exports = { generate, chat };
