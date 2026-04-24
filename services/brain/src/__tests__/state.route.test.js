const http = require('http');
const request = require('supertest');
const express = require('express');

describe('state route', () => {
  let app, state, stateRoute;

  beforeEach(() => {
    jest.resetModules();
    state = require('../state');
    stateRoute = require('../routes/state');
    app = express();
    app.use(express.json());
    app.use('/state', stateRoute);
  });

  describe('POST /state', () => {
    it('returns 204 and updates currentState', async () => {
      const res = await request(app).post('/state').send({ state: 'thinking' });
      expect(res.status).toBe(204);
      expect(state.currentState).toBe('thinking');
    });

    it('returns 400 when state field is missing', async () => {
      const res = await request(app).post('/state').send({});
      expect(res.status).toBe(400);
    });

    it('returns 400 when state is not a string', async () => {
      const res = await request(app).post('/state').send({ state: 42 });
      expect(res.status).toBe(400);
    });

    it('returns 400 when state is not a known key', async () => {
      const res = await request(app).post('/state').send({ state: 'bogus' });
      expect(res.status).toBe(400);
    });
  });

  describe('GET /state/stream', () => {
    it('sets SSE headers and sends current state immediately', (done) => {
      const server = app.listen(0, () => {
        const { port } = server.address();
        let data = '';
        const req = http.get(`http://localhost:${port}/state/stream`, (res) => {
          expect(res.headers['content-type']).toMatch('text/event-stream');
          expect(res.headers['cache-control']).toBe('no-cache');
          expect(res.headers['connection']).toBe('keep-alive');
          expect(res.headers['access-control-allow-origin']).toBe('*');
          res.on('data', (chunk) => {
            data += chunk.toString();
            if (data.includes('\n\n')) {
              expect(data).toContain('data: {"state":"idle"}');
              req.destroy();
              server.close(done);
            }
          });
        });
      });
    });

    it('removes client from clients array on connection close', (done) => {
      const server = app.listen(0, () => {
        const { port } = server.address();
        const req = http.get(`http://localhost:${port}/state/stream`, () => {
          expect(state.clients.length).toBe(1);
          req.destroy();
          setTimeout(() => {
            expect(state.clients.length).toBe(0);
            server.close(done);
          }, 50);
        });
      });
    });
  });
});
