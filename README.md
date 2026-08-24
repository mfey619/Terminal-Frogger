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

Long maps use a fixed-height view: when you climb near the top of the
screen, the camera jumps and places the frog at the bottom of the next
page of the map.

The game opens on a start screen; death and win events show their own
screens and wait for a key before continuing (or exiting on game over).

Water, logs, and cars use curses color pairs (cyan water, yellow logs,
red/magenta cars). Use a color-capable terminal for the best look.

Display and keyboard input go through Python's **curses** library, which
keeps a screen buffer and only updates cells that changed. On Windows,
install `windows-curses` (`pip install windows-curses`).

[![asciicast](https://asciinema.org/a/zS5dHHiX3TahTpQUznsObDtAp.svg)](https://asciinema.org/a/zS5dHHiX3TahTpQUznsObDtAp)
