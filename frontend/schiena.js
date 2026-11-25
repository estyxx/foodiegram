"use strict";

// --- Routine: fetched from the server (single source), cached offline -----
let CATEGORIES = [];
let FLAT = [];

function buildFlat() {
  FLAT = CATEGORIES.flatMap((cat) =>
    cat.exercises.map((ex) => ({
      id: ex.id,
      name: ex.name,
      pose: ex.pose,
      reps: ex.reps,
      tip: ex.tip,
      category: cat.name,
      color: cat.color,
      tint: cat.tint,
      note: cat.note,
    })),
  );
}

const ROUTINE_CACHE_KEY = "schiena-routine";

// Fetch the catalogue once; fall back to the last cached copy offline.
async function loadRoutine() {
  try {
    const res = await fetch("/api/exercise-log/routine");
    if (!res.ok) throw new Error("routine " + res.status);
    CATEGORIES = await res.json();
    try {
      localStorage.setItem(ROUTINE_CACHE_KEY, JSON.stringify(CATEGORIES));
    } catch (e) {
      // storage blocked; the in-memory copy still serves this session.
    }
  } catch (e) {
    try {
      const cached = localStorage.getItem(ROUTINE_CACHE_KEY);
      CATEGORIES = cached ? JSON.parse(cached) : [];
    } catch (e2) {
      CATEGORIES = [];
    }
  }
  buildFlat();
}

// --- Sections by body position ------------------------------------
// Names, not copies: a section is a filtered view of the catalogue above, in
// catalogue order (so Strengthen stays easy → hard). Exercises done on all
// fours, seated or in a plank fit neither section.
const POSITIONS = [
  {
    id: "standing",
    label: "In piedi",
    names: [
      "Hip Extension",
      "Forward Bend",
      "Marching",
      "Hip Up and Out",
      "Shoulder Blade Squeeze",
      "Standing Bow and Arrow",
      "Split Stance Hip Hinge",
      "Forward Bend Hip Hinge",
      "Squat",
      "Jefferson Curl",
      "Exercise Top End",
      "Lunge and Twist",
    ],
  },
  {
    id: "lying",
    label: "Sdraiata",
    names: [
      "Pelvic Lift",
      "Knee Rolling",
      "Hip Flex",
      "Knees to Chest",
      "Front Lying Back Lift",
      "Leg Cross Overs",
      "Static Glutes",
      "Bilateral Bridge",
      "Offset Bridge",
      "Superman",
      "Deadbug",
    ],
  },
];

for (const position of POSITIONS) {
  for (const name of position.names) {
    if (!FLAT.some((ex) => ex.name === name)) {
      console.warn("unknown exercise in " + position.id + ": " + name);
    }
  }
}

const MODE_LABELS = { breve: "Giro breve", completo: "Sessione completa" };
for (const position of POSITIONS) MODE_LABELS[position.id] = position.label;

