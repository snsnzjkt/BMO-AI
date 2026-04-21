jest.mock('../services/intentRouter');
jest.mock('../pipelines/chatPipeline');

const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline } = require('../pipelines/chatPipeline');
const request = require('supertest');
const express = require('express');
const chatRoute = require('../routes/chat');

const app = express();
app.use(express.json());
app.use('/chat', chatRoute);

describe('POST /chat', () => {
  afterEach(() => jest.resetAllMocks());

  it('returns 400 when text field is missing', async () => {
    const res = await request(app).post('/chat').send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('BMO needs something to think about!');
  });

  it('returns 400 when text is an empty string', async () => {
    const res = await request(app).post('/chat').send({ text: '   ' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('BMO needs something to think about!');
  });

  it('returns text, intent, and model on success', async () => {
    classifyIntent.mockResolvedValue('chat');
    runChatPipeline.mockResolvedValue('Beep boop! I am BMO.');

    const res = await request(app).post('/chat').send({ text: 'Hello BMO!' });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      text: 'Beep boop! I am BMO.',
      intent: 'chat',
      model: 'gemma3',
    });
  });

  it('returns 503 when intentRouter throws (Ollama unreachable)', async () => {
    classifyIntent.mockRejectedValue(new Error('ECONNREFUSED'));

    const res = await request(app).post('/chat').send({ text: 'Hello' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("BMO's brain is sleeping... try again!");
  });

  it('returns 503 when chatPipeline throws', async () => {
    classifyIntent.mockResolvedValue('chat');
    runChatPipeline.mockRejectedValue(new Error('timeout'));

    const res = await request(app).post('/chat').send({ text: 'Hello' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("BMO's brain is sleeping... try again!");
  });
});
