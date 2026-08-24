# Terminal-Frogger
Small frogger-themed game for the terminal. Run with Python 3:

```bash
python3 Frogger.py
```

**Controls:** `w` up, `s` down, `a` left, `d` right, `x` exit

**Goal:** Cross to the top border. You have 3 lives. Score points for moving
upward and a bonus for each successful crossing.

Each win starts a new **crossing** on a longer map with more roads and
water (with logs). Keep going further as far as you can.

The game opens on a start screen; death and win events show their own
screens and wait for a key before continuing (or exiting on game over).

Water, logs, and cars use ANSI colors (blue water, yellow logs, red/magenta
cars). Use a color-capable terminal for the best look.

Should work on Windows as well but hasn't been fully tested.

[![asciicast](https://asciinema.org/a/zS5dHHiX3TahTpQUznsObDtAp.svg)](https://asciinema.org/a/zS5dHHiX3TahTpQUznsObDtAp)
