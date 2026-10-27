// @ts-check

/**
 * The Shortcut the owner creates once on the iPhone: "Start Timer" for the
 * Shortcut Input, in seconds. A web page cannot ring while the phone is locked
 * or on silent; the system Clock timer can.
 */
export const PHONE_SHORTCUT_NAME = "Dispensa Timer";

/**
 * Whether this device has the Shortcuts app (iPhone, iPad — including iPads
 * that report themselves as a Mac).
 * @returns {boolean}
 */
export function canSetPhoneTimer() {
  const ua = navigator.userAgent;
  return /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
}

/**
 * The Shortcuts URL that starts the Clock timer for `seconds`.
 * @param {number} seconds
 * @returns {string}
 */
export function phoneTimerUrl(seconds) {
  const name = encodeURIComponent(PHONE_SHORTCUT_NAME);
  const text = String(Math.max(1, Math.round(seconds)));
  return `shortcuts://run-shortcut?name=${name}&input=text&text=${text}`;
}
