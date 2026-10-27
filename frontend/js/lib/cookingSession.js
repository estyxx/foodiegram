// @ts-check

/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/**
 * @typedef {object} CookTimer
 * @property {string} id
 * @property {string} key "step:seconds" for a step's timer, the id for a quick one
 * @property {string} label
 * @property {number | null} step index of the step it was started from
 * @property {number} total seconds, for the progress bar
 * @property {number} remaining seconds left when last paused
 * @property {number} endAt epoch ms it ends at while running
 * @property {boolean} running
 * @property {boolean} done
 */
/**
 * @typedef {object} CookSession
 * @property {RecipeDetail} recipe
 * @property {number} ratio the servings scale set on the recipe page
 * @property {number} step
 * @property {boolean} finished
 * @property {Set<number>} checked ingredient indexes ticked off
 * @property {CookTimer[]} timers
 * @property {boolean} open
 */
/**
 * "change" re-renders, "tick" only moves the clocks.
 * @typedef {{ type: "change" } | { type: "tick" } | { type: "announce", message: string }} CookEvent
 */

const TICK_MS = 250;
const MINUTE_MS = 60_000;

/**
 * The one cooking session. It outlives route changes so timers keep running
 * while the rest of the app is used.
 * @type {CookSession | null}
 */
let session = null;

/** @type {Set<(event: CookEvent) => void>} */
const listeners = new Set();

/** @type {number | null} */
let ticker = null;
let nextId = 0;

/** @type {AudioContext | null} */
let audio = null;

/** @returns {CookSession | null} */
export function getSession() {
  return session;
}

/**
 * @param {(event: CookEvent) => void} listener
 * @returns {() => void} unsubscribe
 */
export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Open cooking mode for a recipe. Reopening the same recipe keeps its place,
 * ticks and timers; a different recipe starts fresh.
 * @param {RecipeDetail} recipe
 * @param {number} ratio
 */
export function startCooking(recipe, ratio) {
  if (session !== null && session.recipe.code === recipe.code) {
    session = { ...session, recipe, ratio, finished: false, open: true };
  } else {
    session = {
      recipe,
      ratio,
      step: 0,
      finished: false,
      checked: new Set(),
      timers: [],
      open: true,
    };
  }
  syncTicker();
  emit({ type: "change" });
}

/** Bring back the session the corner pill points to. */
export function resumeCooking() {
  update({ open: true });
}

/** Leave cooking mode; running timers carry on. */
export function closeCooking() {
  update({ open: false });
}

/** @param {number} step */
export function goToStep(step) {
  update({ step, finished: false });
}

export function nextStep() {
  if (session === null) {
    return;
  }
  if (session.finished) {
    closeCooking();
  } else if (session.step < session.recipe.instructions.length - 1) {
    update({ step: session.step + 1 });
  } else {
    update({ finished: true });
  }
}

export function previousStep() {
  if (session === null) {
    return;
  }
  if (session.finished) {
    update({ finished: false });
  } else if (session.step > 0) {
    update({ step: session.step - 1 });
  }
}

export function restartCooking() {
  update({ step: 0, finished: false, checked: new Set() });
}

/** @param {number} index */
export function toggleIngredient(index) {
  if (session === null) {
    return;
  }
  const checked = new Set(session.checked);
  if (!checked.delete(index)) {
    checked.add(index);
  }
  update({ checked });
}

/**
 * @param {{ seconds: number, label: string, step: number | null }} timer
 */
export function startTimer({ seconds, label, step }) {
  unlockAudio();
  nextId += 1;
  const id = `t${nextId}`;
  /** @type {CookTimer} */
  const timer = {
    id,
    key: step === null ? id : timerKey(step, seconds),
    label,
    step,
    total: seconds,
    remaining: seconds,
    endAt: Date.now() + seconds * 1000,
    running: true,
    done: false,
  };
  setTimers((timers) => [...timers, timer]);
  emit({ type: "announce", message: `${label} timer started.` });
}

/**
 * Pause a running timer, resume a paused one, dismiss a finished one.
 * @param {string} id
 */
