jest.mock('../services/ollamaClient');

const { chat } = require('../services/ollamaClient');
const fs = require('fs');
const chatPipeline = require('../pipelines/chatPipeline');

describe('chatPipeline.runChatPipeline', () => {
  let readFileSyncSpy;

  beforeEach(() => {
    jest.resetAllMocks();
    readFileSyncSpy = jest.spyOn(fs, 'readFileSync');
    chatPipeline._resetHistory();
  });

  afterEach(() => {
    readFileSyncSpy.mockRestore();
  });

  it('returns Ollama response using the system prompt from file', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValue('Beep boop, hello friend!');

    const result = await chatPipeline.runChatPipeline('Hello!');

    expect(result).toBe('Beep boop, hello friend!');
    expect(chat).toHaveBeenCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'Hello!' },
      ]
    );
  });

  it('trims whitespace from the system prompt file content', async () => {
    readFileSyncSpy.mockReturnValue('   You are Beemo!   \n');
    chat.mockResolvedValue('Hi!');

    await chatPipeline.runChatPipeline('Hey');

    expect(chat).toHaveBeenCalledWith(
      expect.any(String),
      expect.arrayContaining([{ role: 'system', content: 'You are Beemo!' }])
    );
  });

  it('falls back to a default prompt when the system prompt file is unreadable', async () => {
    readFileSyncSpy.mockImplementation(() => { throw new Error('ENOENT'); });
    chat.mockResolvedValue('Hi there!');

    const result = await chatPipeline.runChatPipeline('Hello!');

    expect(result).toBe('Hi there!');
    expect(chat).toHaveBeenCalledWith(
      expect.any(String),
      expect.arrayContaining([
        { role: 'system', content: 'You are Beemo, a cheerful and playful AI assistant.' },
      ])
    );
  });

  it('propagates errors from chat without catching them', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(chatPipeline.runChatPipeline('Hello!')).rejects.toThrow('ECONNREFUSED');
  });

  it('accumulates conversation history across calls', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValueOnce('Hi there!').mockResolvedValueOnce('Good, thanks!');

    await chatPipeline.runChatPipeline('Hello!');
    await chatPipeline.runChatPipeline('How are you?');

    expect(chat).toHaveBeenLastCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'Hello!' },
        { role: 'assistant', content: 'Hi there!' },
        { role: 'user', content: 'How are you?' },
      ]
    );
  });

  it('caps history at 20 messages by dropping the oldest when over limit', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValue('ok');

    for (let i = 0; i < 10; i++) {
      await chatPipeline.runChatPipeline(`message ${i}`);
    }

    await chatPipeline.runChatPipeline('message 10');

    const calledMessages = chat.mock.calls[chat.mock.calls.length - 1][1];
    expect(calledMessages.length).toBe(21); // system + 20 history entries
    expect(calledMessages[0].role).toBe('system');
    expect(calledMessages.find(m => m.role === 'user' && m.content === 'message 0')).toBeUndefined();
    expect(calledMessages[calledMessages.length - 1]).toEqual({ role: 'user', content: 'message 10' });
  });

  it('does not store history when chat throws', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockRejectedValueOnce(new Error('network error'));
    chat.mockResolvedValueOnce('success');

    await chatPipeline.runChatPipeline('failed message').catch(() => {});
    await chatPipeline.runChatPipeline('second message');

    expect(chat).toHaveBeenLastCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'second message' },
      ]
    );
  });

  it('_resetHistory clears stored conversation', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValue('hi');

    await chatPipeline.runChatPipeline('hello');
    chatPipeline._resetHistory();

    chat.mockResolvedValue('fresh start');
    await chatPipeline.runChatPipeline('new message');

    expect(chat).toHaveBeenLastCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'new message' },
      ]
    );
  });
});
