#!/usr/bin/env node
/**
 * Generate mock JSON for every /api/* endpoint into dashboard/public/mocks/.
 * Single source of truth for both dev-mode sample data (via the mock-api Vite
 * plugin) and production fallback when ClickHouse is unreachable (served as a
 * static asset under /mocks/<path>.json).
 *
 * Shapes match the Cloudflare Functions response — keep in sync when adding endpoints.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const MOCKS_ROOT = resolve(__dirname, '..', 'public', 'mocks');

const DAYS = 90;
const TODAY = new Date('2026-05-21T12:00:00Z');

// Tiny seeded PRNG so output is stable across runs.
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}
const rand = rng(42);
const pick = (arr) => arr[Math.floor(rand() * arr.length)];
const between = (lo, hi) => lo + Math.floor(rand() * (hi - lo + 1));
const round1 = (n) => Math.round(n * 10) / 10;

/**
 * Per-item 30-day trend for TopList sparklines. Bell-curve around a random
 * peak position with varying width and a noise floor — gives each item a
 * visually distinct shape (rising, falling, spiky, steady) without us
 * pre-defining patterns by hand.
 */
function generateTrend(days = 30) {
  const peak = rand();                        // 0–1, position of peak
  const width = 0.18 + rand() * 0.35;         // 0.18–0.53, peak spread
  const baseline = rand() * 0.25;             // 0–0.25, off-peak floor
  return Array.from({ length: days }, (_, i) => {
    const x = i / (days - 1);
    const dist = (x - peak) / width;
    const bell = Math.exp(-(dist * dist));
    const noise = (rand() - 0.5) * 0.18;
    return Math.max(0, round1(baseline + bell + noise));
  });
}

function dateOffset(days) {
  const d = new Date(TODAY);
  d.setUTCDate(d.getUTCDate() - days);
  return d;
}
const isoDate = (d) => d.toISOString().slice(0, 10);

function write(relPath, data) {
  const full = join(MOCKS_ROOT, relPath);
  mkdirSync(dirname(full), { recursive: true });
  writeFileSync(full, JSON.stringify(data, null, 2));
  console.log(`  ${relPath}`);
}

// ---------- shared timeseries ----------
const dates = Array.from({ length: DAYS }, (_, i) => isoDate(dateOffset(DAYS - 1 - i)));
const spotifyDaily = dates.map(() => between(15, 80));
const youtubeDaily = dates.map(() => between(5, 35));
const calendarDaily = dates.map(() => between(2, 9));
const mapsDaily = dates.map(() => between(0, 12));

// Pre-computed Hours totals (used by both /api/overview/stats and the per-source pages).
const spotifyTimeseries = dates.map(() => round1(0.5 + rand() * 4.5));
const spotifyTotalHours = round1(spotifyTimeseries.reduce((a, b) => a + b, 0));
const youtubeTotalHours = round1(youtubeDaily.reduce((a, b) => a + b, 0) * 0.25);

const totalEvents =
  spotifyDaily.reduce((a, b) => a + b, 0) +
  youtubeDaily.reduce((a, b) => a + b, 0) +
  calendarDaily.reduce((a, b) => a + b, 0) +
  mapsDaily.reduce((a, b) => a + b, 0);

// ---------- /api/overview/stats ----------
write('overview/stats.json', {
  summary: {
    // Channel-tile headlines (Home cards)
    spotifyHours:    spotifyTotalHours,
    youtubeHours:    youtubeTotalHours,

    // Per-source secondary counts (still consumed elsewhere)
    songsStreamed:   spotifyDaily.reduce((a, b) => a + b, 0),
    artistsListened: 847,
    videosWatched:   youtubeDaily.reduce((a, b) => a + b, 0),
    youtubeChannels: 312,
    calendarEvents:  calendarDaily.reduce((a, b) => a + b, 0),
    citiesVisited:   24,
  },
  dataGeneration: {
    dates,
    spotify: spotifyDaily,
    youtube: youtubeDaily,
    calendar: calendarDaily,
    maps: mapsDaily,
    totalEvents,
    avgPerDay: Math.round(totalEvents / DAYS),
  },
  // Producer-console signatures — Home shows these as the "Console" row.
  console: {
    noisiestHour:           '14:00',
    noisiestHourEventCount: 42,
    quietStreakMinutes:     17,
    daysTracked:            DAYS,
    channelDominance: [
      { channel: 'spotify',  share: 0.42 },
      { channel: 'youtube',  share: 0.28 },
      { channel: 'maps',     share: 0.18 },
      { channel: 'calendar', share: 0.12 },
    ],
  },
  _meta: { cached: true, timestamp: TODAY.toISOString() },
});

