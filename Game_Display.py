class GD(object):

    def __init__(self, map, symbols):
        self._symbols = symbols

        # Size of one map unit in y, x length
        empty_block = self.get(' ')
        self.size = (len(empty_block), len(empty_block[0]))

        self.map = self.trans_map(map)
        self.act_map = [list(i) for i in map]

    def get(self, symbol, symbol_num=0):
        """Returns a copy of the transformed symbol"""
        return self._symbols[symbol][symbol_num][:]

    def print_map(self, y_range, x_range):
        new_map = [i[x_range[0]:x_range[1]]
                    for i in self.map[y_range[0]: y_range[1]]]
        for i in new_map:
            print(''.join(i))

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
        #Start the new lines, one symbol turns into multiple lines
        new_lines = self.get(line[0])

        #For each symbol, retrieve its map and add each line to the
        #corresponding line in new_lines
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
