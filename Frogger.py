import os
import time
import random
import locale
import curses
import traceback

from Game_Display import GD, init_curses_colors


class LevelReset(Exception):
    """Raised after a life is lost or the goal is reached so the game loop
    can abort the current update pass on a freshly reset level."""
    pass


class Game(object):

    STARTING_LIVES = 3
    SCORE_PER_ROW = 10
    SCORE_PER_WIN = 100
    # Fixed terminal window in action-map tiles (classic map height).
    VIEW_TILES = 11
    # When the frog enters this many tiles of the top of the view, page up.
    JUMP_MARGIN = 2

    def __init__(self, map, symbols, level=1):
        """
        Initialize the game

        :param map: <list> A list of strings containing simple map
        :param symbols: <dict> Contains all the graphics for our symbols
        :param level: <int> Crossing number; higher levels use longer maps
        """
        self.original_map = [row[:] for row in map]
        self.symbols = symbols
        self.level = max(1, int(level))
        self.lives = self.STARTING_LIVES
        self.score = 0
        self.camera_row = 0

        # Initialize game display, includes the Display Map
        self.GD = GD(map, symbols)
        # GD makes a copy of the Symbol Map as a list of lists
        self.act_map = self.GD.act_map

        self._init_entities()

        # Latest key from curses (polled on the main thread; curses is not
        # safe to share stdin across threads).
        self.input = [None]
        self.stdscr = None

    def _init_entities(self):
        """Create player and moving objects from the current action map."""
        self.player = Player('H', self)
        self.logs = self.init_objects('o', 3, Log)
        self.cars = self.init_objects('u', 1, Car)
        speed_cars = self.init_objects('p', 1, SpeedCar)
        if speed_cars:
            self.cars.extend(speed_cars)
        self.snakes = self.init_objects('s', 3, Snake)
        # Track farthest progress toward the top (lower y is farther)
        self.farthest_row = self.GD.trans_coords(self.player.coords, "disp_map")[0]
        # Start on the bottom page so the lower border is visible.
        self.camera_row = max(0, len(self.act_map) - self.view_height())

    def reset_level(self):
        """Restore the map and entities after a death or successful crossing."""
        self.GD = GD([row[:] for row in self.original_map], self.symbols)
        self.act_map = self.GD.act_map
        self._init_entities()

    def find(self, symbol):
        """
        Searches for Symbol in act_map and returns coords

        :param symbol: <char> The symbol to search for
        :return: <list> [y, x] coords of symbol's position in act_map
        """
        for i, x in enumerate(self.act_map):
            if symbol in x:
                return [i, x.index(symbol)]
        return None

    def init_objects(self, symbol, length, Object):
        """
        Initialize all objects of type "Object" in the game map

        :param symbol: <char> Symbol of the object
        :param length: <int> How many symbols one object has in the map
        :param Object: <type> Name of the Class from which to create object
        :return: <list> Returns a list of all objects of one type in map
        """
        objects = []
        dire = 'R'

        for i in range(len(self.act_map)):
            count = 0
            coords = []
            # Switch the direction every new line
            dire = 'R' if dire == 'L' else 'L'

            for j in range(len(self.act_map[i])):

                if self.act_map[i][j] == symbol:
                    count += 1
                    coords.append((i, j))
                if count == length:
                    n_obj = Object(coords, dire, self)
                    objects.append(n_obj)
                    count = 0
                    coords = []

        return objects

    def print_game(self, normal=False):
        """
        Draw the current camera page via curses (curses diffs on refresh).
        """
        old_camera = self.camera_row
        self.update_camera()
        if self.camera_row != old_camera and self.stdscr is not None:
            self.stdscr.erase()
        y_range, x_range = self.camera_env()
        status = [
            "Lives: {}   Score: {}   Crossing: {}".format(
                self.lives, self.score, self.level),
            "Up[w], Down[s], Left[a], Right[d] or Exit[x]",
        ]
        if self.stdscr is None:
            self.GD.print_map(y_range, x_range)
            for line in status:
                print(line)
            return
        self.GD.draw_curses(self.stdscr, y_range, x_range, status)

    def view_height(self):
        """How many action-map rows fit in the terminal window."""
        return min(self.VIEW_TILES, len(self.act_map))

    def player_act_row(self):
        """Player row in action-map coordinates."""
        return self.GD.trans_coords(self.player.coords, "disp_map")[0]

    def snap_camera_to_player(self):
        """Page the camera so the frog sits on the bottom row of the view."""
        view_h = self.view_height()
        player_y = self.player_act_row()
        max_camera = max(0, len(self.act_map) - view_h)
        # Place frog on the last visible row, then clamp to the map.
        self.camera_row = player_y - (view_h - 1)
        if self.camera_row < 0:
            self.camera_row = 0
        elif self.camera_row > max_camera:
            self.camera_row = max_camera
        # Near the map bottom, pin to the final page so the border shows.
        if player_y >= len(self.act_map) - 2:
            self.camera_row = max_camera

    def update_camera(self):
        """
        Jump to a new page when the frog leaves the comfortable band of
        the current view. After an upward jump, the frog is at the bottom
        again with more map revealed above.
        """
        view_h = self.view_height()
        if view_h >= len(self.act_map):
            self.camera_row = 0
            return

        player_y = self.player_act_row()
        view_top = self.camera_row
        view_bottom = self.camera_row + view_h - 1

        # Climbed into the top band of this page -> snap frog to bottom.
        if player_y <= view_top + self.JUMP_MARGIN and view_top > 0:
            self.snap_camera_to_player()
        # Moved below (or somehow above) the current page -> resnap.
        elif player_y > view_bottom or player_y < view_top:
            self.snap_camera_to_player()

    def camera_env(self):
        """Display-map y/x ranges for the current camera page."""
        tile_h = self.GD.size[0]
        view_h = self.view_height()
        y_up = self.camera_row * tile_h
        y_down = min(len(self.GD.map), (self.camera_row + view_h) * tile_h)
        x_left = 0
        x_right = len(self.GD.map[0])
        return [[y_up, y_down], [x_left, x_right]]

    def player_env(self, y_range, x_range):
        """
        Takes the whole map and returns a new one with only that part
        which is in player's environment
        """
        pos_y, pos_x = self.player.coords

        if pos_x - x_range < 0:
            x_left = 0
            x_right = x_left + x_range * 2
        elif pos_x + x_range > len(self.GD.map[0]) - 1:
            x_right = len(self.GD.map[0]) - 1
            x_left = x_right - x_range * 2
        else:
            x_left = pos_x - x_range
            x_right = x_left + x_range * 2

        if pos_y - y_range < 0:
            y_up = 0
            y_down = y_up + y_range * 2
        elif pos_y + y_range > len(self.GD.map) - 1:
            y_down = len(self.GD.map) - 1
            y_up = y_down - y_range * 2
        else:
            y_up = pos_y - y_range
            y_down = y_up + y_range * 2

        return [[y_up, y_down], [x_left, x_right]]

    def action(self):
        """
        Checks for input from user and acts accordingly

        :return: <bool> Returns True if there is an action, else False
        """
        if self.input[0] == None:
            return False
        else:
            key = self.input[0]
            self.input[0] = None

            if key == 'x':
                self.kill()
            elif key == 'w':
                move = "Up"
            elif key == 's':
                move = "Down"
            elif key == 'a':
                move = "Left"
            elif key == 'd':
                move = "Right"
            else:
                return False

            try:
                self.player.update(move)
            except LevelReset:
                pass
            return True

    def poll_keys(self):
        """Non-blocking read of all pending keys; keep the most recent one."""
        if self.stdscr is None:
            return
        while True:
            ch = self.stdscr.getch()
            if ch == -1:
                break
            if 0 <= ch < 256:
                self.input[0] = chr(ch)

    def update_map(self):
        """Updates all objects in map"""
        try:
            for log in self.logs:
                log.update()

            for car in self.cars:
                car.update()

            for snake in self.snakes:
                snake.update()
        except LevelReset:
            return

    def show_screen(self, title, body_lines, prompt):
        """Clear the curses window and print a framed status screen."""
        width = 44
        border = '=' * width
        lines = [
            border,
            title.center(width),
            border,
            '',
        ]
        for line in body_lines:
            lines.append('  ' + line)
        lines.append('')
        lines.append(prompt.center(width))

        if self.stdscr is None:
            os.system('clear')
            for line in lines:
                print(line)
            print()
            return

        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        start_y = max(0, (max_y - len(lines)) // 2)
        for i, line in enumerate(lines):
            y = start_y + i
            if y >= max_y:
                break
            x = max(0, (max_x - len(line)) // 2)
            try:
                self.stdscr.addnstr(y, x, line, max(0, max_x - x - 1))
            except curses.error:
                pass
        self.stdscr.refresh()

    def wait_for_key(self):
        """Block until the player presses a key, then resume non-blocking input."""
        self.input[0] = None
        if self.stdscr is None:
            return
        self.stdscr.nodelay(False)
        self.stdscr.getch()
        self.stdscr.nodelay(True)

    def start_screen(self):
        """Title screen shown before the first crossing."""
        self.show_screen(
            'TERMINAL FROGGER',
            [
                'Cross the road. Ride the logs.',
                'Reach the top border to score!',
                'Each win opens a longer map.',
                '',
                'Controls:',
                '  w Up     s Down',
                '  a Left   d Right',
                '  x Exit',
                '',
                'Lives: {}'.format(self.STARTING_LIVES),
                '+{} points per row advanced'.format(self.SCORE_PER_ROW),
                '+{} points per crossing'.format(self.SCORE_PER_WIN),
            ],
            'Press any key to start',
        )
        self.wait_for_key()

    def death_screen(self, message):
        """Screen after losing a life, with lives remaining."""
        self.show_screen(
            'SPLAT!',
            [
                message.strip() or 'You died.',
                '',
                'Lives left: {}'.format(self.lives),
                'Score: {}'.format(self.score),
                'Crossing: {}'.format(self.level),
            ],
            'Press any key to continue',
        )
        self.wait_for_key()

    def game_over_screen(self, message):
        """Final screen when all lives are gone."""
        self.show_screen(
            'GAME OVER',
            [
                message.strip() or 'You died.',
                '',
                'Final score: {}'.format(self.score),
                'Reached crossing: {}'.format(self.level),
            ],
            'Press any key to exit',
        )
        self.wait_for_key()

    def win_screen(self):
        """Screen after a successful crossing."""
        next_level = self.level + 1
        self.show_screen(
            'YOU MADE IT!',
            [
                'Safe on the far side.',
                '',
                '+{} crossing bonus'.format(self.SCORE_PER_WIN),
                'Score: {}'.format(self.score),
                '',
                'Crossing {} complete.'.format(self.level),
                'Next map grows longer (#{})'.format(next_level),
            ],
            'Press any key for the next crossing',
        )
        self.wait_for_key()

    def resync_clock(self):
        """
        Reset frame/tick timing after a pause (win/death screen) and redraw.

        The main loop's sleeper schedules from tick count vs self.start. If we
        reset start but leave tick high, sleeper sleeps for a huge delay and the
        screen stays blank until that sleep finishes.
        """
        self.start = time.perf_counter()
        self.frame = 1
        self.tick = 0
        self.input[0] = None
        if self.stdscr is not None:
            self.stdscr.erase()
        self.print_game()
        self.frame += 1

    def main_loop(self):
        """Run the game inside a curses session."""
        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            pass
        try:
            curses.wrapper(self._curses_main)
        except SystemExit:
            # Normal exit via kill() / pressing x.
            pass

    def _setup_curses(self, stdscr):
        """Configure the curses window for gameplay."""
        self.stdscr = stdscr
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.keypad(True)
        stdscr.timeout(0)
        init_curses_colors()

    def _curses_main(self, stdscr):
        """Main loop body running under curses.wrapper."""
        self._setup_curses(stdscr)
        self.start_screen()

        self.FPS = 40
        self.frame = 1
        self.tick = 0
        self.start = time.perf_counter()

        try:
            while True:
                self.poll_keys()
                self.action()
                self.update_map()

                if self.timer(self.FPS):
                    self.print_game()
                    self.frame += 1

                self.sleeper(self.tick)
                self.tick += 1
        except SystemExit:
            raise
        except Exception:
            # Restore the terminal before printing a traceback.
            try:
                curses.endwin()
            except curses.error:
                pass
            traceback.print_exc()
            raise

    def timer(self, FPS):
        """
        Game should be printed *FPS* times per second. Determines if we are
        behind schedule and should print a frame.

        :param FPS: <int> Amount of frames per second that we want
        :return: <bool> True if it's time to print, False if not
        """
        frame_time = self.frame / FPS
        elapsed_time = time.perf_counter() - self.start

        return frame_time - elapsed_time < 0

    def sleeper(self, tick, TPS=70):
        """
        Sleeps for just enough time to meet our TPS schedule

        :param tick: <int> How many game ticks have elapsed
        :param TPS: <int> Ticks per second (How often we udpate our game map)
        """
        correct_time = tick / TPS
        actual_time = time.perf_counter() - self.start

        # If we are ahead of time: sleep off the difference
        if correct_time - actual_time > 0:
            time.sleep(correct_time - actual_time)

    def award_progress(self, act_row):
        """Award points when the player reaches a new farthest row up the map."""
        if act_row < self.farthest_row:
            rows_gained = self.farthest_row - act_row
            self.score += rows_gained * self.SCORE_PER_ROW
            self.farthest_row = act_row

    def win(self):
        """Handle reaching the top goal: score bonus and start a longer crossing."""
        self.score += self.SCORE_PER_WIN
        self.win_screen()
        self.level += 1
        self.original_map = generate_map(self.level)
        self.reset_level()
        self.resync_clock()
        raise LevelReset()

    def dead(self, message=' '):
        """
        Lose a life on death. Respawn if lives remain; otherwise end the game.
        """
        self.lives -= 1

        if self.lives > 0:
            self.death_screen(message)
            self.reset_level()
            self.resync_clock()
            raise LevelReset()
        else:
            self.game_over_screen(message)
            self.kill(prompt=False)

    def kill(self, prompt=True):
        """Leave the game loop; curses.wrapper restores the terminal."""
        if prompt and self.stdscr is not None:
            self.show_screen(
                'BYE',
                ['Thanks for playing.'],
                'Press any key to exit',
            )
            self.wait_for_key()
        raise SystemExit()


class Player(object):

    def __init__(self, symbol, Game):
        self.sym = symbol
        self.GD = Game.GD
        self.act_map = self.GD.act_map
        self.game = Game
        self.coords = self.GD.trans_coords(self.find(self.sym), "act_map")
        self.replace = ' '

    def find(self, symbol):
        """Searches for Symbol in map and returns coords"""
        for i, x in enumerate(self.act_map):
            if symbol in x:
                return [i, x.index(symbol)]
        return None

    def update(self, move, steps=1):
        """Move player *steps* times in direction specified by *move*"""
        for i in range(steps):
            pos_y, pos_x = self.coords[:]

            if move == "Up":
                pos_y -= self.GD.size[0]
            elif move == "Down":
                pos_y += self.GD.size[0]
            elif move == "Left":
                pos_x -= self.GD.size[1]
            elif move == "Right":
                pos_x += self.GD.size[1]

            self.check_position([pos_y, pos_x])

    def check_position(self, position):
        """
        Checks if move is possible and what should happen

        :param position: <list> Display Coords in the form of [y, x]
        """
        # Check if player is at either edge of map, if so do nothing
        if position[1] < 0 or position[1] >= len(self.GD.map[0]):
            return True

        # Block moving off the top/bottom of the display map
        if position[0] < 0 or position[0] >= len(self.GD.map):
            return True

        pos_y, pos_x = self.GD.trans_coords(position, "disp_map")
        symbol = self.act_map[pos_y][pos_x]

        if symbol in [' ', 'o', '_']:
            self.move_position(self.coords, position)
            self.replace = symbol
            self.game.award_progress(pos_y)
            return True
        elif symbol == '-':
            # Top border is the goal; bottom border is solid
            if pos_y == 0:
                self.move_position(self.coords, position)
                self.replace = symbol
                self.game.award_progress(pos_y)
                self.game.win()
            return True
        elif symbol == '^':
            self.move_position(self.coords, position)
            self.GD.display("water_death", position)
            self.game.dead("You poor fellow drowned.")
        elif symbol in ('u', 'p'):
            self.move_position(self.coords, position)
            self.GD.display("car_death", position)
            self.game.dead("You jumped on a car...SPLAT!")
        elif symbol == 's':
            self.move_position(self.coords, position)
            self.GD.display("snake_death", position)
            self.game.dead("You jumped on a snake...SPLAT!")

    def move_position(self, position, new_position):
        """
        Moves symbol at position to new_position

        :param position: <list> Current position in form of [y, x] coords
        :param new_position: <list> Display map target coords in form of [y, x]
        """
        y, x = self.GD.trans_coords(position, "disp_map")
        y_new, x_new = self.GD.trans_coords(new_position, "disp_map")
        symbol = self.act_map[y][x]

        # Update action map replacing old spot with previous symbol
        self.act_map[y][x] = self.replace
        self.act_map[y_new][x_new] = symbol

        # Update the Game Display with normal coords
        self.GD.display(self.replace, position)
        self.GD.display(symbol, new_position)

        self.coords = new_position[:]

class Thing(object):

    def __init__(self, coords, direction, Game):
        self.GD = Game.GD
        self.game = Game
        self.coords = [self.GD.trans_coords(i, "act_map") for i in coords]
        self.act_map = self.GD.act_map

        # Specifies the default symbol with which to replace when moving
        self.replace = ' '

        if direction == 'R':
            self.move = +1
            # reverse coords so that head is the first item
            self.coords.reverse()
        else:
            self.move = -1

        # Random speed between one update every cycle, every 2nd or 3rd cycle
        self.speed = random.randint(2, 3)
        self.cycle_count = 1

    def update(self):
        """Update Thing every *speed* cycle"""
        # Only continues if cycle_count is equal to self.speed
        if self.cycle_count == self.speed:
            self.cycle_count = 1
        else:
            self.cycle_count += 1
            return None

        # Update each separate chunk of Thing
        for i in range(len(self.coords)):
            self.update_piece(i)

    def update_piece(self, i):
        """Moves piece one to the right or left
        and displays it on the map
        """
        old = self.coords[i][:]
        new = self.coords[i]

        new[1] += self.move

        # If over the board to the right or left
        if new[1] >= len(self.GD.map[0]):
            new[1] = 0
        elif new[1] < 0:
            new[1] = len(self.GD.map[0]) - 1

        # Transform display map coords to action map coords
        pos = self.GD.trans_coords(old, "disp_map")
        new_pos = self.GD.trans_coords(new, "disp_map")

        # Get the correct symbol from act_map and change display map
        symbol = self.act_map[pos[0]][pos[1]]
        self.change_display(symbol, old, new)

        # If pos and new_pos are different, update action map
        if pos != new_pos:
            self.move_symbol(pos, new_pos)

    def change_display(self, symbol, old, new):
        """Changes display at old and new positions, using symbol at new"""
        self.GD.display(self.replace, old)
        self.GD.display(symbol, new)

    def move_symbol(self, pos, new_pos):
        """Moves symbol in action map to a new position and
        replaces old with replace symbol
        """
        y, x = pos
        y_new, x_new = new_pos
        symbol = self.GD.act_map[y][x]

        self.GD.act_map[y][x] = self.replace
        self.GD.act_map[y_new][x_new] = symbol

    def cycle_generator(self, num, times):
        """Yields an infinite cycle from 0 to num - 1, each number *times*"""
        while True:
            for i in range(num):
                for j in range(times):
                    yield i

class Log(Thing):

    def __init__(self, coords, direction, Game):
        super(Log, self).__init__(coords, direction, Game)

        # Override Thing replace symbol with '^' water symbol
        self.replace = '^'

    def update_piece(self, i):
        """Overrides Thing method and adds a player check for each piece"""
        super(Log, self).update_piece(i)

        # Logs can have players on them so we additionally check for player
        player = self.game.player
        y, x = self.GD.trans_coords(self.coords[i], "disp_map")

        if self.act_map[y][x] == player.sym:
            # Check if player is at the edge at new coords
            if self.coords[i][1] >= len(self.GD.map[0]) - self.GD.size[1]:
                self.game.dead()
            elif self.coords[i][1] == 0:
                self.game.dead()

            # If not dead update players coords
            player.coords = self.coords[i][:]

class Car(Thing):

    def __init__(self, coords, direction, Game):
        super(Car, self).__init__(coords, direction, Game)

        # Override Thing replace symbol with '_' lane symbol
        self.replace = '_'
        # Override Thing speed with set speed
        self.speed = 3
        # Initialize generator object in order to cycle pictures of Car
        self.cycle = self.cycle_generator(3, 6)

    def update_piece(self, i):
        """
        Overrides Thing method, adding a check for player collision
        """
        super(Car, self).update_piece(i)

        player = self.game.player
        # Get display map coords from player and car
        car_coords = self.coords[i]
        play_coords = player.coords

        # Check if their coords collide
        if self.GD.check_collision(car_coords, play_coords):
            self.GD.display("car_death", play_coords)
            self.game.dead("You got hit by a car..SPLAT!")

    def change_display(self, symbol, old, new):
        """Overrides Thing method and adds picture cycle"""
        self.GD.display(self.replace, old)
        self.GD.display(symbol, new, next(self.cycle))

class SpeedCar(Car):

    def __init__(self, coords, direction, Game):
        super(SpeedCar, self).__init__(coords, direction, Game)

        # Make this car go fast
        self.speed = 1
        # Override Car cycle, this car has only one picture
        self.cycle = self.cycle_generator(1, 1)

class Snake(Thing):

    def __init__(self, coords, direction, Game):
        super(Snake, self).__init__(coords, direction, Game)

        # Override Thing speed with set speed
        self.speed = 3
        # Initialize generator object in order to cycle pictures of Car
        self.cycle = self.cycle_generator(2, 6)

    def update_piece(self, i):
        """
        Overrides Thing method, adding a check for player collision
        """
        super(Snake, self).update_piece(i)

        player = self.game.player
        # Get display map coords from player and car
        car_coords = self.coords[i]
        play_coords = player.coords

        # Check if their coords collide
        if self.GD.check_collision(car_coords, play_coords):
            self.GD.display("snake_death", play_coords)
            self.game.dead("You got eaten by a snake..SPLAT!")

    def change_display(self, symbol, old, new):
        """Overrides Thing method and adds picture cycle"""
        self.GD.display(self.replace, old)
        self.GD.display(symbol, new, next(self.cycle))



MAP_WIDTH = 12


def _grass_row(width):
    return ' ' * width


def _border_row(width):
    return '-' * width


def _place_run(row, start, length, symbol):
    """Write a contiguous run of *symbol* into *row* starting at *start*."""
    for offset in range(length):
        row[start + offset] = symbol


def _water_row(width, rng):
    """One river lane with a single log (ooo) the frog can ride.

    One log per lane keeps riders from colliding: logs pick their own
    random speed, so two on the same row would eventually overlap.
    """
    row = ['^'] * width
    start = rng.randint(0, width - 3)
    _place_run(row, start, 3, 'o')
    return ''.join(row)


def _road_row(width, rng, with_speed=False):
    """One traffic lane with cars spaced apart so they do not stack.

    Fast cars get their own lane: they move at a different speed than normal
    cars, so mixing them on one row lets them overwrite each other.
    """
    row = ['_'] * width
    placed = []
    # Keep a wide gap; cars wrap the row and same-speed packs stay clear.
    min_gap = 3

    def can_place(index):
        if row[index] != '_':
            return False
        for other in placed:
            direct = abs(index - other)
            wrapped = width - direct
            if min(direct, wrapped) < min_gap:
                return False
        return True

    candidates = list(range(width))
    rng.shuffle(candidates)

    if with_speed:
        # Exclusive fast lane — only 'p' cars, same speed.
        car_target = rng.randint(1, 2)
        symbol = 'p'
    else:
        car_target = rng.randint(1, 2)
        symbol = 'u'

    for index in candidates:
        if len(placed) >= car_target:
            break
        if can_place(index):
            row[index] = symbol
            placed.append(index)

    return ''.join(row)


def _median_row(width, rng, allow_snake=False):
    """Safe grass between hazard blocks; sometimes a snake on later crossings."""
    if allow_snake and rng.random() < 0.45:
        row = [' '] * width
        start = rng.randint(0, width - 3)
        _place_run(row, start, 3, 's')
        return ''.join(row)
    return _grass_row(width)


def generate_map(level, width=MAP_WIDTH, rng=None):
    """
    Build a Frogger map that grows longer with each crossing.

    Level 1 is a short classic layout (water, then roads). Each later level
    adds more river and road rows. From level 3 onward, extra hazard sections
    are stacked so you can keep going further.
    """
    level = max(1, int(level))
    if rng is None:
        rng = random.Random()

    # Depth grows each crossing; inner section size is capped so late
    # crossings stay playable while still getting longer overall.
    water_depth = 2 + level
    road_depth = 2 + level
    extra_section_pairs = max(0, level - 2)
    inner_water = max(2, min(water_depth - 1, 5))
    inner_road = max(2, min(road_depth - 1, 5))

    # Top -> bottom: goal border, water (near goal), optional extra
    # road/water pairs, then roads above the frog's start.
    sections = [('water', water_depth)]
    for _ in range(extra_section_pairs):
        sections.append(('road', inner_road))
        sections.append(('water', inner_water))
    sections.append(('road', road_depth))

    rows = [_border_row(width), _grass_row(width)]
    for index, (kind, count) in enumerate(sections):
        if kind == 'water':
            for _ in range(count):
                rows.append(_water_row(width, rng))
        else:
            speed_lane = count // 2
            for lane in range(count):
                rows.append(_road_row(width, rng, with_speed=(lane == speed_lane)))
        if index < len(sections) - 1:
            rows.append(_median_row(width, rng, allow_snake=(level >= 2)))

    start = list(_grass_row(width))
    start[width // 2] = 'H'
    rows.append(''.join(start))
    rows.append(_border_row(width))
    return rows


symbols = {

    ' ':  [['        ',
            '        ',
            '        ',
            '        ',]],

    '-':  [['--------',
            '||||||||',
            '||||||||',
            '--------',]],

    '_':  [['        ',
            '________',
            '        ',
            '________',]],

    '^':  [['        ',
            '        ',
            '        ',
            '""""""""',]],

    'o':  [['        ',
            '        ',
            '--------',
            '--------',]],

    'H':  [['        ',
            '   o o  ',
            ' _|   |_',
            r' \  |  /',]],

    'u':  [['    _   ',
            '___| |__',
            ' |_____|',
            '__O___O_',],

           ['    _   ',
            '___| |__',
            ' |_____|',
            '__U___U_',],

           ['    _   ',
            '___| |__',
            ' |_____|',
            '__C___C_',]],

    'p':  [['        ',
            '__-----_',
            ' /_____\\',
            '__O___O_',]],

    's':  [['        ',
            '    ⦢ = ',
            '  ⦢     ',
            '⦢       ',],

           ['        ',
            '= = ⦥   ',
            '     ⦥  ',
            '       ⦥',],

           ['        ',
            '       ⦢',
            '     ⦢  ',
            ' = ⦢    ',]],

    'water_death':  [['        ',
                      '        ',
                      '   o o  ',
                      '""""""""',]],

    'car_death':    [['        ',
                      r' \ o o /',
                      ' _     _',
                      r' /  |  \\',]],

    'snake_death':  [['        ',
                      '        ',
                      '        ',
                      '   o o  ',]], }


if __name__ == "__main__":
    start_level = 1
    game = Game(generate_map(start_level), symbols, level=start_level)
    game.main_loop()
