import os
import time
import random
import threading
import traceback

from Game_Display import GD
from getch import getch

class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, target, args):
        super(StoppableThread, self).__init__(target=target, args=args)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

class Game(object):

    def __init__(self, map, symbols):
        """
        Initialize the game

        :param map: <list> A list of strings containing simple map
        :param symbols: <dict> Contains all the graphics for our symbols
        """
        # Initialize game display, includes the Display Map
        self.GD = GD(map, symbols)
        # GD makes a copy of the Symbol Map as a list of lists
        self.act_map = self.GD.act_map

        #Initialize the different objects in the map
        self.player = Player('H', self)
        self.logs = self.init_objects('o', 3, Log)
        self.cars = self.init_objects('u', 1, Car)
        self.cars.append(self.init_objects('p', 1, SpeedCar)[0])
        self.snakes = self.init_objects('s', 3, Snake)

        # Initialize shared list between __main__ and thread for input
        self.input = [None]
        self.thread = StoppableThread(target=self.get_input,
                                        args=(self.input, ))

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
        Prints Display Map in players environment with info
        """
        y_range, x_range = self.player_env(100, len(self.GD.map[0]))
        self.GD.print_map(y_range, x_range)

        # for i in self.act_map:
            # print(''.join(i))

        p_coords = self.player.coords
        actp_coords = self.GD.trans_coords(p_coords, "disp_map")
        c_coords = self.cars[0].coords[0]
        actc_coords = self.GD.trans_coords(c_coords, "disp_map")

        time_elapsed = round(time.perf_counter() - self.start, 2)
        if time_elapsed > 1:
            fps = self.frame / time_elapsed
        else:
            fps = 0

        # print("Yrange and xrange: {} {}".format(y_range,x_range))
        # print("Player coords: {}".format(p_coords))
        # print("Act_map player coords: {}".format(actp_coords))
        # print("First car coords: {}".format(c_coords))
        # print("Act_map car coords: {}".format(actc_coords))
        # print("Time elapsed: {}".format(time_elapsed))
        # print("FPS: {}".format(round(fps, 2)))

        print("Up[w], Down[s], Left[a], Right[d] or Exit[x]")


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
            input = self.input[0]
            self.input[0] = None

            if input == 'x':
                self.kill()
            elif input == 'w':
                move = "Up"
            elif input == 's':
                move = "Down"
            elif input == 'a':
                move = "Left"
            elif input == 'd':
                move = "Right"
            else:
                return False

            self.player.update(move)
            return True

    def update_map(self):
        """Updates all objects in map"""
        for log in self.logs:
            log.update()

        for car in self.cars:
            car.update()

        for snake in self.snakes:
            snake.update()

    def get_input(self, input):
        """
        Thread that gets keyboard input from user

        :param input: <list> List of len(1) that both threads share
        """
        while True:
            input[0] = getch()
            if threading.current_thread().stopped():
                exit()

    def main_loop(self):
        """The main loop of the game"""
        # Clear screen once at the beginning
        os.system('clear')
        # Start thread which checks for input and alternate terminal screen
        self.thread.start()

        # Loop forever, printing game approx. FPS per second
        self.FPS = 40
        self.frame = 1
        tick = 0

        self.start = time.perf_counter()
        try:
            while True:
                self.action()
                self.update_map()

                if self.timer(self.FPS):
                    print("\033[H", end='')
                    self.print_game()
                    self.frame += 1

                self.sleeper(tick)
                tick += 1
        except Exception:
            traceback.print_exc()
            self.kill()

        self.kill()

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

    def dead(self, message= ' '):
        """
        Prints the map once more to show final death screen,
        prints final message and then kills program
        """
        os.system('clear')
        self.print_game()
        print("Sorry but you died. " + message)
        self.kill()

    def kill(self):
        """
        Waits for thread to stop properly
        """
        print("Press any key to exit.")
        self.thread.stop()
        self.thread.join()
        exit()


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

        pos_y, pos_x = self.GD.trans_coords(position, "disp_map")
        symbol = self.act_map[pos_y][pos_x]

        if symbol in [' ', 'o', '_']:
            self.move_position(self.coords, position)
            self.replace = symbol
            return True
        elif symbol == '^':
            self.move_position(self.coords, position)
            self.GD.display("water_death", position)
            self.game.dead("You poor fellow drowned.")
        elif symbol == 'u':
            self.move_position(self.coords, position)
            self.GD.display("car_death", position)
            self.game.dead("You jumped on a car...SPLAT!")

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



maze2=     ['------------',
            '            ',
            '^^^^ooo^^^^^',
            '^^^^^^^ooo^^',
            '^ooo^^^^^^^^',
            '            ',
            '___u_u_u_u_u',
            '_p__________',
            'u_u_u___u_u_',
            '     H      ',
            '------------']

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
            ' \  |  /',]],

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
                      ' \ o o /',
                      ' _     _',
                      ' /  |  \\',]],

    'snake_death':  [['        ',
                      '        ',
                      '        ',
                      '   o o  ',]], }


if __name__ == "__main__":
    game = Game(maze2, symbols)
    game.main_loop()
