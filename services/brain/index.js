require('dotenv').config();
const express = require('express');

const chatRoute = require('./src/routes/chat');
const visionRoute = require('./src/routes/vision');
const ragRoute = require('./src/routes/rag');

const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());

app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    console.log(`${req.method} ${req.path} ${res.statusCode} — ${Date.now() - start}ms`);
  });
  next();
});

app.get('/health', (req, res) => res.json({ status: 'ok', service: 'brain' }));

app.use('/chat', chatRoute);
app.use('/vision', visionRoute);
app.use('/rag', ragRoute);

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`BMO Brain service running on port ${PORT} 🎮`);
  });
}

module.exports = app;
