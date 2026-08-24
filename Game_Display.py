import sys

# ANSI colors for terminal sprites. Applied per cell so map geometry
# (one logical character wide) stays intact.
RESET = '\033[0m'
SYMBOL_COLORS = {
    # Water: bright cyan on blue background
    '^': {'fg': '96', 'bg': '44'},
    'water_death': {'fg': '97', 'bg': '44'},
    # Logs: yellow/brown characters only (no background fill)
    'o': {'fg': '33'},
    # Cars: bright red; speed cars: bright magenta
    'u': {'fg': '91'},
    'p': {'fg': '95'},
    'car_death': {'fg': '91'},
}


class GD(object):

    def __init__(self, map, symbols):
        self._symbols = symbols

        # Size of one map unit in y, x length
        empty_block = self.get(' ')
        self.size = (len(empty_block), len(empty_block[0]))

        self.map = self.trans_map(map)
        self.act_map = [list(i) for i in map]

        # Last frame written to the terminal (viewport cells + status lines).
        # Used so we only emit the cells that actually changed.
        self._screen_buf = None
        self._status_buf = None

    def _colorize(self, char, style):
        """Wrap a single display cell in ANSI color codes when styled."""
        if not style:
            return char
        # Keep plain spaces transparent unless a background fills the tile
        if char == ' ' and 'bg' not in style:
            return char
        codes = []
        if 'fg' in style:
            codes.append(style['fg'])
        if 'bg' in style:
            codes.append(style['bg'])
        return '\033[{}m{}{}'.format(';'.join(codes), char, RESET)

    def get(self, symbol, symbol_num=0):
        """
        Returns a copy of the symbol as rows of display cells.

        Each cell is one visible character, optionally wrapped in ANSI color.
        """
        rows = self._symbols[symbol][symbol_num]
        style = SYMBOL_COLORS.get(symbol)
        return [[self._colorize(ch, style) for ch in row] for row in rows]

    def invalidate(self):
        """Forget the last drawn frame so the next draw is a full refresh."""
        self._screen_buf = None
        self._status_buf = None

    def enter_draw_mode(self):
        """Switch to the alternate screen and hide the cursor."""
        sys.stdout.write('\033[?1049h\033[?25l')
        sys.stdout.flush()
        self.invalidate()

    def leave_draw_mode(self):
        """Restore the cursor and leave the alternate screen."""
        sys.stdout.write('\033[?25h\033[?1049l')
        sys.stdout.flush()
        self.invalidate()

    def print_map(self, y_range, x_range):
        """Full print of a map slice (used by tests / simple callers)."""
        new_map = [i[x_range[0]:x_range[1]]
                    for i in self.map[y_range[0]: y_range[1]]]
        for i in new_map:
            print(''.join(i))

    def draw_frame(self, y_range, x_range, status_lines=None, force=False):
        """
        Paint the current viewport to the terminal.

        Instead of reprinting the whole map every frame, compare against the
        previous frame and only write runs of cells that changed, using ANSI
        cursor addressing. A camera jump or invalidate() forces a full redraw.
        """
        if status_lines is None:
            status_lines = []

        new_rows = [row[x_range[0]:x_range[1]][:]
                    for row in self.map[y_range[0]:y_range[1]]]

        need_full = (
            force
            or self._screen_buf is None
            or len(self._screen_buf) != len(new_rows)
            or (self._screen_buf and len(self._screen_buf[0]) != len(new_rows[0]))
        )

        if need_full:
            self._draw_full(new_rows, status_lines)
        else:
            self._draw_dirty(new_rows, status_lines)

        self._screen_buf = new_rows
        self._status_buf = list(status_lines)

    def _draw_full(self, rows, status_lines):
        """Home, clear, and write the entire viewport + status."""
        parts = ['\033[H\033[J']
        for row in rows:
            parts.append(''.join(row))
            parts.append('\n')
        for line in status_lines:
            parts.append(line)
            parts.append('\n')
        sys.stdout.write(''.join(parts))
        sys.stdout.flush()

    def _draw_dirty(self, rows, status_lines):
        """Rewrite only changed cell runs and status lines."""
        parts = []
        for y, (old_row, new_row) in enumerate(zip(self._screen_buf, rows)):
            if old_row == new_row:
                continue
            x = 0
            width = len(new_row)
            while x < width:
                if old_row[x] == new_row[x]:
                    x += 1
                    continue
                start = x
                while x < width and old_row[x] != new_row[x]:
                    x += 1
                # Terminal positions are 1-based; each map cell is one column.
                parts.append('\033[{};{}H'.format(y + 1, start + 1))
                parts.append(''.join(new_row[start:x]))

        status_row = len(rows) + 1
        if status_lines != self._status_buf:
            for i, line in enumerate(status_lines):
                # Clear the line then write, so shorter HUD text does not ghost.
                parts.append('\033[{};1H\033[2K{}'.format(status_row + i, line))

        if parts:
            # Park the cursor below the HUD so stray input does not junk the map.
            parts.append('\033[{};1H'.format(status_row + len(status_lines)))
            sys.stdout.write(''.join(parts))
            sys.stdout.flush()

    def update(self, symbol_map):
        """Updates the Display Map using the Symbol Map"""
        self.map = self.trans_map(symbol_map)

    def trans_map(self, map):
        """Takes each line and transforms it, returning a new map"""
        new_map = self.trans_line(map[0])

        for i in range(1, len(map)):
            new_lines = self.trans_line(map[i])
            new_map += new_lines

        return [list(i) for i in new_map]

    def trans_line(self, line):
        """Takes a line and transforms each symbol, the line may turn
        into multiple lines
        """
        # Deep-copy rows so later symbols can extend them independently
        new_lines = [row[:] for row in self.get(line[0])]

        # For each symbol, retrieve its map and add each line to the
        # corresponding line in new_lines
        for i in range(1, len(line)):
            new_symbol = self.get(line[i])

            for j in range(len(new_symbol)):
                new_lines[j] += new_symbol[j]

        return new_lines

    def trans_coords(self, coords, map):
        """Takes coords from *map* and returns the top left corner
        coords of the corresponding field from the other map as a list
        """
        y, x = coords
        y_len, x_len = self.size

        if map == "disp_map":
            # Get the nearest number, gets next number if more than half
            y_new = (y + y_len // 2) // y_len
            x_new = (x + x_len // 2) // x_len
            # Extra case at end of map, nearest field is 0 again
            if x_new >= len(self.act_map[y_new]):
                x_new = 0

            return [y_new, x_new]

        elif map == "act_map":
            return [y * y_len, x * x_len]

    def display(self, symbol, coords, symbol_num=0):
        """Paints *symbol* on map in position *coords*"""
        pic = self.get(symbol, symbol_num)
        # Define starting point: line(y) and pos(x) in line
        y, x = coords

        for i in range(len(pic)):
            for j in range(len(pic[0])):
                x_index = x + j
                # If pixel goes over edge on x axis: wrap it around
                if x + j >= len(self.map[y + i]):
                    x_index = (x + j) % len(self.map[y + i])

                self.map[y + i][x_index] = pic[i][j]

    def check_collision(self, obj1, obj2):
        """Checks for a collision between two objects using their coords"""
        # Coords are always only the upper left-hand corner of object
        # so first get all four corners of objects by adding size
        y1 = [obj1[0], obj1[0] + self.size[0]-1]
        x1 = [obj1[1], obj1[1] + self.size[1]-1]

        y2 = [obj2[0], obj2[0] + self.size[0]-1]
        x2 = [obj2[1], obj2[1] + self.size[1]-1]

        # Now check if y ranges overlap, then check x ranges
        if y1[0] <= y2[1] and y1[1] >= y2[0]:
            return x1[0] <= x2[1] and x1[1] >= x2[0]
        else:
            return False
