// Map colours. Day heat is a 10-step sequential ramp over deciles; night is a
// diverging ramp around the city's typical built-up night temperature.

export const DECILE_COLOURS = [
  '#fff1c2', '#fde09c', '#fcc87a', '#fbac5e', '#f58d4a',
  '#ea6b3c', '#d84c33', '#be322e', '#9c1f2b', '#701425',
];
export const NOT_BUILT = '#cfcac1';

export const NIGHT_STOPS = [
  [-2, '#3f6fa6'],
  [-0.75, '#a9c4dc'],
  [0, '#f3efe8'],
  [0.75, '#f0a17e'],
  [2, '#b3202c'],
];

export const HOT = '#be322e';
export const COOL = '#2f6f8f';
export const MUTED = '#d9d4cb';
