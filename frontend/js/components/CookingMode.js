// @ts-check

import { formatQuantity } from "../lib/format.js";
import { PHONE_SHORTCUT_NAME, canSetPhoneTimer } from "../lib/phoneTimer.js";
import { formatClock, mentionsIngredient, parseStep } from "../lib/cookingSteps.js";
import {
  closeCooking,
  getSession,
  goToStep,
  nextStep,
  previousStep,
  restartCooking,
  startTimer,
  subscribe,
  timerKey,
  timerRemaining,
  toggleIngredient,
  toggleTimer,
  removeTimer,
} from "../lib/cookingSession.js";
import {
  PresetButtons,
  TIMER_ICON,
  TimerCard,
  TimerChip,
  TimerClock,
  progress,
  timerState,
  toggleLabel,
} from "./CookTimers.js";

/** @typedef {import("../lib/cookingSession.js").CookSession} CookSession */
/** @typedef {import("../lib/cookingSession.js").CookTimer} CookTimer */
/** @typedef {import("../lib/cookingSteps.js").ParsedStep} ParsedStep */
/** @typedef {import("../lib/cookingSteps.js").StepTime} StepTime */

const NUMBER_RE = /(\d+\.?\d*)/;

/** A horizontal swipe longer than this (px), and mostly sideways, turns the step. */
const SWIPE_PX = 60;

/**
 * The full-screen cooking mode. Mounted once; opens and closes with the
 * cooking session. A <dialog> gives the focus trap and inert page for free.
 * @returns {HTMLDialogElement}
 */
