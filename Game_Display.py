import curses

# Logical color names mapped to curses color-pair ids in init_curses_colors().
SYMBOL_COLOR_PAIRS = {
    '^': 1,
    'water_death': 1,
    'o': 2,
    'u': 3,
    'car_death': 3,
    'p': 4,
}


def init_curses_colors():
    """Register the color pairs used by sprites (safe if terminal has no color)."""
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        default_bg = -1
    except curses.error:
        default_bg = curses.COLOR_BLACK
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLUE)      # water
    curses.init_pair(2, curses.COLOR_YELLOW, default_bg)           # logs
    curses.init_pair(3, curses.COLOR_RED, default_bg)              # cars
    curses.init_pair(4, curses.COLOR_MAGENTA, default_bg)          # speed cars


class GD(object):

    def __init__(self, map, symbols):
        self._symbols = symbols

        # Size of one map unit in y, x length (plain chars, no ANSI wrappers)
        empty_block = self.get(' ')
        self.size = (len(empty_block), len(empty_block[0]))

        self.map, self.attrs = self.trans_map(map)
        self.act_map = [list(i) for i in map]

    def color_for(self, symbol):
        """Return the curses color-pair id for a logical map symbol."""
        return SYMBOL_COLOR_PAIRS.get(symbol, 0)

    def get(self, symbol, symbol_num=0):
        """
        Returns a copy of the symbol as rows of plain display characters.
        """
        rows = self._symbols[symbol][symbol_num]
        return [list(row) for row in rows]

    def print_map(self, y_range, x_range):
        """Full print of a map slice (tests / non-curses callers)."""
        new_map = [i[x_range[0]:x_range[1]]
                    for i in self.map[y_range[0]: y_range[1]]]
        for i in new_map:
            print(''.join(i))

    def draw_curses(self, stdscr, y_range, x_range, status_lines=None):
        """
        Paint the viewport onto a curses window and refresh.

        curses keeps its own screen buffer and only sends dirty cells to the
        terminal on refresh(), so we can rewrite the whole view each frame.
        """
        if status_lines is None:
            status_lines = []

        max_y, max_x = stdscr.getmaxyx()
        view = self.map[y_range[0]:y_range[1]]
        view_attrs = self.attrs[y_range[0]:y_range[1]]

        for y, row in enumerate(view):
            if y >= max_y:
                break
            chars = row[x_range[0]:x_range[1]]
            colors = view_attrs[y][x_range[0]:x_range[1]]
            self._add_row(stdscr, y, chars, colors, max_x)

        for i, line in enumerate(status_lines):
            sy = len(view) + i
            if sy >= max_y:
                break
            try:
                stdscr.move(sy, 0)
                stdscr.clrtoeol()
                stdscr.addnstr(sy, 0, line, max(0, max_x - 1))
            except curses.error:
                pass

        # Clear any leftover HUD lines below if the view shrank.
        for sy in range(len(view) + len(status_lines), max_y):
            try:
                stdscr.move(sy, 0)
                stdscr.clrtoeol()
            except curses.error:
                break

        stdscr.refresh()

    def _add_row(self, stdscr, y, chars, colors, max_x):
        """Write one row, coalescing runs that share the same color pair."""
        width = min(len(chars), max_x)
        x = 0
        while x < width:
            color = colors[x] if x < len(colors) else 0
            start = x
            x += 1
            while x < width and (colors[x] if x < len(colors) else 0) == color:
                x += 1
            chunk = ''.join(chars[start:x])
            attr = curses.color_pair(color) if color else 0
            try:
                stdscr.addstr(y, start, chunk, attr)
            except curses.error:
                # Writing the bottom-right corner raises; ignore safely.
                pass

    def update(self, symbol_map):
        """Updates the Display Map using the Symbol Map"""
        self.map, self.attrs = self.trans_map(symbol_map)

    def trans_map(self, map):
        """Takes each line and transforms it, returning chars + color attrs."""
        lines, attrs = self.trans_line(map[0])

        for i in range(1, len(map)):
            new_lines, new_attrs = self.trans_line(map[i])
            lines += new_lines
            attrs += new_attrs

        return lines, attrs

    def trans_line(self, line):
        """Takes a line and transforms each symbol into display rows + attrs."""
        color = self.color_for(line[0])
        new_lines = [row[:] for row in self.get(line[0])]
        new_attrs = [[color] * len(row) for row in new_lines]

        for i in range(1, len(line)):
            new_symbol = self.get(line[i])
            color = self.color_for(line[i])

            for j in range(len(new_symbol)):
                new_lines[j] += new_symbol[j]
                new_attrs[j] += [color] * len(new_symbol[j])

        return new_lines, new_attrs

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
        color = self.color_for(symbol)
        y, x = coords

        for i in range(len(pic)):
            for j in range(len(pic[0])):
                x_index = x + j
                # If pixel goes over edge on x axis: wrap it around
                if x + j >= len(self.map[y + i]):
                    x_index = (x + j) % len(self.map[y + i])

                self.map[y + i][x_index] = pic[i][j]
                self.attrs[y + i][x_index] = color

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
