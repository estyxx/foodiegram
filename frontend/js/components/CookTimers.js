// @ts-check

import { formatClock, formatDuration } from "../lib/cookingSteps.js";
import {
  addMinute,
  goToStep,
  removeTimer,
  startTimer,
  timerRemaining,
  toggleTimer,
} from "../lib/cookingSession.js";

/** @typedef {import("../lib/cookingSession.js").CookTimer} CookTimer */

/** Minutes offered as one-tap timers. */
const PRESET_MINUTES = [1, 3, 5, 10, 15];

/**
 * @param {CookTimer} timer
 * @returns {"done" | "running" | "paused"}
 */
export function timerState(timer) {
  if (timer.done) {
    return "done";
  }
  return timer.running ? "running" : "paused";
}

/**
 * "Pause Soffritto timer" and friends, for the toggle's accessible name.
 * @param {CookTimer} timer
 * @returns {string}
 */
export function toggleLabel(timer) {
  const verb = { done: "Dismiss", running: "Pause", paused: "Resume" }[timerState(timer)];
  return `${verb} ${timer.label} timer`;
}

/** @type {Record<"done" | "running" | "paused", string>} */
export const TIMER_ICON = { done: "✓", running: "❚❚", paused: "▶" };

/**
 * A clock the session ticker updates in place (see CookingMode's onTick).
 * @param {CookTimer} timer
 * @param {number} now
 * @param {string} className
 * @returns {HTMLSpanElement}
 */
export function TimerClock(timer, now, className) {
  const clock = document.createElement("span");
  clock.className = className;
  clock.dataset.clock = timer.id;
  clock.textContent = formatClock(timerRemaining(timer, now));
  return clock;
}

/**
 * The desktop timer card: big clock, progress bar, pause / +1 min / step.
 * @param {CookTimer} timer
 * @param {number} now
 * @returns {HTMLElement}
 */
export function TimerCard(timer, now) {
  const state = timerState(timer);
  const card = document.createElement("div");
  card.className = `cook-timer cook-timer--${state}`;

  const head = document.createElement("div");
  head.className = "cook-timer__head";
  const label = document.createElement("span");
  label.className = "cook-timer__label";
  const stateText = { done: "Time’s up", running: "Running", paused: "Paused" }[state];
  label.textContent = `${timer.label} · ${stateText}`;
  head.append(label, removeButton(timer, `card-remove:${timer.id}`, "cook-timer__remove"));

  const track = document.createElement("div");
  track.className = "cook-timer__track";
  const bar = document.createElement("div");
  bar.className = "cook-timer__bar";
  bar.dataset.bar = timer.id;
  bar.style.width = progress(timer, now);
  track.append(bar);

  const actions = document.createElement("div");
  actions.className = "cook-timer__actions";
  const toggle = timerButton(
    { done: "Dismiss", running: "Pause", paused: "Resume" }[state],
    `card-toggle:${timer.id}`,
    () => toggleTimer(timer.id),
  );
  toggle.classList.add("cook-timer__toggle");
  toggle.setAttribute("aria-label", toggleLabel(timer));
  const plus = timerButton("+1 min", `card-plus:${timer.id}`, () => addMinute(timer.id));
  plus.setAttribute("aria-label", `Add one minute to ${timer.label} timer`);
  actions.append(toggle, plus);
  const { step } = timer;
  if (step !== null) {
    actions.append(
      timerButton(`Step ${step + 1}`, `card-step:${timer.id}`, () => goToStep(step)),
    );
  }

  card.append(head, TimerClock(timer, now, "cook-timer__clock"), track, actions);
  return card;
}

/**
 * The phone timer chip for the bottom strip: tap to pause/resume, × to remove.
 * @param {CookTimer} timer
 * @param {number} now
 * @returns {HTMLElement}
 */
export function TimerChip(timer, now) {
  const state = timerState(timer);
  const chip = document.createElement("div");
  chip.className = `cook-chip cook-timer--${state}`;

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "cook-chip__toggle";
  toggle.dataset.focus = `strip-toggle:${timer.id}`;
  toggle.setAttribute("aria-label", toggleLabel(timer));
  toggle.addEventListener("click", () => toggleTimer(timer.id));
  const icon = document.createElement("span");
  icon.className = "cook-chip__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = TIMER_ICON[state];
  const label = document.createElement("span");
  label.className = "cook-chip__label";
  label.textContent = timer.label;
  toggle.append(icon, TimerClock(timer, now, "cook-chip__clock"), label);

  chip.append(toggle, removeButton(timer, `strip-remove:${timer.id}`, "cook-chip__remove"));
  return chip;
}

/**
 * One-tap 1–15 minute timers.
 * @param {string} focusPrefix keeps focus keys unique between the two layouts
 * @param {() => void} [onStart]
 * @returns {HTMLButtonElement[]}
 */
export function PresetButtons(focusPrefix, onStart) {
  return PRESET_MINUTES.map((minutes) => {
    const button = timerButton(`${minutes} min`, `${focusPrefix}:${minutes}`, () => {
      startTimer({ seconds: minutes * 60, label: `${minutes}-min timer`, step: null });
      onStart?.();
    });
    button.classList.add("cook-preset");
    button.setAttribute("aria-label", `Start a ${formatDuration(minutes * 60)} timer`);
    return button;
  });
}

/**
 * Percentage elapsed, as a CSS width.
 * @param {CookTimer} timer
 * @param {number} now
 * @returns {string}
 */
export function progress(timer, now) {
  if (timer.done) {
    return "100%";
  }
  const elapsed = 1 - timerRemaining(timer, now) / timer.total;
  return `${Math.min(100, Math.max(0, elapsed * 100))}%`;
}

/**
 * @param {CookTimer} timer
 * @param {string} focusKey
 * @param {string} className
 * @returns {HTMLButtonElement}
 */
function removeButton(timer, focusKey, className) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.dataset.focus = focusKey;
  button.textContent = "×";
  button.setAttribute("aria-label", `Remove ${timer.label} timer`);
  button.addEventListener("click", () => removeTimer(timer.id));
  return button;
}

/**
 * @param {string} text
 * @param {string} focusKey
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function timerButton(text, focusKey, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "cook-timer__btn";
  button.dataset.focus = focusKey;
  button.textContent = text;
  button.addEventListener("click", onClick);
  return button;
}
