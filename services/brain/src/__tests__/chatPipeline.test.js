jest.mock('../services/ollamaClient');

const { generate } = require('../services/ollamaClient');
const fs = require('fs');
const { runChatPipeline } = require('../pipelines/chatPipeline');

describe('chatPipeline.runChatPipeline', () => {
  let readFileSyncSpy;

  beforeEach(() => {
    readFileSyncSpy = jest.spyOn(fs, 'readFileSync');
  });

  afterEach(() => {
    readFileSyncSpy.mockRestore();
    jest.resetAllMocks();
  });

  it('returns Gemma response using the system prompt from file', async () => {
    readFileSyncSpy.mockReturnValue('You are BMO!');
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
    readFileSyncSpy.mockReturnValue('   You are BMO!   \n');
    generate.mockResolvedValue('Hi!');

    await runChatPipeline('Hey');

    expect(generate).toHaveBeenCalledWith(expect.any(String), 'Hey', 'You are BMO!');
  });

  it('falls back to a default prompt when the system prompt file is unreadable', async () => {
    readFileSyncSpy.mockImplementation(() => { throw new Error('ENOENT'); });
    generate.mockResolvedValue('Hi there!');

    const result = await runChatPipeline('Hello!');

    expect(result).toBe('Hi there!');
    expect(generate).toHaveBeenCalledWith(
      expect.any(String),
      'Hello!',
      'You are BMO, a cheerful and playful AI assistant.'
    );
  });

  it('propagates errors from generate without catching them', async () => {
    readFileSyncSpy.mockReturnValue('You are BMO!');
    generate.mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(runChatPipeline('Hello!')).rejects.toThrow('ECONNREFUSED');
  });
});
