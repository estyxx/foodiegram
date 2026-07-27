// @ts-check

/**
 * @template T
 * @typedef {object} Store
 * @property {() => T} get                         Current state snapshot.
 * @property {(patch: Partial<T>) => void} set     Shallow-merge a patch, then notify.
 * @property {(listener: (state: T) => void) => () => void} subscribe
 *   Register a listener; returns an unsubscribe function.
 */

/**
 * Create a tiny observable store with shallow-merge updates.
 * @template T
 * @param {T} initial
 * @returns {Store<T>}
 */
export function createStore(initial) {
  let state = initial;
  /** @type {Set<(state: T) => void>} */
  const listeners = new Set();

  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      for (const listener of listeners) {
        listener(state);
      }
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
