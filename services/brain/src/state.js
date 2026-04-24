const store = {
  currentState: 'idle',
  clients: [],
  setState(key) {
    this.currentState = key;
    const message = `data: ${JSON.stringify({ state: key })}\n\n`;
    this.clients.forEach(res => res.write(message));
  },
};

module.exports = store;
