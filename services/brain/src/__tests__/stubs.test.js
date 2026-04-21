const request = require('supertest');
const express = require('express');
const visionRoute = require('../routes/vision');
const ragRoute = require('../routes/rag');

const app = express();
app.use(express.json());
app.use('/vision', visionRoute);
app.use('/rag', ragRoute);

describe('Stub routes', () => {
  it('POST /vision returns 501', async () => {
    const res = await request(app).post('/vision').send({});
    expect(res.status).toBe(501);
    expect(res.body).toHaveProperty('error');
  });

  it('POST /rag returns 501', async () => {
    const res = await request(app).post('/rag').send({});
    expect(res.status).toBe(501);
    expect(res.body).toHaveProperty('error');
  });
});