// ---------- /api/spotify/* ----------
const ARTIST_NAMES = [
  'DOPE LEMON', 'Marlon Funaki', 'TABAL', 'kokoro', 'L\'IMPÉRATRICE', 'Khruangbin',
  'Men I Trust', 'Mac DeMarco', 'Tom Misch', 'Yussef Dayes', 'Nujabes', 'J Dilla',
  'Tycho', 'Bonobo', 'Floating Points', 'Four Tet', 'Aphex Twin', 'Boards of Canada',
  'Caribou', 'Burial', 'Jamie xx', 'Romare', 'Phaeleh', 'Emancipator',
  'Sleep Token', 'Polyphia', 'Plini', 'Animals as Leaders', 'Periphery', 'Tesseract',
];
const GENRES = [
  { name: 'lo-fi', weight: 12 },
  { name: 'lo-fi beats', weight: 9 },
  { name: 'electronic', weight: 8 },
  { name: 'indie', weight: 7 },
  { name: 'jazz', weight: 6 },
  { name: 'house', weight: 5 },
  { name: 'ambient', weight: 5 },
  { name: 'hip-hop', weight: 4 },
  { name: 'progressive metal', weight: 4 },
  { name: 'downtempo', weight: 3 },
  { name: 'funk', weight: 3 },
  { name: 'soul', weight: 2 },
];

const topArtists = ARTIST_NAMES.slice(0, 15).map((name, i) => ({
  rank: i + 1,
  name,
  plays: between(20, 80) - i * 2,
  hours: round1((between(20, 80) - i * 2) * 0.06),
  genre: pick(GENRES).name,
  trend: generateTrend(30),
}));

write('spotify/data.json', {
  kpis: {
    // Raw values; formatter applies units / separators in the UI.
    totalTime:     spotifyTotalHours,                              // hours (number)
    songsStreamed: spotifyDaily.reduce((a, b) => a + b, 0),        // count
    uniqueArtists: 847,                                            // count
    avgDaily:      round1(spotifyTotalHours / DAYS),               // hours
  },
  topArtists,
  genres: GENRES.map((g) => ({ name: g.name, value: g.weight * between(8, 14) })),
  timeSeries: { dates, values: spotifyTimeseries },
});

write('spotify/summary.json', {
  stats: [
    { label: 'Artists', value: 847 },
    { label: 'Songs', value: spotifyDaily.reduce((a, b) => a + b, 0) },
  ],
  totalHours: spotifyTotalHours,
});

const TRACK_NAMES = [
  'Butterfly\'s Journey', 'Falling Softly', 'Smooth Sailing', 'Midnight Drive',
  'Cosmic Drift', 'Honeycomb', 'Slow River', 'Paper Lanterns', 'Velvet Sky',
  'Glass Houses', 'Echo Chamber', 'Pacific Blue', 'Tangerine', 'Marigold',
  'Silver Lining', 'Quiet Storm', 'Northern Lights', 'Crystal Clear', 'Open Road',
  'Sunset Boulevard', 'Lazy Sunday', 'Afternoon Light', 'Coffee Break', 'Last Train',
];
const recentTracks = Array.from({ length: 10 }, (_, i) => {
  const playedAt = new Date(TODAY.getTime() - i * 4 * 60 * 1000);
  const artist = pick(ARTIST_NAMES);
  return {
    track: pick(TRACK_NAMES),
    artist,
    time: playedAt.toISOString(),
    albumArt: `https://picsum.photos/seed/${encodeURIComponent(artist)}/100`,
  };
});
write('spotify/recent.json', recentTracks);

