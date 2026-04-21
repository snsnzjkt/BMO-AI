jest.mock('../services/ollamaClient');
jest.mock('fs');

const { generate } = require('../services/ollamaClient');
const fs = require('fs');
const { runChatPipeline } = require('../pipelines/chatPipeline');

describe('chatPipeline.runChatPipeline', () => {
  afterEach(() => jest.resetAllMocks());

  it('returns Gemma response using the system prompt from file', async () => {
    fs.readFileSync.mockReturnValue('You are BMO!');
    generate.mockResolvedValue('Beep boop, hello friend!');

    const result = await runChatPipeline('Hello!');

    expect(result).toBe('Beep boop, hello friend!');
    expect(generate).toHaveBeenCalledWith(
      expect.any(String),
      'Hello!',
      'You are BMO!'
    );
  });

  it('trims whitespace from the system prompt file content', async () => {
    fs.readFileSync.mockReturnValue('   You are BMO!   \n');
    generate.mockResolvedValue('Hi!');

    await runChatPipeline('Hey');

    expect(generate).toHaveBeenCalledWith(expect.any(String), 'Hey', 'You are BMO!');
  });

  it('falls back to a default prompt when the system prompt file is unreadable', async () => {
    fs.readFileSync.mockImplementation(() => { throw new Error('ENOENT'); });
    generate.mockResolvedValue('Hi there!');

    const result = await runChatPipeline('Hello!');

    expect(result).toBe('Hi there!');
    expect(generate).toHaveBeenCalledWith(
      expect.any(String),
      'Hello!',
      'You are BMO, a cheerful and playful AI assistant.'
    );
  });
});