// --- Stick-figure poses (inline SVG, no assets) ------------------------
const SVGNS = "http://www.w3.org/2000/svg";
const POSES = {
  supineBent: {
    c: [[18, 55, 7]],
    d: [
      "M25 55 H55",
      "M55 55 L70 40 L70 75",
      "M55 55 L75 55 L88 40 L88 75",
      "M30 50 L35 40",
    ],
  },
  supineTabletop: {
    c: [[18, 60, 7]],
    d: [
      "M25 60 H60",
      "M60 60 L68 35 L85 30",
      "M60 60 L70 40 L60 25",
      "M30 55 L15 40",
    ],
  },
  seatedForward: {
    c: [[55, 45, 7]],
    faint: ["M40 80 H90 M40 80 V50 M90 80 V50"],
    d: ["M55 52 L70 65", "M70 65 L55 85", "M70 65 L90 85", "M62 58 L45 85"],
  },
  standingLegBack: {
    c: [[55, 20, 7]],
    d: [
      "M55 27 V55",
      "M55 35 L35 45",
      "M55 35 L75 25",
      "M55 55 L45 85",
      "M55 55 L75 70 L90 60",
    ],
  },
  standingForwardFold: {
    c: [[70, 30, 7]],
    d: [
      "M67 36 Q50 55 40 75",
      "M40 75 L38 90",
      "M60 55 L35 65",
      "M55 90 V60 M70 90 V60",
    ],
  },
  proneExtend: {
    c: [[85, 45, 7]],
    d: [
      "M78 48 Q55 55 30 50",
      "M85 52 L95 65",
      "M78 45 L95 35",
      "M35 52 L20 45",
      "M35 52 L20 60",
    ],
  },
  quadruped: {
    c: [[90, 40, 7]],
    d: [
      "M83 42 Q55 40 30 60",
      "M83 48 L83 75",
      "M45 55 L38 78",
      "M30 60 L25 75",
    ],
  },
  childPose: {
    c: [[22, 35, 7]],
    d: ["M85 70 Q60 75 45 65 Q35 60 25 40", "M85 70 L85 55", "M45 65 L45 55"],
  },
  sideLying: {
    c: [[20, 45, 7]],
    d: ["M27 47 H65", "M65 47 L90 40", "M65 50 L88 60"],
  },
  standingKneeUp: {
    c: [[60, 20, 7]],
    d: [
      "M60 27 V55",
      "M60 55 L45 60 L48 40",
      "M60 55 L70 85",
      "M60 35 L45 30",
      "M60 35 L75 45",
    ],
  },
  standingSqueeze: {
    c: [[60, 20, 7]],
    d: [
      "M60 27 V70",
      "M60 35 L40 25",
      "M60 35 L80 25",
      "M60 70 L48 95 M60 70 L72 95",
    ],
  },
  lungeSquat: {
    c: [[55, 18, 7]],
    d: [
      "M55 25 V50",
      "M55 30 L35 40 M55 30 L75 40",
      "M55 50 L35 65 L30 90",
      "M55 50 L78 60 L85 40",
    ],
  },
  plank: {
    c: [[95, 50, 7]],
    d: ["M88 52 L25 62", "M90 58 L90 75 M78 60 L78 75", "M25 62 L20 50"],
  },
};

function strokeAttrs(node, faint) {
  node.setAttribute("fill", "none");
  node.setAttribute("stroke", "#44403c");
  node.setAttribute("stroke-width", "3.2");
  node.setAttribute("stroke-linecap", "round");
  node.setAttribute("stroke-linejoin", "round");
  if (faint) node.setAttribute("stroke-opacity", "0.35");
}

function poseSvg(id) {
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", "0 0 120 100");
  svg.setAttribute("class", "pose");
  svg.setAttribute("aria-hidden", "true");
  const spec = POSES[id];
  if (!spec) return svg;
  for (const d of spec.faint || []) {
    const p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", d);
    strokeAttrs(p, true);
    svg.appendChild(p);
  }
  for (const circle of spec.c || []) {
    const el = document.createElementNS(SVGNS, "circle");
    el.setAttribute("cx", String(circle[0]));
    el.setAttribute("cy", String(circle[1]));
    el.setAttribute("r", String(circle[2]));
    strokeAttrs(el, false);
    svg.appendChild(el);
  }
  for (const d of spec.d || []) {
    const p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", d);
    strokeAttrs(p, false);
    svg.appendChild(p);
  }
  return svg;
}

// --- DOM helper --------------------------------------------------------
function el(tag, opts, children) {
  const node = document.createElement(tag);
  opts = opts || {};
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = opts.text;
  if (opts.onClick) node.addEventListener("click", opts.onClick);
  if (opts.style) Object.assign(node.style, opts.style);
  if (opts.attrs) {
    for (const key of Object.keys(opts.attrs)) {
      node.setAttribute(key, opts.attrs[key]);
    }
  }
  for (const child of children || []) {
    if (child) node.appendChild(child);
  }
  return node;
}

