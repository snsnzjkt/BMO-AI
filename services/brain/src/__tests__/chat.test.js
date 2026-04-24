jest.mock('../services/intentRouter');
jest.mock('../pipelines/chatPipeline');

const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline, streamChatPipeline } = require('../pipelines/chatPipeline');
const request = require('supertest');
const express = require('express');
const chatRoute = require('../routes/chat');

const app = express();
app.use(express.json());
app.use('/chat', chatRoute);

describe('POST /chat', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    jest.resetAllMocks();
  });

  it('returns 400 when text field is missing', async () => {
    const res = await request(app).post('/chat').send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Beemo needs something to think about!');
  });

  it('returns 400 when text is an empty string', async () => {
    const res = await request(app).post('/chat').send({ text: '   ' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Beemo needs something to think about!');
  });

  it('returns 400 when text is a non-string truthy value', async () => {
    const res = await request(app).post('/chat').send({ text: 42 });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Beemo needs something to think about!');
  });

  it('returns text, intent, and model on success and calls pipelines with the original text', async () => {
    classifyIntent.mockResolvedValue('chat');
    runChatPipeline.mockResolvedValue('Beep boop! I am Beemo.');

    const res = await request(app).post('/chat').send({ text: 'Hello Beemo!' });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      text: 'Beep boop! I am Beemo.',
      intent: 'chat',
      model: 'gemma3',
    });
    expect(classifyIntent).toHaveBeenCalledWith('Hello Beemo!');
    expect(runChatPipeline).toHaveBeenCalledWith('Hello Beemo!');
  });

  it('falls back to chat pipeline for unregistered intents', async () => {
    classifyIntent.mockResolvedValue('camera');
    runChatPipeline.mockResolvedValue('Beemo looks around...');

    const res = await request(app).post('/chat').send({ text: 'take a picture' });

    expect(res.status).toBe(200);
    expect(res.body.intent).toBe('camera');
    expect(runChatPipeline).toHaveBeenCalledWith('take a picture');
  });

  it('returns 503 when intentRouter throws (Ollama unreachable)', async () => {
    classifyIntent.mockRejectedValue(new Error('ECONNREFUSED'));

    const res = await request(app).post('/chat').send({ text: 'Hello' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("Beemo's brain is sleeping... try again!");
    expect(consoleErrorSpy).toHaveBeenCalledWith('[chat route] pipeline error:', expect.any(Error));
  });

  it('returns 503 when chatPipeline throws', async () => {
    classifyIntent.mockResolvedValue('chat');
    runChatPipeline.mockRejectedValue(new Error('timeout'));

    const res = await request(app).post('/chat').send({ text: 'Hello' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("Beemo's brain is sleeping... try again!");
    expect(consoleErrorSpy).toHaveBeenCalledWith('[chat route] pipeline error:', expect.any(Error));
  });
});

describe('POST /chat/stream', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    jest.resetAllMocks();
  });

  it('returns 400 when text field is missing', async () => {
    const res = await request(app).post('/chat/stream').send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Beemo needs something to think about!');
  });

  it('returns 400 when text is empty string', async () => {
    const res = await request(app).post('/chat/stream').send({ text: '   ' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Beemo needs something to think about!');
  });

  it('streams sentences as NDJSON and ends with done:true', async () => {
    streamChatPipeline.mockImplementation(async function* () {
      yield 'Hello!';
      yield 'How are you?';
    });

    const res = await request(app)
      .post('/chat/stream')
      .send({ text: 'Hi there' })
      .buffer(true)
      .parse((res, fn) => {
        let data = '';
        res.on('data', chunk => { data += chunk.toString(); });
        res.on('end', () => fn(null, data));
      });

    const lines = res.body.split('\n').filter(Boolean).map(JSON.parse);
    expect(lines).toEqual([
      { sentence: 'Hello!' },
      { sentence: 'How are you?' },
      { done: true },
    ]);
  });

  it('returns 503 JSON when streamChatPipeline throws before first write', async () => {
    streamChatPipeline.mockImplementation(async function* () {
      throw new Error('Ollama down');
      yield; // make it an async generator
    });

    const res = await request(app)
      .post('/chat/stream')
      .send({ text: 'Hi' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("Beemo's brain is sleeping... try again!");
    expect(consoleErrorSpy).toHaveBeenCalledWith('[chat/stream] pipeline error:', expect.any(Error));
  });
});
