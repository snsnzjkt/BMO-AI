const { generate, chat, chatStream } = require('../services/ollamaClient');

describe('ollamaClient.generate', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
    delete global.fetch;
  });

  it('sends a POST request to Ollama and returns response text', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'Hello from Beemo!' }),
    });

    const result = await generate('gemma3', 'say hello', 'you are Beemo');

    expect(result).toBe('Hello from Beemo!');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/generate',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gemma3',
          prompt: 'say hello',
          system: 'you are Beemo',
          stream: false,
          options: { num_predict: 80, temperature: 0.7 },
        }),
      })
    );
  });

  it('defaults system to empty string when omitted', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'ok' }),
    });

    await generate('gemma3', 'hello');

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({ model: 'gemma3', prompt: 'hello', system: '', stream: false, options: { num_predict: 80, temperature: 0.7 } }),
      })
    );
  });

  it('throws when Ollama returns a non-ok HTTP status', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 500 });

    await expect(generate('gemma3', 'hello')).rejects.toThrow(
      'Ollama request failed: 500'
    );
  });

  it('throws when fetch rejects (Ollama unreachable)', async () => {
    global.fetch.mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(generate('gemma3', 'hello')).rejects.toThrow('ECONNREFUSED');
  });
});

describe('ollamaClient.chat', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
    delete global.fetch;
  });

  it('sends messages to /api/chat and returns message content', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: { content: 'Hello from Beemo!' } }),
    });

    const messages = [
      { role: 'system', content: 'You are Beemo.' },
      { role: 'user', content: 'hello' },
    ];

    const result = await chat('gemma3', messages);

    expect(result).toBe('Hello from Beemo!');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/chat',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gemma3',
          messages,
          stream: false,
          options: { num_predict: 80, temperature: 0.7 },
        }),
      })
    );
  });

  it('throws when Ollama returns a non-ok status', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 503 });
    await expect(chat('gemma3', [])).rejects.toThrow('Ollama request failed: 503');
  });

  it('throws when response is missing message.content', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: {} }),
    });
    await expect(chat('gemma3', [])).rejects.toThrow('missing "message.content"');
  });

  it('throws when response has an empty content string', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: { content: '' } }),
    });
    await expect(chat('gemma3', [])).rejects.toThrow('missing "message.content"');
  });

  it('throws when fetch rejects (Ollama unreachable)', async () => {
    global.fetch.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(chat('gemma3', [])).rejects.toThrow('ECONNREFUSED');
  });
});

describe('ollamaClient.chatStream', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
    delete global.fetch;
  });

  function makeReader(lines) {
    const encoder = new TextEncoder();
    const chunks = lines.map(l => encoder.encode(l + '\n'));
    let i = 0;
    return {
      read: jest.fn().mockImplementation(async () => {
        if (i < chunks.length) return { done: false, value: chunks[i++] };
        return { done: true, value: undefined };
      }),
    };
  }

  it('yields token content from Ollama streaming response', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      body: {
        getReader: () => makeReader([
          JSON.stringify({ message: { content: 'Hello' }, done: false }),
          JSON.stringify({ message: { content: ' world' }, done: false }),
          JSON.stringify({ message: { content: '' }, done: true }),
        ]),
      },
    });

    const tokens = [];
    for await (const token of chatStream('gemma3', [])) {
      tokens.push(token);
    }

    expect(tokens).toEqual(['Hello', ' world']);
  });

  it('stops yielding at done:true even if more lines follow', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      body: {
        getReader: () => makeReader([
          JSON.stringify({ message: { content: 'Hi' }, done: false }),
          JSON.stringify({ message: { content: '' }, done: true }),
          JSON.stringify({ message: { content: 'after done' }, done: false }),
        ]),
      },
    });

    const tokens = [];
    for await (const token of chatStream('gemma3', [])) {
      tokens.push(token);
    }

    expect(tokens).toEqual(['Hi']);
  });

  it('throws when Ollama returns a non-ok status', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 503 });

    const gen = chatStream('gemma3', []);
    await expect(gen.next()).rejects.toThrow('Ollama request failed: 503');
  });

  it('calls /api/chat with stream:true and shared options', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      body: { getReader: () => makeReader([JSON.stringify({ message: { content: '' }, done: true })]) },
    });

    const msgs = [{ role: 'user', content: 'hi' }];
    for await (const _ of chatStream('gemma3', msgs)) { /* drain */ }

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/chat',
      expect.objectContaining({
        body: JSON.stringify({
          model: 'gemma3',
          messages: msgs,
          stream: true,
          options: { num_predict: 80, temperature: 0.7 },
        }),
      })
    );
  });
});