// --- Persistence: today's position per category ----------------------
// Every day starts again from the first (easiest) exercise of every
// category, so the saved position is stamped with its day and ignored once
// that day is over.
const ROTATION_KEY = "esercizi-schiena-rotation";
const DEFAULT_ROTATION = { Mobilize: 0, Move: 0, Strengthen: 0, Activate: 0 };

// Local calendar day (YYYY-MM-DD) — the day the user lives, not UTC.
function dayKey(date) {
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return date.getFullYear() + "-" + mm + "-" + dd;
}

function loadRotation(day) {
  try {
    const raw = localStorage.getItem(ROTATION_KEY);
    if (!raw) return Object.assign({}, DEFAULT_ROTATION);
    const parsed = JSON.parse(raw);
    // Stale day, or the pre-daily shape without a date: start from the top.
    if (!parsed || parsed.date !== day) return Object.assign({}, DEFAULT_ROTATION);
    return Object.assign({}, DEFAULT_ROTATION, parsed.rotation);
  } catch (err) {
    return Object.assign({}, DEFAULT_ROTATION);
  }
}

function saveRotation(day, next) {
  try {
    localStorage.setItem(
      ROTATION_KEY,
      JSON.stringify({ date: day, rotation: next }),
    );
  } catch (err) {
    // private mode / storage disabled — the session still works in memory
  }
}

// --- Completion log: queued in the browser, flushed to the API -------
// Each "Fatto" is queued first and then sent, so a flaky connection never
// loses a tap. client_id makes a retried send idempotent on the server,
// while two real repeats of the same exercise stay two entries.
const LOG_URL = "/api/exercise-log";
const PENDING_KEY = "esercizi-schiena-pending";

function loadPending() {
  try {
    const raw = localStorage.getItem(PENDING_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    return [];
  }
}

function savePending() {
  try {
    localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  } catch (err) {
    // storage disabled — the queue still lives in memory for this page
  }
}

function newClientId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12);
}

// --- State ----------------------------------------------------------
let mode = null; // null | "breve" | "completo"
let today = dayKey(new Date());
let rotation = loadRotation(today);
let index = 0;
let done = new Set();
let pending = loadPending(); // taps not yet confirmed by the server
let todayLog = []; // server-confirmed completions for `today`
let flushing = false;
// Server-confirmed completions per week, keyed by that week's Monday. Visited
// weeks render instantly and are refreshed in the background.
const weekCache = new Map();
let weekOffset = 0; // weeks back from the current one (0 = this week)
let weekError = false; // the viewed week could not be loaded

function currentList() {
  if (mode === "breve") {
    return CATEGORIES.map((cat) => {
      const i = rotation[cat.name] % cat.exercises.length;
      const ex = cat.exercises[i];
      return {
        id: ex.id,
        name: ex.name,
        pose: ex.pose,
        reps: ex.reps,
        tip: ex.tip,
        category: cat.name,
        color: cat.color,
        tint: cat.tint,
        note: cat.note,
      };
    });
  }
  const position = POSITIONS.find((p) => p.id === mode);
  if (position) return FLAT.filter((ex) => position.names.includes(ex.name));
  return FLAT;
}

// Pending taps from today that the server has not echoed back yet.
function queuedToday() {
  const confirmed = new Set(todayLog.map((e) => e.client_id));
  return pending.filter((e) => e.done_on === today && !confirmed.has(e.client_id));
}

function doneTodayCount(name) {
  const confirmed = todayLog.filter((e) => e.exercise === name).length;
  return confirmed + queuedToday().filter((e) => e.exercise === name).length;
}

function doneTodayTotal() {
  return todayLog.length + queuedToday().length;
}