// Offline state on purpose: the live card should show "not playing" when the
// warehouse is unreachable, not a fake currently-playing track.
write('spotify/current.json', {
  type: 'no_track',
  data: {
    is_playing: false,
    timestamp: '2026-01-01T00:00:00.000Z',
  },
});

// ---------- /api/youtube/data ----------
const CHANNEL_NAMES = [
  'Fireship', 'Theo - t3.gg', 'Web Dev Simplified', 'Lex Fridman', 'Veritasium',
  'Kurzgesagt', 'Two Minute Papers', 'ThePrimeagen', 'Coder Foundry', 'CGP Grey',
  '3Blue1Brown', 'Computerphile', 'Tom Scott', 'NileRed', 'Hardware Unboxed',
];
const CATEGORIES = [
  { name: 'Science & Technology', weight: 32 },
  { name: 'Education', weight: 22 },
  { name: 'Music', weight: 14 },
  { name: 'Entertainment', weight: 11 },
  { name: 'Gaming', weight: 9 },
  { name: 'News & Politics', weight: 6 },
  { name: 'Howto & Style', weight: 4 },
  { name: 'Comedy', weight: 2 },
];

write('youtube/data.json', {
  kpis: {
    videosWatched:        youtubeDaily.reduce((a, b) => a + b, 0),
    totalSearches:        between(800, 1200),
    totalAdsWatched:      between(180, 320),
    adsPercentage:        12.4,
    totalWatchTime:       round1(youtubeTotalHours),                                       // hours
    totalChannels:        312,
    avgWatchTimePerDay:   Math.round(youtubeDaily.reduce((a, b) => a + b, 0) / DAYS),
    enrichmentPercentage: 87.3,
    firstActivityDate:    isoDate(dateOffset(DAYS - 1)),
    lastActivityDate:     isoDate(dateOffset(0)),
  },
  topChannels: CHANNEL_NAMES.slice(0, 10).map((name, i) => {
    const watchCount = between(40, 120) - i * 5;
    const seconds = watchCount * between(180, 720);
    return {
      channelId: `UC${i.toString().padStart(22, '0')}`,
      channelTitle: name,
      watchCount,
      totalWatchTime: `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`,
      watchTimeHours: round1(seconds / 3600),
      category: pick(CATEGORIES).name,
      trend: generateTrend(30),
      uniqueVideos: between(20, 80),
    };
  }),
  categoryBreakdown: CATEGORIES.map((c) => ({
    name: c.name,
    watchCount: c.weight * between(8, 12),
    watchTime: `${c.weight * 2}h`,
    watchPercentage: c.weight,
    timePercentage: c.weight,
    uniqueChannels: between(5, 30),
  })),
  dailyWatchTimeBreakdown: dates.map((d, i) => {
    const total = youtubeDaily[i] * 0.25;
    const watched = round1(total * 0.7);
    const searches = round1(total * 0.05);
    const visits = round1(total * 0.1);
    const ads = round1(total * 0.08);
    const other = round1(total - watched - searches - visits - ads);
    const dow = new Date(d).getUTCDay();
    return {
      date: d,
      watchedHours: watched,
      searchesHours: searches,
      visitsHours: visits,
      adsHours: ads,
      otherHours: other < 0 ? 0 : other,
      totalHours: round1(total),
      watchedCount: Math.round(watched * 4),
      searchesCount: Math.round(searches * 8),
      visitsCount: Math.round(visits * 4),
      adsCount: Math.round(ads * 6),
      dayName: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][dow],
      isWeekend: dow === 0 || dow === 6,
    };
  }),
  recentVideos: Array.from({ length: 10 }, (_, i) => {
    const t = new Date(TODAY.getTime() - i * 22 * 60 * 1000);
    return {
      title: `${pick(['Why', 'How', 'The truth about', 'Inside'])} ${pick(['Rust', 'TypeScript', 'WebGPU', 'Postgres', 'Linux', 'Kubernetes'])} ${pick(['changes everything', 'in 100 seconds', 'explained', 'for beginners'])}`,
      time: t.toISOString(),
      isFromAds: i % 7 === 0,
    };
  }),
  hourlyActivity: Array.from({ length: 24 }, (_, h) => ({
    hour: `${h.toString().padStart(2, '0')}:00`,
    activities: h < 6 ? between(0, 4) : h < 9 ? between(2, 10) : h < 18 ? between(8, 28) : between(12, 35),
  })),
});

