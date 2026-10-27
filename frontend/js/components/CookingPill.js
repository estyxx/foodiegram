// @ts-check

import { formatClock } from "../lib/cookingSteps.js";
import {
  getSession,
  resumeCooking,
  subscribe,
  timerRemaining,
} from "../lib/cookingSession.js";

/**
 * The corner button left behind when cooking mode is closed with timers
 * still set: shows the most urgent one and takes you back. Mounted once.
 * @returns {HTMLButtonElement}
 */
export function CookingPill() {
  const pill = document.createElement("button");
  pill.type = "button";
  pill.className = "cook-pill";
  pill.hidden = true;

  const clock = document.createElement("span");
  clock.className = "cook-pill__clock";
  const label = document.createElement("span");
  label.className = "cook-pill__label";
  pill.append(clock, label);

  pill.addEventListener("click", () => {
    const session = getSession();
    if (session === null) {
      return;
    }
    window.location.hash = `#recipe/${encodeURIComponent(session.recipe.code)}`;
    resumeCooking();
  });

  subscribe((event) => {
    if (event.type !== "announce") {
      paint();
    }
  });

  function paint() {
    const session = getSession();
    if (session === null || session.open || session.timers.length === 0) {
      pill.hidden = true;
      return;
    }
    const { timers } = session;
    const pick = timers.find((t) => t.done) ?? timers.find((t) => t.running) ?? timers[0];
    const more = timers.length - 1;
    pill.hidden = false;
    pill.classList.toggle("cook-pill--done", pick.done);
    clock.textContent = `⏱ ${
      pick.done ? "Time’s up" : formatClock(timerRemaining(pick, Date.now()))
    }`;
    label.textContent = `${pick.label}${more > 0 ? ` +${more}` : ""} · back to cooking`;
  }

  return pill;
}