// --- Server sync ----------------------------------------------------
async function flushPending() {
  if (flushing) return;
  flushing = true;
  try {
    while (pending.length > 0) {
      const entry = pending[0];
      const res = await fetch(LOG_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry),
      });
      if (res.status === 422) {
        // Can never succeed; drop it rather than wedge everything behind it.
        console.warn("exercise log rejected", entry);
        pending.shift();
        savePending();
        continue;
      }
      if (!res.ok) break; // keep it queued; retried on the next tap / load
      const saved = await res.json();
      pending.shift();
      savePending();
      const known = todayLog.some((e) => e.client_id === saved.client_id);
      if (saved.done_on === today && !known) todayLog.push(saved);
      const cached = weekCache.get(dayKey(weekStartOf(saved.done_on)));
      if (cached && !cached.some((e) => e.client_id === saved.client_id)) {
        cached.push(saved);
      }
    }
  } catch (err) {
    // offline: leave the queue as is
  } finally {
    flushing = false;
    paint();
  }
}

async function refreshToday() {
  const day = today;
  try {
    const res = await fetch(LOG_URL + "?day=" + encodeURIComponent(day));
    if (res.status === 401) {
      // Signed out: the web login returns here. Without it (Basic auth)
      // the body carries no login_url and nothing happens.
      const body = await res.json().catch(() => null);
      if (body && body.login_url === "/auth/login") {
        window.location.assign("/auth/login?next=/schiena.html");
      }
      return;
    }
    if (!res.ok || day !== today) return;
    todayLog = await res.json();
    paint();
  } catch (err) {
    // offline: counts fall back to what is queued locally
  }
}