// ---------- /api/travel/data ----------
const PLACES = [
  { name: 'Zurich, Switzerland', lat: 47.3769, lng: 8.5417 },
  { name: 'Lugano, Switzerland', lat: 46.0037, lng: 8.9511 },
  { name: 'Milan, Italy', lat: 45.4642, lng: 9.19 },
  { name: 'Rome, Italy', lat: 41.9028, lng: 12.4964 },
  { name: 'Paris, France', lat: 48.8566, lng: 2.3522 },
  { name: 'Barcelona, Spain', lat: 41.3851, lng: 2.1734 },
  { name: 'Lisbon, Portugal', lat: 38.7223, lng: -9.1393 },
  { name: 'Amsterdam, Netherlands', lat: 52.3676, lng: 4.9041 },
  { name: 'Berlin, Germany', lat: 52.52, lng: 13.405 },
  { name: 'Vienna, Austria', lat: 48.2082, lng: 16.3738 },
  { name: 'Prague, Czechia', lat: 50.0755, lng: 14.4378 },
  { name: 'Copenhagen, Denmark', lat: 55.6761, lng: 12.5683 },
  { name: 'Stockholm, Sweden', lat: 59.3293, lng: 18.0686 },
  { name: 'London, UK', lat: 51.5074, lng: -0.1278 },
  { name: 'Edinburgh, UK', lat: 55.9533, lng: -3.1883 },
  { name: 'Tokyo, Japan', lat: 35.6762, lng: 139.6503 },
  { name: 'Kyoto, Japan', lat: 35.0116, lng: 135.7681 },
  { name: 'New York, USA', lat: 40.7128, lng: -74.006 },
];
const ACTIVITY_TYPES = ['directions', 'search', 'explore', 'place_view', 'place_visit'];

const totalActivities = mapsDaily.reduce((a, b) => a + b, 0);
const directionsCount = Math.round(totalActivities * 0.42);
const searchCount = Math.round(totalActivities * 0.31);
const exploreCount = Math.round(totalActivities * 0.18);
const visitsCount = totalActivities - directionsCount - searchCount - exploreCount;

// Derived breadth: count unique cities and countries from PLACES.
const uniqueCities    = new Set(PLACES.map((p) => p.name.split(',')[0].trim())).size;
const uniqueCountries = new Set(PLACES.map((p) => p.name.split(',').slice(-1)[0].trim())).size;

