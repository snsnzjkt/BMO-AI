describe('state store', () => {
  let state;

  beforeEach(() => {
    jest.resetModules();
    state = require('../state');
  });

  it('starts with idle as current state', () => {
    expect(state.currentState).toBe('idle');
  });

  it('setState updates currentState', () => {
    state.setState('thinking');
    expect(state.currentState).toBe('thinking');
  });

  it('setState broadcasts to all clients', () => {
    const write1 = jest.fn();
    const write2 = jest.fn();
    state.clients.push({ write: write1 }, { write: write2 });
    state.setState('recording');
    expect(write1).toHaveBeenCalledWith('data: {"state":"recording"}\n\n');
    expect(write2).toHaveBeenCalledWith('data: {"state":"recording"}\n\n');
  });

  it('setState with no clients does not throw', () => {
    expect(() => state.setState('speaking')).not.toThrow();
  });
});