// --- Week view helpers (weeks run Monday to Sunday) -----------------
function parseDay(key) {
  const parts = key.split("-").map(Number);
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function addDays(date, n) {
  const copy = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  copy.setDate(copy.getDate() + n);
  return copy;
}

function weekStartOf(key) {
  const date = parseDay(key);
  return addDays(date, -((date.getDay() + 6) % 7));
}

function viewedWeekStart() {
  return addDays(weekStartOf(today), weekOffset * 7);
}

async function refreshWeek() {
  const startKey = dayKey(viewedWeekStart());
  const endKey = dayKey(addDays(viewedWeekStart(), 6));
  try {
    const res = await fetch(LOG_URL + "/range?start=" + startKey + "&end=" + endKey);
    if (!res.ok) throw new Error("status " + res.status);
    const rows = await res.json();
    weekCache.set(startKey, rows);
    if (startKey === dayKey(viewedWeekStart())) weekError = false;
  } catch (err) {
    // offline: the week falls back to what is cached or queued locally
    if (startKey === dayKey(viewedWeekStart())) weekError = true;
  }
  if (startKey === dayKey(viewedWeekStart())) paint();
}

function shiftWeek(delta) {
  const next = Math.min(0, weekOffset + delta); // never into the future
  if (next === weekOffset) return;
  weekOffset = next;
  weekError = false;
  paint();
  refreshWeek();
}

function weekLoaded() {
  return weekCache.has(dayKey(viewedWeekStart()));
}

// Confirmed + still-queued completions that fall in the viewed week.
function weekEntries() {
  const start = viewedWeekStart();
  const lo = dayKey(start);
  const hi = dayKey(addDays(start, 6));
  const inWeek = (e) => e.done_on >= lo && e.done_on <= hi;
  const confirmed = (weekCache.get(lo) || []).filter(inWeek);
  const known = new Set(confirmed.map((e) => e.client_id));
  const queued = pending.filter((e) => inWeek(e) && !known.has(e.client_id));
  return confirmed.concat(queued);
}

// A new calendar day: position back to the start, today's log re-read.
function syncDay() {
  const day = dayKey(new Date());
  if (day === today) return;
  today = day;
  rotation = Object.assign({}, DEFAULT_ROTATION);
  saveRotation(today, rotation);
  todayLog = [];
  weekCache.clear();
  weekOffset = 0;
  weekError = false;
  refreshToday();
}

// --- Actions ------------------------------------------------------
function startMode(next) {
  syncDay();
  mode = next;
  index = 0;
  done = new Set();
  render();
}

function markDone() {
  const ex = currentList()[index];
  if (ex) {
    const now = new Date();
    pending.push({
      client_id: newClientId(),
      exercise_id: ex.id,
      exercise: ex.name,
      category: ex.category,
      done_on: dayKey(now),
      completed_at: now.toISOString(),
    });
    savePending();
    flushPending();
  }
  done.add(index);
  index += 1;
  render();
}

function skip() {
  index += 1;
  render();
}

function adjustDifficulty(categoryName, delta) {
  const cat = CATEGORIES.find((c) => c.name === categoryName);
  if (!cat) return;
  const max = cat.exercises.length - 1;
  const value = Math.min(max, Math.max(0, rotation[categoryName] + delta));
  rotation = Object.assign({}, rotation, { [categoryName]: value });
  saveRotation(today, rotation);
  render();
}

function backToMenu() {
  // Leaving mid-round (or from another section) must not skip an exercise.
  if (mode === "breve" && index >= currentList().length) {
    const next = Object.assign({}, rotation);
    for (const name of ["Mobilize", "Move"]) {
      const cat = CATEGORIES.find((c) => c.name === name);
      next[name] = (rotation[name] + 1) % cat.exercises.length;
    }
    rotation = next;
    saveRotation(today, rotation);
  }
  mode = null;
  index = 0;
  done = new Set();
  render();
}

function openStats() {
  syncDay();
  weekOffset = 0;
  weekError = false;
  mode = "stats";
  render();
  refreshWeek();
}

function resetProgress(evt) {
  const ok = window.confirm(
    "Riparto da capo per oggi? Rotazione e livelli tornano al primo esercizio. " +
      "Il registro degli esercizi fatti resta com'è.",
  );
  if (!ok) return;
  rotation = Object.assign({}, DEFAULT_ROTATION);
  saveRotation(today, rotation);
  const btn = evt.currentTarget;
  btn.textContent = "Ripartito da capo ✓";
  btn.disabled = true;
}

// --- Screens ----------------------------------------------------
// Every screen except the menu starts with the way back, plus where you are.
function topBar(label) {
  return el("div", { class: "topbar" }, [
    el("button", { class: "topbar__back", text: "← Menu", onClick: backToMenu }),
    el("span", { class: "topbar__ctx", text: label || "" }),
  ]);
}

function todaySummary() {
  const total = doneTodayTotal();
  const waiting = pending.length;
  const base =
    total === 0
      ? "Oggi: ancora niente"
      : "Oggi: " + total + (total === 1 ? " esercizio fatto" : " esercizi fatti");
  return waiting > 0 ? base + " · " + waiting + " da sincronizzare" : base;
}

const DAY_LABELS = ["L", "M", "M", "G", "V", "S", "D"];
const DAY_NAMES = [
  "lunedì",
  "martedì",
  "mercoledì",
  "giovedì",
  "venerdì",
  "sabato",
  "domenica",
];

function categoryColor(name) {
  const cat = CATEGORIES.find((c) => c.name === name);
  return cat ? cat.color : "#a8a29e";
}

function timeLabel(iso) {
  return new Date(iso).toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function countLabel(n) {
  return n + (n === 1 ? " esercizio" : " esercizi");
}

// Today's completions folded by exercise: name, category, one time per tap.
function groupByExercise(entries) {
  const groups = [];
  const byName = new Map();
  for (const e of entries) {
    let group = byName.get(e.exercise);
    if (!group) {
      group = { name: e.exercise, category: e.category, times: [] };
      byName.set(e.exercise, group);
      groups.push(group);
    }
    group.times.push(timeLabel(e.completed_at));
  }
  return groups;
}

function todaySection(entries) {
  const children = [
    el("h2", { class: "stats__h", text: "Oggi" }),
    el("p", {
      class: "stats__sub",
      text: parseDay(today).toLocaleDateString("it-IT", {
        weekday: "long",
        day: "numeric",
        month: "long",
      }),
    }),
  ];
  if (entries.length === 0) {
    children.push(
      el("p", {
        class: "stats__empty",
        text: "Ancora niente oggi. Un giro breve dura ~2 minuti.",
      }),
    );
    return el("section", { class: "stats__card" }, children);
  }
  children.push(el("p", { class: "stats__big", text: countLabel(entries.length) }));
  const list = el("ul", { class: "stats__list" });
  for (const group of groupByExercise(entries)) {
    list.appendChild(
      el("li", { class: "stats__row" }, [
        el("span", {
          class: "stats__dot",
          style: { backgroundColor: categoryColor(group.category) },
          attrs: { "aria-hidden": "true" },
        }),
        el("span", { class: "stats__name", text: group.name }),
        el("span", { class: "stats__count", text: "×" + group.times.length }),
        el("span", { class: "stats__times", text: group.times.join(" · ") }),
      ]),
    );
  }
  children.push(list);
  return el("section", { class: "stats__card" }, children);
}

function weekSection(entries) {
  const start = viewedWeekStart();
  const days = [];
  for (let i = 0; i < 7; i++) {
    const key = dayKey(addDays(start, i));
    days.push({ key, count: entries.filter((e) => e.done_on === key).length });
  }
  const peak = Math.max(1, ...days.map((d) => d.count));
  const activeDays = days.filter((d) => d.count > 0).length;

  const bars = el("div", { class: "bars" });
  days.forEach((d, i) => {
    const isToday = d.key === today;
    const height = d.count === 0 ? 0 : Math.max(8, Math.round((d.count / peak) * 100));
    bars.appendChild(
      el(
        "div",
        {
          class: "bar" + (d.key > today ? " bar--future" : ""),
          attrs: { role: "img", "aria-label": DAY_NAMES[i] + ": " + d.count },
        },
        [
          el("span", { class: "bar__n", text: d.count > 0 ? String(d.count) : "" }),
          el("div", { class: "bar__track" }, [
            el("div", {
              class: "bar__fill" + (isToday ? " bar__fill--today" : ""),
              style: { height: height + "%" },
            }),
          ]),
          el("span", {
            class: "bar__d" + (isToday ? " bar__d--today" : ""),
            text: DAY_LABELS[i],
          }),
        ],
      ),
    );
  });

  const perCategory = CATEGORIES.map((cat) => ({
    name: cat.name,
    color: cat.color,
    count: entries.filter((e) => e.category === cat.name).length,
  }));
  const topCount = Math.max(1, ...perCategory.map((c) => c.count));
  const cats = el("ul", { class: "stats__list" });
  for (const cat of perCategory) {
    cats.appendChild(
      el("li", { class: "catrow" }, [
        el("span", { class: "catrow__name", text: cat.name }),
        el("span", { class: "catrow__track" }, [
          el("span", {
            class: "catrow__fill",
            style: {
              width: Math.round((cat.count / topCount) * 100) + "%",
              backgroundColor: cat.color,
            },
          }),
        ]),
        el("span", { class: "catrow__n", text: String(cat.count) }),
      ]),
    );
  }

  const range =
    start.toLocaleDateString("it-IT", { day: "numeric", month: "short" }) +
    " – " +
    addDays(start, 6).toLocaleDateString("it-IT", {
      day: "numeric",
      month: "short",
    });
  // Never show a made-up zero for a week we could not read.
  let summary =
    countLabel(entries.length) +
    " · " +
    activeDays +
    (activeDays === 1 ? " giorno" : " giorni") +
    " su 7";
  if (!weekLoaded()) summary = weekError ? "Dati non disponibili" : "Carico…";

  let title = "Questa settimana";
  if (weekOffset === -1) title = "Settimana scorsa";
  else if (weekOffset < -1) title = -weekOffset + " settimane fa";

  const next = el("button", {
    class: "weeknav__btn",
    text: "›",
    onClick: () => shiftWeek(1),
    attrs: { "aria-label": "Settimana successiva" },
  });
  next.disabled = weekOffset === 0;
  const nav = el("div", { class: "weeknav" }, [
    el("button", {
      class: "weeknav__btn",
      text: "‹",
      onClick: () => shiftWeek(-1),
      attrs: { "aria-label": "Settimana precedente" },
    }),
    el("div", { class: "weeknav__mid" }, [
      el("h2", { class: "stats__h", text: title }),
      el("p", { class: "stats__sub", text: range }),
    ]),
    next,
  ]);

  const children = [nav];
  if (weekOffset < 0) {
    children.push(
      el("button", {
        class: "weeknav__now",
        text: "Torna a questa settimana",
        onClick: () => shiftWeek(-weekOffset),
      }),
    );
  }
  children.push(el("p", { class: "stats__big", text: summary }), bars, cats);
  return el("section", { class: "stats__card" }, children);
}

function statsScreen() {
  const entries = weekEntries();
  const waiting = pending.length;
  const children = [
    topBar(""),
    el("h1", { class: "title", text: "Progressi" }),
    weekOffset === 0 ? todaySection(entries.filter((e) => e.done_on === today)) : null,
    weekSection(entries),
  ];
  if (weekError) {
    children.push(
      el("p", {
        class: "stats__empty",
        text: "Non riesco a caricare questa settimana dal server. Riprova tra poco.",
      }),
    );
  }
  if (waiting > 0) {
    children.push(
      el("p", {
        class: "stats__empty",
        text: waiting + " da sincronizzare — compaiono qui appena torni online.",
      }),
    );
  }
  return el("div", { class: "screen" }, children);
}

function menuScreen() {
  return el("div", { class: "screen" }, [
    el("a", {
      class: "backlink",
      text: "← Dispensa",
      attrs: { href: "/" },
    }),
    el("h1", { class: "title", text: "Esercizi schiena" }),
    el("p", {
      class: "lede",
      text:
        "Il giro breve tocca tutte e 4 le categorie in poche mosse — fallo a ogni pausa. " +
        "Strengthen e Activate non avanzano da soli: dici tu «più difficile». " +
        "Ogni giorno si riparte dal primo esercizio di ogni categoria.",
    }),
    el("p", { class: "today", text: todaySummary() }),
    el("button", { class: "big big--dark", onClick: () => startMode("breve") }, [
      el("span", { class: "big__label", text: "Giro breve" }),
      el("span", {
        class: "big__sub",
        text: "1 esercizio per categoria · ~2 min",
      }),
    ]),
    el(
      "button",
      { class: "big big--light", onClick: () => startMode("completo") },
      [
        el("span", { class: "big__label", text: "Sessione completa" }),
        el("span", {
          class: "big__sub",
          text: "Tutti i " + FLAT.length + " esercizi in sequenza",
        }),
      ],
    ),
    el(
      "div",
      { class: "pair" },
      POSITIONS.map((position) =>
        el(
          "button",
          { class: "big big--light", onClick: () => startMode(position.id) },
          [
            el("span", { class: "big__label", text: position.label }),
            el("span", {
              class: "big__sub",
              text: position.names.length + " esercizi",
            }),
          ],
        ),
      ),
    ),
    el("button", { class: "big big--light", onClick: openStats }, [
      el("span", { class: "big__label", text: "Progressi" }),
      el("span", { class: "big__sub", text: "Cosa hai fatto oggi e questa settimana" }),
    ]),
    el("button", {
      class: "linkbtn",
      text: "Riparti da capo (oggi)",
      onClick: resetProgress,
    }),
  ]);
}

function progressBar(list) {
  const bar = el("div", {
    class: "progress",
    attrs: { role: "progressbar", "aria-label": "Avanzamento sessione" },
  });
  list.forEach((_, i) => {
    const dot = el("div", { class: "progress__dot" });
    dot.style.backgroundColor = done.has(i)
      ? "#44403c"
      : i === index
        ? "#d6d3d1"
        : "#e7e5e4";
    bar.appendChild(dot);
  });
  return bar;
}

function exerciseCard(ex) {
  const body = el("div", { class: "card__body" }, [
    el("h2", { class: "card__name", text: ex.name }),
    el("p", { class: "card__reps", text: ex.reps }),
  ]);
  const times = doneTodayCount(ex.name);
  if (times > 0) {
    body.appendChild(
      el("p", {
        class: "card__today",
        text: "Fatto " + times + (times === 1 ? " volta" : " volte") + " oggi",
      }),
    );
  }

  if (ex.tip) {
    body.appendChild(
      el("div", { class: "tip" }, [
        el("span", {
          class: "tip__icon",
          text: "⚠",
          attrs: { "aria-hidden": "true" },
        }),
        el("p", { class: "tip__text", text: ex.tip }),
      ]),
    );
  }

  const manual =
    mode === "breve" &&
    (ex.category === "Strengthen" || ex.category === "Activate");
  if (manual) {
    body.appendChild(
      el("div", { class: "difficulty" }, [
        el("button", {
          class: "difficulty__btn",
          text: "◀ più facile",
          onClick: () => adjustDifficulty(ex.category, -1),
        }),
        el("button", {
          class: "difficulty__btn",
          text: "più difficile ▶",
          onClick: () => adjustDifficulty(ex.category, 1),
        }),
      ]),
    );
  }

  return el("div", { class: "card", style: { backgroundColor: ex.tint } }, [
    el("div", {
      class: "card__figure",
      style: { backgroundColor: ex.color + "18" },
    }, [poseSvg(ex.pose)]),
    body,
  ]);
}

function finishScreen(list) {
  const box = el("div", { class: "finish" }, [
    el("p", {
      class: "finish__check",
      text: "✓",
      attrs: { "aria-hidden": "true" },
    }),
    el("h2", { class: "finish__title", text: "Fatto per oggi" }),
    el("p", {
      class: "finish__count",
      text: done.size + " di " + list.length + " esercizi completati",
    }),
  ]);
  if (mode === "breve") {
    box.appendChild(
      el("p", {
        class: "finish__hint",
        text:
          "Al prossimo giro breve, Mobilize e Move passano agli esercizi successivi in rotazione. " +
          "Strengthen e Activate restano al livello attuale. Domani si riparte da capo.",
      }),
    );
  }
  return el("div", { class: "screen" }, [
    topBar(MODE_LABELS[mode]),
    progressBar(list),
    box,
    el("button", {
      class: "big big--light",
      text: "↺  Torna al menu",
      onClick: backToMenu,
    }),
  ]);
}

function sessionScreen() {
  const list = currentList();
  if (index >= list.length) return finishScreen(list);

  const ex = list[index];
  const badgeRow = el("div", { class: "badge-row" }, [
    el("span", {
      class: "badge",
      text: ex.category,
      style: { backgroundColor: ex.color },
    }),
  ]);
  if (ex.note) {
    badgeRow.appendChild(el("p", { class: "note", text: ex.note }));
  }

  return el("div", { class: "screen" }, [
    topBar(MODE_LABELS[mode]),
    progressBar(list),
    badgeRow,
    exerciseCard(ex),
    el("button", {
      class: "big big--dark done-btn",
      text: "✓  Fatto",
      onClick: markDone,
    }),
    el("button", {
      class: "linkbtn",
      text: "Salta per oggi",
      onClick: skip,
    }),
    el("p", {
      class: "counter",
      text: index + 1 + " di " + list.length,
    }),
  ]);
}

// --- Mount ----------------------------------------------------
const root = document.getElementById("app");

// paint() redraws in place; render() is for navigation and resets scroll.
function paint() {
  let screen = sessionScreen();
  if (mode === null) screen = menuScreen();
  else if (mode === "stats") screen = statsScreen();
  root.replaceChildren(screen);
}

function render() {
  if (mode === null) syncDay();
  paint();
  window.scrollTo(0, 0);
}

// A phone keeps the page alive in the background: on return, re-check the
// day, re-read today's log and send anything still queued.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  if (mode === null) syncDay();
  refreshToday();
  if (mode === "stats") refreshWeek();
  flushPending();
  if (mode === null) paint();
});

// Load the catalogue (or its offline cache), then paint.
loadRoutine().then(() => {
  render();
  refreshToday();
  flushPending();
});