write('travel/data.json', {
  stats: {
    // Headline (Home channel-tile + per-page KPI row)
    citiesVisited:       uniqueCities,
    countriesVisited:    uniqueCountries,

    // Secondary stats kept for charts / per-page detail
    totalActivities:     totalActivities,
    totalDirections:     directionsCount,
    totalSearches:       searchCount,
    totalExplorations:   exploreCount,
    likelyVisits:        visitsCount,
    uniqueDestinations:  24,
    daysWithActivity:    mapsDaily.filter((n) => n > 0).length,
    daysTracked:         DAYS,
    avgActivitiesPerDay: round1(totalActivities / DAYS),
    directionsPct:       42.0,
    searchPct:           31.0,
    explorePct:          18.0,
    firstActivity:       isoDate(dateOffset(DAYS - 1)),
    lastActivity:        isoDate(dateOffset(0)),

    // Producer-console signature row: real movement, not just app activity.
    kilometersTraveled: 4870,
    daysAwayFromHome:   27,
    newPlacesThisYear:  19,
    longestTripDays:    11,
  },
  locations: PLACES.map((p) => ({
    name: p.name,
    lat: p.lat,
    lng: p.lng,
    duration: pick(['2 hours', '1 day', '3 days', '1 week', '2 weeks']),
  })),
  trips: [
    { start: '2026-04-21', end: '2026-05-02', destination: 'Tokyo',  days: 11, km: 9460 },
    { start: '2026-03-14', end: '2026-03-17', destination: 'Berlin', days:  3, km: 1080 },
    { start: '2026-02-28', end: '2026-03-02', destination: 'Milan',  days:  2, km:  460 },
    { start: '2026-02-08', end: '2026-02-15', destination: 'Lisbon', days:  7, km: 2730 },
    { start: '2026-01-19', end: '2026-01-23', destination: 'London', days:  4, km: 1620 },
  ],
  charts: {
    hourlyActivity: Array.from({ length: 24 }, (_, h) => ({
      hour: `${h.toString().padStart(2, '0')}:00`,
      activities: h < 7 ? between(0, 2) : h < 19 ? between(4, 18) : between(2, 8),
    })),
    lastActivities: Array.from({ length: 10 }, (_, i) => {
      const t = new Date(TODAY.getTime() - i * 35 * 60 * 1000);
      return {
        time: t.toISOString(),
        location: pick(PLACES).name,
        type: pick(ACTIVITY_TYPES),
      };
    }),
    topDestinations: PLACES.slice(0, 10).map((p) => ({
      destination: p.name,
      count: between(8, 60),
      trend: generateTrend(30),
      type: pick(['directions', 'search', 'explore']),
    })),
    dailyActivity: dates.map((d, i) => {
      const total = mapsDaily[i];
      const directions = Math.round(total * 0.42);
      const searches = Math.round(total * 0.31);
      const explorations = Math.round(total * 0.18);
      const other = total - directions - searches - explorations;
      return { date: d, directions, searches, explorations, other: other < 0 ? 0 : other };
    }),
  },
});

// ---------- /api/google/calendar ----------
const EVENT_TITLES = [
  'Standup', '1:1 with manager', 'Design review', 'Sprint planning', 'Retro',
  'Architecture sync', 'Coffee with Ana', 'Doctor', 'Yoga', 'Run with Marco',
  'Family dinner', 'Concert', 'Hairdresser', 'Tax appointment', 'Flight to MXP',
  'Client demo', 'Pair on auth refactor', 'Interview', 'Reading time', 'Deep work',
];
const EVENT_CATEGORIES = [
  { name: 'Work',     weight: 56 },
  { name: 'Health',   weight: 12 },
  { name: 'Social',   weight: 14 },
  { name: 'Personal', weight: 11 },
  { name: 'Travel',   weight:  7 },
];

const calendarTotalEvents = 614;
const calendarMeetingHours = 142;
// Days with zero scheduled events — the negative-space KPI for a personal
// calendar. Counts unscheduled days as a positive signal (recovery / room
// to breathe), not a void.
const calendarFreeDays = 12;

// Build a 7×24 WeekGrid for the "where the week goes" surface. Low overnight,
// peak 9-12 + 14-18 weekdays, low weekends.
const weekGridCells = [];
for (let d = 0; d < 7; d++) {
  for (let h = 0; h < 24; h++) {
    let i = 0;
    const isWeekend = d >= 5;
    if (h < 7 || h > 21) i = 0;
    else if (isWeekend) i = (h >= 10 && h <= 18) ? 0.15 + rand() * 0.25 : 0.05 + rand() * 0.15;
    else if (h >= 9 && h <= 12) i = 0.65 + rand() * 0.30;
    else if (h >= 14 && h <= 18) i = 0.60 + rand() * 0.35;
    else if (h === 8 || h === 13) i = 0.25 + rand() * 0.25;
    else if (h === 19 || h === 20) i = 0.15 + rand() * 0.25;
    else i = 0.10 + rand() * 0.15;
    weekGridCells.push({ day: d, hour: h, intensity: round1(i) });
  }
}

