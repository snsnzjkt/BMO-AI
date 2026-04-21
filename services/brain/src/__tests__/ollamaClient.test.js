const { generate } = require('../services/ollamaClient');

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
      json: async () => ({ response: 'Hello from BMO!' }),
    });

    const result = await generate('gemma3', 'say hello', 'you are BMO');

    expect(result).toBe('Hello from BMO!');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/generate',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gemma3',
          prompt: 'say hello',
          system: 'you are BMO',
          stream: false,
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
        body: JSON.stringify({ model: 'gemma3', prompt: 'hello', system: '', stream: false }),
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
