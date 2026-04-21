const { Router } = require('express');

const router = Router();

router.post('/', (req, res) => {
  res.status(501).json({ error: 'RAG pipeline not yet implemented (Phase 5).' });
});

module.exports = router;