write('google/calendar.json', {
  kpis: {
    // Headline pair (Home channel-tile) — depth · breadth for personal life.
    plansCount:   calendarTotalEvents,   // total events scheduled
    freeDays:     calendarFreeDays,      // days with nothing on the calendar

    // Secondary KPIs (per-page detail row + charts)
    totalEvents:  calendarTotalEvents,   // alias of plansCount (kept for back-compat)
    meetingHours: calendarMeetingHours,
    avgDaily:     round1(calendarTotalEvents / DAYS),
    busiestDay:   'Tue',
  },
  weekGrid: weekGridCells,
  busyHours: Array.from({ length: 24 }, (_, h) => ({
    hour: `${h.toString().padStart(2, '0')}:00`,
    events: h < 7 ? 0 : h < 9 ? between(2, 6) : h < 12 ? between(8, 18) : h < 14 ? between(2, 6) : h < 18 ? between(10, 22) : h < 21 ? between(2, 8) : 0,
  })),
  categories: EVENT_CATEGORIES.map((c) => ({
    name: c.name,
    value: Math.round((c.weight / 100) * calendarTotalEvents),
    percentage: c.weight,
  })),
  weekdayBreakdown: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, i) => ({
    day,
    events: i < 5 ? between(18, 32) : between(2, 9),
  })),
  upcomingEvents: Array.from({ length: 8 }, (_, i) => {
    const t = new Date(TODAY.getTime() + (i + 1) * 45 * 60 * 1000);
    const cat = pick(EVENT_CATEGORIES).name;
    return {
      title: pick(EVENT_TITLES),
      category: cat,
      time: t.toISOString(),
      durationMinutes: between(15, 90),
    };
  }),
  dailyEvents: dates.map((d) => {
    const dow = new Date(d).getUTCDay();
    return {
      date: d,
      events: dow === 0 || dow === 6 ? between(0, 5) : between(4, 12),
    };
  }),
});

// ---------- /api/home/recent-events ----------
write('home/recent-events.json', {
  spotify: recentTracks.slice(0, 5),
  youtube: Array.from({ length: 5 }, (_, i) => {
    const t = new Date(TODAY.getTime() - i * 18 * 60 * 1000);
    return {
      title: `${pick(['Why', 'How', 'The truth about', 'Inside'])} ${pick(['Rust', 'WebGPU', 'Postgres', 'Linux'])} ${pick(['changes everything', 'in 100 seconds', 'explained'])}`,
      activityType: 'watched',
      time: t.toISOString(),
      isFromAds: i === 2,
    };
  }),
  maps: Array.from({ length: 5 }, (_, i) => {
    const t = new Date(TODAY.getTime() - i * 45 * 60 * 1000);
    return {
      location: pick(PLACES).name,
      type: pick(ACTIVITY_TYPES),
      time: t.toISOString(),
    };
  }),
});

// ---------- /api/system/health ----------
write('system/health.json', {
  generatedAt: TODAY.toISOString(),
  overall: { status: 'healthy', summary: 'All channels online · last sync 2m ago' },
  channels: [
    { channel: 'spotify',  status: 'healthy', lastBatchAgo: '2m ago',  eventsPerMonth: 4800, errors24h: 0 },
    { channel: 'youtube',  status: 'healthy', lastBatchAgo: '47m ago', eventsPerMonth:  320, errors24h: 0 },
    { channel: 'maps',     status: 'stale',   lastBatchAgo: '6h ago',  eventsPerMonth:  210, errors24h: 0 },
    { channel: 'calendar', status: 'healthy', lastBatchAgo: '11m ago', eventsPerMonth:   90, errors24h: 0 },
  ],
  storage: {
    name: 'ClickHouse',
    status: 'healthy',
    rowCount: 1234567,
    diskUsedMb: 412,
    byDatabase: [
      { database: 'bronze', rows: 980000, diskUsedMb: 300 },
      { database: 'silver', rows: 180000, diskUsedMb:  70 },
      { database: 'gold',   rows:  74000, diskUsedMb:  38 },
    ],
  },
  errors24h: [],
});

