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

  it('passes a prompt that contains the user text', async () => {
    generate.mockResolvedValue('chat');
    await classifyIntent('tell me a joke');
    const calledPrompt = generate.mock.calls[0][1];
    expect(calledPrompt).toContain('tell me a joke');
  });
});