export function toggleTimer(id) {
  unlockAudio();
  const now = Date.now();
  setTimers((timers) =>
    timers.flatMap((t) => {
      if (t.id !== id) {
        return [t];
      }
      if (t.done) {
        return [];
      }
      if (t.running) {
        return [{ ...t, running: false, remaining: timerRemaining(t, now) }];
      }
      return [{ ...t, running: true, endAt: now + t.remaining * 1000 }];
    }),
  );
}

/**
 * Add a minute; on a finished timer, start a fresh one-minute countdown.
 * @param {string} id
 */
export function addMinute(id) {
  const now = Date.now();
  setTimers((timers) =>
    timers.map((t) => {
      if (t.id !== id) {
        return t;
      }
      if (t.done) {
        return {
          ...t,
          done: false,
          running: true,
          total: 60,
          remaining: 60,
          endAt: now + MINUTE_MS,
        };
      }
      if (t.running) {
        return { ...t, endAt: t.endAt + MINUTE_MS, total: t.total + 60 };
      }
      return { ...t, remaining: t.remaining + 60, total: t.total + 60 };
    }),
  );
}

/** @param {string} id */
export function removeTimer(id) {
  setTimers((timers) => timers.filter((t) => t.id !== id));
}

/**
 * @param {number} step
 * @param {number} seconds
 * @returns {string}
 */
export function timerKey(step, seconds) {
  return `${step}:${seconds}`;
}

/**
 * Seconds left on a timer at `now`.
 * @param {CookTimer} timer
 * @param {number} now epoch ms
 * @returns {number}
 */
export function timerRemaining(timer, now) {
  if (timer.done) {
    return 0;
  }
  return timer.running ? Math.max(0, (timer.endAt - now) / 1000) : timer.remaining;
}

/**
 * @param {Partial<CookSession>} patch
 */
function update(patch) {
  if (session === null) {
    return;
  }
  session = { ...session, ...patch };
  emit({ type: "change" });
}

/**
 * @param {(timers: CookTimer[]) => CookTimer[]} change
 */
function setTimers(change) {
  if (session === null) {
    return;
  }
  session = { ...session, timers: change(session.timers) };
  syncTicker();
  emit({ type: "change" });
}

/** @param {CookEvent} event */
function emit(event) {
  for (const listener of listeners) {
    listener(event);
  }
}

/** Run the clock only while some timer is counting down. */
function syncTicker() {
  const running = session !== null && session.timers.some((t) => t.running);
  if (running && ticker === null) {
    ticker = window.setInterval(tick, TICK_MS);
  } else if (!running && ticker !== null) {
    window.clearInterval(ticker);
    ticker = null;
  }
}

function tick() {
  if (session === null) {
    return;
  }
  const now = Date.now();
  /** @type {CookTimer[]} */
  const fired = [];
  const timers = session.timers.map((t) => {
    if (!t.running || t.endAt > now) {
      return t;
    }
    fired.push(t);
    return { ...t, running: false, done: true, remaining: 0 };
  });
  if (fired.length === 0) {
    emit({ type: "tick" });
    return;
  }
  session = { ...session, timers };
  syncTicker();
  chime();
  emit({ type: "change" });
  emit({
    type: "announce",
    message: fired.map((t) => `${t.label} timer done.`).join(" "),
  });
}

/**
 * Browsers only allow sound after a gesture, so the audio context is created
 * (or resumed) when a timer is started, not when it rings.
 */
function unlockAudio() {
  if (typeof AudioContext === "undefined") {
    return;
  }
  audio ??= new AudioContext();
  if (audio.state === "suspended") {
    audio.resume().catch(() => {});
  }
}

/** Two bursts of three soft beeps, and a buzz on phones that can. */
function chime() {
  if (audio !== null) {
    const t0 = audio.currentTime;
    for (const offset of [0, 0.28, 0.56, 1.2, 1.48, 1.76]) {
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, t0 + offset);
      gain.gain.exponentialRampToValueAtTime(0.3, t0 + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + offset + 0.22);
      osc.connect(gain);
      gain.connect(audio.destination);
      osc.start(t0 + offset);
      osc.stop(t0 + offset + 0.25);
    }
  }
  if ("vibrate" in navigator) {
    navigator.vibrate([250, 120, 250, 120, 250]);
  }
}