// ---------- /api/now/timeline ----------
// 7-day cross-channel feed. Spotify is the real-time channel (dense, ~200
// events). YouTube and Maps are batch ingests (24-48h cadence) so they're
// sparse. Calendar is daily-batched but denser during working hours.
{
  const nowMs = TODAY.getTime();
  const HOUR_MS = 3600_000;
  const DAY_MS = 24 * HOUR_MS;
  const timelineEvents = [];
  const choice = (arr) => arr[Math.floor(rand() * arr.length)];

  // ---- Spotify: ~200 events across 7d, waking-hours weighted ----
  const SPOTIFY_TRACKS = [
    ['Track started','Strobe — Deadmau5'],['Track ended','Tempo Tantrum — RJD2'],
    ['Now playing','I Want You — Mitski'],['Track ended','Random Access Memories — Daft Punk'],
    ['Liked','Untrue — Burial'],['Skipped','Generic Lofi Beat 247'],
    ['Track started','Wide Open — The Chemical Brothers'],['Track ended','Teardrop — Massive Attack'],
    ['Now playing','Midnight City — M83'],['Album opened','In Rainbows — Radiohead'],
    ['Track started','Pyramid Song — Radiohead'],['Track ended','Nightcall — Kavinsky'],
    ['Playlist queued','Deep focus · 47 tracks'],['Track started','Outro — M83'],
    ['Skipped','Bored ambient #3'],['Track started','Genesis — Justice'],
    ['Track ended','D.A.N.C.E. — Justice'],['Liked','Lazerhawk — Visitors'],
    ['Track started','Cosmic Latte — Lone'],['Track ended','Avril 14th — Aphex Twin'],
    ['Liked','Selva — Floating Points'],['Track ended','Last Resort — Trentemøller'],
    ['Now playing','Innerbloom — RÜFÜS DU SOL'],['Track started','Roygbiv — Boards of Canada'],
  ];
  for (let i = 0; i < 200; i++) {
    const daysAgo = rand() * 7;
    const ts = new Date(nowMs - daysAgo * DAY_MS);
    const h = ts.getHours();
    if (h >= 2 && h <= 5 && rand() > 0.08) { i--; continue; }
    const [label, value] = choice(SPOTIFY_TRACKS);
    timelineEvents.push({ time: ts.toISOString(), channel: 'spotify', label, value });
  }

  // ---- YouTube: ~22 events across 7d, batch-clustered (daily cadence) ----
  const YT_TITLES = [
    'Modular synth basics in 12 minutes','Why your dbt jobs are slow',
    'How to lay down vinyl flooring (search)','Inside the Polestar 4 — review',
    'React 19 the things they didn’t tell you','Linux on a Framework 13 — one year later',
    'Postgres bloat reindex concurrently (search)','How TypeScript has too many ways to type a thing',
    'How to design a producer console UI','Best espresso machines (search)',
    'Synthwave essentials — 70 min mix','Berghain documentary — first 15 minutes',
    'What is webgpu actually for (search)','How dbt does incremental models',
    'Building a CLI in Go — full tutorial','Why I switched from Vue to Solid',
    'Cloudflare Pages vs Workers — comparison','Postgres vs ClickHouse for analytics',
    'Tailwind v4 — what changed','The truth about HTMX',
    'Watch this before refactoring','Modular synth bassline tutorial',
  ];
  let ytIdx = 0;
  for (let d = 0; d < 7 && ytIdx < YT_TITLES.length; d++) {
    const batchSize = 2 + Math.floor(rand() * 3);
    for (let k = 0; k < batchSize && ytIdx < YT_TITLES.length; k++) {
      const eventDayAgo = d + 0.05 + rand() * 0.9;
      const ts = new Date(nowMs - eventDayAgo * DAY_MS);
      const title = YT_TITLES[ytIdx++];
      const isSearch = title.includes('(search)');
      timelineEvents.push({
        time: ts.toISOString(),
        channel: 'youtube',
        label: isSearch ? 'Searched' : 'Watched',
        value: title.replace(' (search)', ''),
      });
    }
  }

  // ---- Maps: ~12 events across 7d, batch-clustered (~48h cadence) ----
  const MAPS_EVENTS = [
    ['Directions','Zürich HB → home'],['Place visit','Café Schober'],
    ['Directions','home → Zürich HB'],['Search','sika headquarters baar'],
    ['Place visit','Coop Pronto'],['Directions','Bern → Zürich'],
    ['Search','dim sum near me'],['Place visit','Kaufleuten'],
    ['Directions','airport → home'],['Search','best burger zurich'],
    ['Place visit','Café Henrici'],['Directions','home → office'],
  ];
  let mapsIdx = 0;
  for (let b = 0; b < 4 && mapsIdx < MAPS_EVENTS.length; b++) {
    const batchSize = 2 + Math.floor(rand() * 2);
    for (let k = 0; k < batchSize && mapsIdx < MAPS_EVENTS.length; k++) {
      const eventDayAgo = (b * 2) + rand() * 2;
      const ts = new Date(nowMs - eventDayAgo * DAY_MS);
      const [label, value] = MAPS_EVENTS[mapsIdx++];
      timelineEvents.push({ time: ts.toISOString(), channel: 'maps', label, value });
    }
  }

  // ---- Calendar: ~25 events across 7d, working-hours weighted ----
  const CAL_EVENTS = [
    ['Meeting started','Team standup · 30 min'],['Event ended','Lunch (sandwich)'],
    ['Meeting started','1:1 with manager · 30 min'],['Event ended','Design review · 60 min'],
    ['Meeting started','Sprint planning · 90 min'],['Event ended','Coffee with Ana'],
    ['Meeting started','Architecture sync · 45 min'],['Event ended','Pair on auth refactor'],
    ['Event ended','Yoga · 60 min'],['Meeting started','Customer demo · 30 min'],
    ['Event ended','Retrospective · 60 min'],['Meeting started','Hiring loop · 45 min'],
    ['Event ended','Doctor appointment'],['Meeting started','Reading time · 30 min'],
    ['Event ended','Family dinner'],['Meeting started','Deep work block · 90 min'],
    ['Event ended','Run with Marco'],['Meeting started','Roadmap review · 60 min'],
    ['Event ended','Concert · 3h'],['Meeting started','Sales sync · 30 min'],
  ];
  let calIdx = 0;
  for (let d = 0; d < 7 && calIdx < CAL_EVENTS.length; d++) {
    const dayDate = new Date(nowMs - d * DAY_MS);
    const dow = dayDate.getDay();
    const dayCount = dow === 0 || dow === 6 ? 1 + Math.floor(rand() * 2) : 4 + Math.floor(rand() * 2);
    for (let k = 0; k < dayCount && calIdx < CAL_EVENTS.length; k++) {
      const hour = 9 + Math.floor(rand() * 10);
      const ts = new Date(nowMs - d * DAY_MS);
      ts.setHours(hour, Math.floor(rand() * 60), 0, 0);
      const [label, value] = CAL_EVENTS[calIdx++];
      timelineEvents.push({ time: ts.toISOString(), channel: 'calendar', label, value });
    }
  }

  timelineEvents.sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());

  write('now/timeline.json', {
    generatedAt: TODAY.toISOString(),
    windowMinutes: 10080, // 7d
    ingestionCadence: {
      spotify:  'real-time stream',
      youtube:  'daily batch (~24h)',
      maps:     'batch (~48h)',
      calendar: 'daily batch (~24h)',
    },
    events: timelineEvents,
  });
}

console.log(`\nWrote mocks under ${MOCKS_ROOT}`);
