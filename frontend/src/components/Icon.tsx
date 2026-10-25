// Small stroke icons drawn for chess-o on a 24px grid; they inherit the text colour.
const PATHS = {
  retry: "M4 12a8 8 0 1 0 2.4-5.7 M4 4v4.5h4.5",
  bulb: "M9 18h6 M10 21h4 M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z",
  eyeOff: "M3 3l18 18 M10.6 6.1A9.8 9.8 0 0 1 12 6c5 0 8.5 4 9.5 6a13 13 0 0 1-2.7 3.4 M6.3 7.6A13 13 0 0 0 2.5 12c1 2 4.5 6 9.5 6 1.5 0 2.9-.4 4.1-1 M9.9 10a3 3 0 0 0 4.1 4.1",
  next: "M5 12h14 M13 6l6 6-6 6",
  back: "M19 12H5 M11 6l-6 6 6 6",
  first: "M6 5v14 M18 6l-7 6 7 6",
  prev: "M15 6l-6 6 6 6",
  fwd: "M9 6l6 6-6 6",
  last: "M18 5v14 M6 6l7 6-7 6",
  list: "M9 6h11 M9 12h11 M9 18h11 M4.5 6h.01 M4.5 12h.01 M4.5 18h.01",
  soundOn: "M4 9.5h3.5L12 5.5v13l-4.5-4H4z M16 9a4 4 0 0 1 0 6 M18.6 6.4a7.5 7.5 0 0 1 0 11.2",
  soundOff: "M4 9.5h3.5L12 5.5v13l-4.5-4H4z M16.5 9.5l5 5 M21.5 9.5l-5 5",
  flip: "M7 4v16 M3.5 16.5L7 20l3.5-3.5 M17 20V4 M13.5 7.5L17 4l3.5 3.5",
  play: "M7 4.5v15l12-7.5z",
  key: "M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4l-5.3 3 1.2-6-4.5-4.1 6-.7z",
  upload: "M12 16V4 M7 9l5-5 5 5 M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4",
  search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z M15.3 15.3L20 20",
  download: "M12 4v12 M7 11l5 5 5-5 M4 20h16",
  plus: "M12 5v14 M5 12h14",
  board: "M4 4h16v16H4z M4 12h16 M12 4v16 M4 4h8v8H4z M12 12h8v8h-8z",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M12 12h.01",
  sync: "M20 11a8 8 0 0 0-14.3-4.3L4 8.5 M4 4v4.5h4.5 M4 13a8 8 0 0 0 14.3 4.3l1.7-1.8 M20 20v-4.5h-4.5",
  unlink: "M9.5 14.5l5-5 M10 6.5l1.4-1.4a4 4 0 0 1 5.6 5.6L15.5 12 M8.5 12l-1.4 1.4a4 4 0 0 0 5.6 5.6l1.4-1.4 M3 3l3 3 M18 18l3 3",
  trash: "M4 7h16 M10 11v6 M14 11v6 M6 7l1 13h10l1-13 M9 7V4h6v3",
  send: "M4 12l16-8-6 16-2.5-6.5z M11.5 13.5L20 4",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4.5 20a7.5 7.5 0 0 1 15 0",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M12 2.5v2 M12 19.5v2 M2.5 12h2 M19.5 12h2 M5.3 5.3l1.4 1.4 M17.3 17.3l1.4 1.4 M5.3 18.7l1.4-1.4 M17.3 6.7l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z",
  monitor: "M3.5 5h17v11h-17z M9 20h6 M12 16v4",
  eye: "M2.5 12C3.5 10 7 6 12 6s8.5 4 9.5 6c-1 2-4.5 6-9.5 6s-8.5-4-9.5-6z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  check: "M5 12.5l4.5 4.5L19 7.5",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 17 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill={name === "play" ? "currentColor" : "none"}
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
