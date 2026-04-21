jest.mock('../services/ollamaClient');

const { generate } = require('../services/ollamaClient');
const { classifyIntent } = require('../services/intentRouter');

describe('intentRouter.classifyIntent', () => {
  afterEach(() => jest.resetAllMocks());

  it('returns intent when Gemma responds with a valid label', async () => {
    generate.mockResolvedValue('vision');
    const intent = await classifyIntent('what do you see in this image?');
    expect(intent).toBe('vision');
  });

  it('strips whitespace and lowercases before validating', async () => {
    generate.mockResolvedValue('  RAG  \n');
    const intent = await classifyIntent('search my notes for recipes');
    expect(intent).toBe('rag');
  });

  it('falls back to chat for unrecognized Gemma responses', async () => {
    generate.mockResolvedValue('something completely unexpected');
    const intent = await classifyIntent('hello there');
    expect(intent).toBe('chat');
  });

  it('passes a prompt containing the user text and all valid intent labels', async () => {
    generate.mockResolvedValue('chat');
    await classifyIntent('tell me a joke');
    const calledPrompt = generate.mock.calls[0][1];
    expect(calledPrompt).toContain('tell me a joke');
    for (const label of ['chat', 'rag', 'vision', 'camera', 'web']) {
      expect(calledPrompt).toContain(label);
    }
  });

  it('propagates errors from generate (Ollama unreachable)', async () => {
    generate.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(classifyIntent('hello')).rejects.toThrow('ECONNREFUSED');
  });
});
