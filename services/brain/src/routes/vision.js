const { Router } = require('express');

const router = Router();

router.post('/', (req, res) => {
  res.status(501).json({ error: 'Vision pipeline not yet implemented (Phase 4).' });
});

module.exports = router;