export function CookingMode() {
  const dialog = document.createElement("dialog");
  dialog.className = "cook";

  const live = document.createElement("div");
  live.className = "visually-hidden";
  live.setAttribute("aria-live", "polite");

  let sheetOpen = false;
  let presetsOpen = false;
  let phoneHelpOpen = false;
  /** @type {WakeLockSentinel | null} */
  let wakeLock = null;
  /** @type {HTMLElement | null} */
  let opener = null;
  /** @type {{ x: number, y: number } | null} */
  let touch = null;

  subscribe((event) => {
    if (event.type === "announce") {
      live.textContent = event.message;
    } else if (event.type === "tick") {
      onTick();
    } else {
      sync();
    }
  });

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    if (sheetOpen) {
      setSheet(false);
    } else {
      closeCooking();
    }
  });
  dialog.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      nextStep();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      previousStep();
    }
  });
  dialog.addEventListener("touchstart", (event) => {
    const target = event.target;
    const first = event.touches[0];
    const inStrip = target instanceof Element && target.closest("[data-noswipe]");
    touch = first && !inStrip && !sheetOpen ? { x: first.clientX, y: first.clientY } : null;
  });
  dialog.addEventListener("touchend", (event) => {
    const last = event.changedTouches[0];
    if (touch === null || !last) {
      return;
    }
    const dx = last.clientX - touch.x;
    const dy = last.clientY - touch.y;
    touch = null;
    if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy) * 1.5) {
      if (dx < 0) {
        nextStep();
      } else {
        previousStep();
      }
    }
  });
  document.addEventListener("visibilitychange", () => {
    // The browser drops the wake lock whenever the tab is hidden.
    if (document.visibilityState === "visible" && dialog.open) {
      requestWakeLock();
    }
  });

  /** Open, close or re-render to match the session. */
  function sync() {
    const session = getSession();
    const shouldOpen = session !== null && session.open;
    if (shouldOpen && !dialog.open) {
      opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      sheetOpen = false;
      presetsOpen = false;
      render(session);
      dialog.showModal();
      document.documentElement.classList.add("is-cooking");
      requestWakeLock();
      focusStart();
      return;
    }
    if (!shouldOpen && dialog.open) {
      dialog.close();
      document.documentElement.classList.remove("is-cooking");
      releaseWakeLock();
      if (opener?.isConnected) {
        opener.focus();
      }
      return;
    }
    if (shouldOpen) {
      render(session);
    }
  }

  /** @param {boolean} open */
  function setSheet(open) {
    sheetOpen = open;
    const session = getSession();
    if (session !== null) {
      render(session);
    }
    const key = open ? "sheet-done" : "sheet-open";
    const target = dialog.querySelector(`[data-focus='${key}']`);
    if (target instanceof HTMLElement) {
      target.focus();
    }
  }

  function focusStart() {
    const target = dialog.querySelector(".cook__stage");
    if (target instanceof HTMLElement) {
      target.focus();
    }
  }

  /** @param {CookSession} session */
  function render(session) {
    const active = document.activeElement;
    const hadFocus = active instanceof HTMLElement && dialog.contains(active);
    const focusKey = hadFocus ? active.dataset.focus : undefined;

    const now = Date.now();
    const steps = session.recipe.instructions;
    const index = Math.min(session.step, Math.max(0, steps.length - 1));
    const parsed = parseStep(steps[index] ?? "", index);

    dialog.setAttribute("aria-label", `Cooking mode: ${session.recipe.title ?? "recipe"}`);
    dialog.classList.toggle("cook--sheet-open", sheetOpen);
    dialog.replaceChildren(
      buildTopBar(session),
      buildProgress(session, index),
      buildBody(session, index, parsed, now),
      buildStrip(session, now),
      buildNav(session, index),
      live,
    );

    if (focusKey) {
      const again = dialog.querySelector(`[data-focus="${CSS.escape(focusKey)}"]`);
      if (again instanceof HTMLElement) {
        again.focus();
        return;
      }
    }
    if (hadFocus && !dialog.contains(document.activeElement)) {
      focusStart();
    }
  }

  /** Move the clocks and bars without rebuilding (and losing focus). */
  function onTick() {
    const session = getSession();
    if (session === null || !dialog.open) {
      return;
    }
    const now = Date.now();
    const byId = new Map(session.timers.map((t) => [t.id, t]));
    for (const el of dialog.querySelectorAll("[data-clock]")) {
      const timer = el instanceof HTMLElement ? byId.get(el.dataset.clock ?? "") : undefined;
      if (timer) {
        el.textContent = formatClock(timerRemaining(timer, now));
      }
    }
    for (const el of dialog.querySelectorAll("[data-bar]")) {
      const timer = el instanceof HTMLElement ? byId.get(el.dataset.bar ?? "") : undefined;
      if (timer && el instanceof HTMLElement) {
        el.style.width = progress(timer, now);
      }
    }
  }

  async function requestWakeLock() {
    if (!("wakeLock" in navigator) || wakeLock !== null) {
      return;
    }
    try {
      wakeLock = await navigator.wakeLock.request("screen");
      wakeLock.addEventListener("release", () => {
        wakeLock = null;
        sync();
      });
      sync();
    } catch {
      // Refused (low battery, unsupported context): cooking works without it.
      wakeLock = null;
    }
  }

  function releaseWakeLock() {
    const lock = wakeLock;
    wakeLock = null;
    lock?.release().catch(() => {});
  }

  /** @param {CookSession} session */
  function buildTopBar(session) {
    const bar = document.createElement("div");
    bar.className = "cook__top";

    const close = button("×", "cook__close", "close", closeCooking);
    close.setAttribute("aria-label", "Exit cooking mode");

    const titles = document.createElement("div");
    titles.className = "cook__titles";
    const eyebrow = document.createElement("div");
    eyebrow.className = "cook__eyebrow";
    eyebrow.textContent = "Cooking mode";
    const title = document.createElement("div");
    title.className = "cook__title";
    title.textContent = session.recipe.title ?? "";
    titles.append(eyebrow, title);

    bar.append(close, titles);
    if (wakeLock !== null) {
      const awake = document.createElement("span");
      awake.className = "cook__awake";
      awake.textContent = "☀ Screen stays on";
      bar.append(awake);
    }
    const ingredients = button("Ingredients", "cook__sheet-btn", "sheet-open", () =>
      setSheet(true),
    );
    ingredients.setAttribute("aria-expanded", String(sheetOpen));
    bar.append(ingredients);
    return bar;
  }

  /**
   * @param {CookSession} session
   * @param {number} index
   */
  function buildProgress(session, index) {
    const nav = document.createElement("div");
    nav.className = "cook__progress";
    session.recipe.instructions.forEach((_, k) => {
      const dot = button("", "cook__dot", `dot:${k}`, () => goToStep(k));
      dot.setAttribute("aria-label", `Go to step ${k + 1}`);
      const current = !session.finished && k === index;
      if (current) {
        dot.setAttribute("aria-current", "step");
      }
      const bar = document.createElement("span");
      bar.className = "cook__dot-bar";
      if (session.finished || k < index) {
        bar.classList.add("cook__dot-bar--done");
      } else if (current) {
        bar.classList.add("cook__dot-bar--current");
      }
      dot.append(bar);
      nav.append(dot);
    });
    return nav;
  }

  /**
   * @param {CookSession} session
   * @param {number} index
   * @param {ParsedStep} parsed
   * @param {number} now
   */
  function buildBody(session, index, parsed, now) {
    const body = document.createElement("div");
    body.className = "cook__body";

    const stage = document.createElement("div");
    stage.className = "cook__stage";
    stage.tabIndex = -1;
    const inner = document.createElement("div");
    inner.className = "cook__stage-inner";
    inner.append(
      ...(session.finished
        ? buildFinished(session)
        : buildStep(session, index, parsed, now)),
    );
    stage.append(inner);

    body.append(buildIngredients(session, parsed), stage, buildTimerRail(session, now));
    return body;
  }

  /**
   * @param {CookSession} session
   * @param {number} index
   * @param {ParsedStep} parsed
   * @param {number} now
   * @returns {HTMLElement[]}
   */
  function buildStep(session, index, parsed, now) {
    const eyebrow = document.createElement("div");
    eyebrow.className = "cook__step-num";
    eyebrow.textContent = `Step ${index + 1} of ${session.recipe.instructions.length}`;

    /** @type {HTMLElement[]} */
    const parts = [eyebrow];
    if (parsed.title !== null) {
      const heading = document.createElement("h2");
      heading.className = "cook__step-title";
      heading.textContent = parsed.title;
      parts.push(heading);
    }

    const text = document.createElement("p");
    text.className = "cook__step-text";
    parsed.segments.forEach((segment, k) => {
      if (segment.time === null) {
        text.append(document.createTextNode(segment.text));
        return;
      }
      const time = segment.time;
      const inline = button(segment.text, "cook__inline-time", `inline:${k}`, () =>
        pressTime(session, index, parsed, time),
      );
      inline.setAttribute("aria-label", timeLabel(session, index, parsed, time));
      text.append(inline);
    });
    parts.push(text);

    if (parsed.times.length > 0) {
      const chips = document.createElement("div");
      chips.className = "cook__times";
      for (const time of parsed.times) {
        chips.append(buildTimeChip(session, index, parsed, time, now));
      }
      parts.push(chips);
    }
    if (canSetPhoneTimer()) {
      parts.push(buildPhoneHelp());
    }
    return parts;
  }

  /** How to make timers ring like an alarm: the one-time Shortcut setup. */
  function buildPhoneHelp() {
    const help = document.createElement("details");
    help.className = "cook__phone-help";
    help.open = phoneHelpOpen;
    help.addEventListener("toggle", () => {
      phoneHelpOpen = help.open;
    });
    const summary = document.createElement("summary");
    summary.dataset.focus = "phone-help";
    summary.textContent = "⏰ Ring even when the iPhone is locked or on silent";
    const how = document.createElement("p");
    how.textContent =
      "Tap ⏰ on a timer to start the same countdown in the Clock app. " +
      `Set up once in Shortcuts: a new shortcut named “${PHONE_SHORTCUT_NAME}” ` +
      "with one “Start Timer” action, its duration set to Shortcut Input " +
      "and the unit to seconds.";
    help.append(summary, how);
    return help;
  }

  /**
   * The big "Start 3 min timer" button under the step text.
   * @param {CookSession} session
   * @param {number} index
   * @param {ParsedStep} parsed
   * @param {StepTime} time
   * @param {number} now
   */
  function buildTimeChip(session, index, parsed, time, now) {
    const timer = findTimer(session, index, time);
    const chip = button("", "cook__time", `chip:${time.seconds}`, () =>
      pressTime(session, index, parsed, time),
    );
    chip.setAttribute("aria-label", timeLabel(session, index, parsed, time));
    const icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    if (timer === undefined) {
      icon.textContent = "⏱";
      chip.append(icon, document.createTextNode(`Start ${time.label} timer`));
      return chip;
    }
    const state = timerState(timer);
    chip.classList.add(`cook__time--${state}`);
    icon.textContent = TIMER_ICON[state];
    if (state === "done") {
      chip.append(icon, document.createTextNode("Time’s up · dismiss"));
    } else {
      const verb = state === "running" ? "pause" : "resume";
      chip.append(icon, TimerClock(timer, now, ""), document.createTextNode(` · ${verb}`));
    }
    return chip;
  }

  /**
   * @param {CookSession} session
   * @param {number} index
   * @param {ParsedStep} parsed
   * @param {StepTime} time
   */
  function pressTime(session, index, parsed, time) {
    const timer = findTimer(session, index, time);
    if (timer === undefined) {
      startTimer({ seconds: time.seconds, label: parsed.short, step: index });
    } else if (timer.done) {
      removeTimer(timer.id);
    } else {
      toggleTimer(timer.id);
    }
  }

  /**
   * @param {CookSession} session
   * @param {number} index
   * @param {ParsedStep} parsed
   * @param {StepTime} time
   * @returns {string}
   */
  function timeLabel(session, index, parsed, time) {
    const timer = findTimer(session, index, time);
    return timer === undefined
      ? `Start a ${time.label} timer for ${parsed.short}`
      : toggleLabel(timer);
  }

  /** @param {CookSession} session */
  function buildFinished(session) {
    const running = session.timers.some((t) => t.running);
    const note = document.createElement("div");
    note.className = "cook__step-num";
    note.textContent = `All ${session.recipe.instructions.length} steps done${
      running ? " · a timer is still running" : ""
    }`;
    const heading = document.createElement("h2");
    heading.className = "cook__done-title";
    heading.textContent = "Buon appetito.";
    const actions = document.createElement("div");
    actions.className = "cook__done-actions";
    actions.append(
      button("Back to recipe", "cook__btn cook__btn--light", "done-close", closeCooking),
      button("Start over", "cook__btn", "done-restart", restartCooking),
    );
    const wrap = document.createElement("div");
    wrap.className = "cook__done";
    wrap.append(note, heading, actions);
    return [wrap];
  }

  /**
   * Tick-off list: a column on desktop, a slide-up sheet on phones.
   * @param {CookSession} session
   * @param {ParsedStep} parsed
   */
  function buildIngredients(session, parsed) {
    const panel = document.createElement("section");
    panel.className = "cook__ingredients";
    panel.setAttribute("aria-label", "Ingredients");
    panel.dataset.noswipe = "true";

    const handle = document.createElement("div");
    handle.className = "cook__sheet-handle";
    handle.setAttribute("aria-hidden", "true");

    const head = document.createElement("div");
    head.className = "cook__panel-head";
    const title = document.createElement("h3");
    title.className = "cook__panel-title";
    title.textContent = "Ingredients";
    const base = session.recipe.base_servings;
    const servings = document.createElement("span");
    servings.className = "cook__panel-meta";
    servings.textContent =
      base === null ? "as saved" : `for ${formatQuantity(base * session.ratio)}`;
    const done = button("Done", "cook__sheet-done", "sheet-done", () => setSheet(false));
    head.append(title, servings, done);

    const list = document.createElement("ul");
    list.className = "cook__ing-list";
    const stepText = session.finished ? "" : parsed.body;
    session.recipe.ingredients.forEach((line, k) => {
      const checked = session.checked.has(k);
      const row = button("", "cook__ing", `ing:${k}`, () => toggleIngredient(k));
      row.setAttribute("role", "checkbox");
      row.setAttribute("aria-checked", String(checked));
      const box = document.createElement("span");
      box.className = "cook__ing-box";
      box.setAttribute("aria-hidden", "true");
      box.textContent = checked ? "✓" : "";
      const text = document.createElement("span");
      text.className = "cook__ing-text";
      const match = NUMBER_RE.exec(line);
      if (match === null) {
        text.textContent = line;
      } else {
        const amount = document.createElement("b");
        amount.className = "cook__ing-amt";
        amount.textContent = formatQuantity(parseFloat(match[1]) * session.ratio);
        const rest = (line.slice(0, match.index) + line.slice(match.index + match[1].length)).trim();
        text.append(amount, document.createTextNode(` ${rest}`));
      }
      row.append(box, text);
      if (!checked && stepText && mentionsIngredient(line, stepText)) {
        const tag = document.createElement("span");
        tag.className = "cook__ing-step";
        tag.textContent = "this step";
        row.append(tag);
      }
      const item = document.createElement("li");
      item.append(row);
      list.append(item);
    });

    panel.append(handle, head, list);

    const scrim = document.createElement("div");
    scrim.className = "cook__scrim";
    scrim.addEventListener("click", () => setSheet(false));
    const wrap = document.createElement("div");
    wrap.className = "cook__ing-wrap";
    wrap.append(scrim, panel);
    return wrap;
  }

  /**
   * @param {CookSession} session
   * @param {number} now
   */
  function buildTimerRail(session, now) {
    const rail = document.createElement("aside");
    rail.className = "cook__timers";
    rail.setAttribute("aria-label", "Timers");

    const head = document.createElement("div");
    head.className = "cook__panel-head";
    const title = document.createElement("h3");
    title.className = "cook__panel-title";
    title.textContent = "Timers";
    const count = document.createElement("span");
    count.className = "cook__panel-meta";
    const running = session.timers.filter((t) => t.running).length;
    count.textContent = session.timers.length > 0 ? `${running} running` : "";
    head.append(title, count);
    rail.append(head);

    if (session.timers.length === 0) {
      const hint = document.createElement("p");
      hint.className = "cook__hint";
      hint.textContent =
        "Tap a time in the step to start a timer. Timers keep running while you move between steps.";
      rail.append(hint);
    }
    for (const timer of session.timers) {
      rail.append(TimerCard(timer, now));
    }

    const quick = document.createElement("div");
    quick.className = "cook__quick";
    const label = document.createElement("div");
    label.className = "cook__quick-label";
    label.textContent = "Quick timer";
    const presets = document.createElement("div");
    presets.className = "cook__presets";
    presets.append(...PresetButtons("rail-preset"));
    quick.append(label, presets);
    rail.append(quick);
    return rail;
  }

  /**
   * The phone timer strip, scrolled sideways.
   * @param {CookSession} session
   * @param {number} now
   */
  function buildStrip(session, now) {
    const strip = document.createElement("div");
    strip.className = "cook__strip";
    strip.setAttribute("role", "region");
    strip.setAttribute("aria-label", "Timers");
    strip.dataset.noswipe = "true";

    const add = button("+ Timer", "cook__strip-add", "strip-add", () => {
      presetsOpen = !presetsOpen;
      render(session);
    });
    add.setAttribute("aria-expanded", String(presetsOpen));
    strip.append(add);
    if (presetsOpen) {
      strip.append(
        ...PresetButtons("strip-preset", () => {
          presetsOpen = false;
        }),
      );
    }
    for (const timer of session.timers) {
      strip.append(TimerChip(timer, now));
    }
    return strip;
  }

  /**
   * @param {CookSession} session
   * @param {number} index
   */
  function buildNav(session, index) {
    const nav = document.createElement("nav");
    nav.className = "cook__nav";
    nav.setAttribute("aria-label", "Steps");
    const total = session.recipe.instructions.length;
    const atStart = !session.finished && index === 0;

    const back = button("← Back", "cook__btn", "back", previousStep);
    back.disabled = atStart;
    const position = document.createElement("span");
    position.className = "cook__position";
    position.setAttribute("aria-live", "polite");
    position.textContent = session.finished ? "Finished" : `Step ${index + 1} of ${total}`;

    let nextText = "Next →";
    if (session.finished) {
      nextText = "Close";
    } else if (index === total - 1) {
      nextText = "Finish ✓";
    }
    const next = button(nextText, "cook__btn cook__btn--light", "next", nextStep);
    nav.append(back, position, next);
    return nav;
  }

  return dialog;
}

/**
 * @param {CookSession} session
 * @param {number} index
 * @param {StepTime} time
 * @returns {CookTimer | undefined}
 */
function findTimer(session, index, time) {
  const key = timerKey(index, time.seconds);
  return session.timers.find((t) => t.key === key);
}

/**
 * @param {string} text
 * @param {string} className
 * @param {string} focusKey survives re-renders, so focus does too
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function button(text, className, focusKey, onClick) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = className;
  el.dataset.focus = focusKey;
  el.textContent = text;
  el.addEventListener("click", onClick);
  return el;
}
