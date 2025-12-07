# tui_overseer.py
import curses
import curses.panel
import time

from core.board import Board
from core.player import Player
from core.game import Game


# --- small utility to center a windowed slice with sel_index in middle when possible
def centered_window(lst, sel_index, width=5):
    n = len(lst)
    if n == 0:
        return [], 0
    half = width // 2
    start = max(0, sel_index - half)
    end = start + width
    if end > n:
        end = n
        start = max(0, end - width)
    return lst[start:end], start


class TuiOverseer:
    """
    Single-file terminal UI for the game.
    Layout:
      - Top half: map prototype (inline node list)
      - Bottom half:
          left quarter: dice panel
          right three-quarters: player panel (P1 left half, P2 right half)
    Navigation:
      - Up/Down: move between rows (Finish, Village, Road, City, Resources)
      - Left/Right or mouse-wheel or 'a'/'d': scroll options for active player
      - Enter: execute selected action (for active player)
    """

    ACTION_ROWS = ["finish", "village", "road", "city", "resources"]

    def __init__(self, stdscr, game: Game):
        self.stdscr = stdscr
        self.game = game

        # per-player selection indices for each action (keeps position when switching player)
        self.selection = {
            1: {"village": 0, "road": 0, "city": 0},
            2: {"village": 0, "road": 0, "city": 0},
        }

        # which row (index into ACTION_ROWS) is currently highlighted
        self.selected_row = 0

        # curses init
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, -1)   # default
        curses.init_pair(2, curses.COLOR_BLUE, -1)    # p1
        curses.init_pair(3, curses.COLOR_MAGENTA, -1) # p2
        curses.init_pair(4, curses.COLOR_YELLOW, -1)  # highlight
        curses.init_pair(5, curses.COLOR_CYAN, -1)    # dice color

        self.C_DEFAULT = curses.color_pair(1)
        self.C_P1 = curses.color_pair(2) | curses.A_BOLD
        self.C_P2 = curses.color_pair(3) | curses.A_BOLD
        self.C_HL = curses.color_pair(4) | curses.A_BOLD
        self.C_DICE = curses.color_pair(5) | curses.A_BOLD

        # enable mouse events for scroll wheel if terminal supports it
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

        # small delay for getch blocking behavior
        self.stdscr.timeout(100)  # ms

    # safe index utility
    def _safe_index(self, lst, idx):
        """Clamp index safely to valid range."""
        if not lst:
            return 0
        if idx < 0:
            return 0
        if idx >= len(lst):
            return len(lst) - 1
        return idx  

    # --- main loop ---
    def run(self):
        while True:
            self.draw()
            key = self.stdscr.getch()
            if key == -1:
                continue

            if key == ord('q'):
                break

            if key == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()
                except Exception:
                    continue
                # handle wheel: BUTTON4_PRESSED = wheel up, BUTTON5_PRESSED = wheel down
                if bstate & curses.BUTTON4_PRESSED:
                    self.on_left()
                elif bstate & curses.BUTTON5_PRESSED:
                    self.on_right()
                continue

            # navigation keys
            if key in (curses.KEY_UP, ord('k')):
                self.on_up()
            elif key in (curses.KEY_DOWN, ord('j')):
                self.on_down()
            elif key in (curses.KEY_LEFT, ord('a')):
                self.on_left()
            elif key in (curses.KEY_RIGHT, ord('d')):
                self.on_right()
            elif key in (10, 13, curses.KEY_ENTER):
                self.on_enter()
            # ignore others

    # --- navigation actions ---
    def on_up(self):
        self.selected_row = max(0, self.selected_row - 1)

    def on_down(self):
        self.selected_row = min(len(self.ACTION_ROWS) - 1, self.selected_row + 1)

    def on_left(self):
        """Scroll left for active player's current row's selection"""
        state = self.game.get_ui_state()
        active = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]
        if row == "village":
            lst = state[f"available_villages_p{active}"]
            idx = self._safe_index(lst, self.selection[active]["village"])
            self.selection[active]["village"] = self._safe_index(lst, idx - 1)
        elif row == "road":
            lst = state[f"available_roads_p{active}"]
            idx = self._safe_index(lst, self.selection[active]["road"])
            self.selection[active]["road"] = self._safe_index(lst, idx - 1)
        elif row == "city":
            lst = state[f"available_cities_p{active}"]
            idx = self._safe_index(lst, self.selection[active]["city"])
            self.selection[active]["city"] = self._safe_index(lst, idx - 1)

    def on_right(self):
        """Scroll right for active player's current row's selection"""
        state = self.game.get_ui_state()
        active = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]
        if row == "village":
            lst = state[f"available_villages_p{active}"]
            idx = self._safe_index(lst, self.selection[active]["village"])
            self.selection[active]["village"] = self._safe_index(lst, idx + 1)
        elif row == "road": 
            lst = state[f"available_roads_p{active}"]
            idx = self._safe_index(lst, self.selection[active]["road"])
            self.selection[active]["road"] = self._safe_index(lst, idx + 1)
        elif row == "city":
            lst = state[f"available_cities_p{active}"]
            idx = self._safe_index(lst, self.selection[active]["city"])
            self.selection[active]["city"] = self._safe_index(lst, idx + 1)

    def on_enter(self):
        state = self.game.get_ui_state()
        active = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]

        if row == "finish":
            self.game.advance_one_action("end_turn")
            self.game.advance_one_action("start_turn")
            return

        if row == "village":
            lst = state[f"available_villages_p{active}"]
            if not lst:
                return
            
            idx = self._safe_index(lst, self.selection[active][row])
            self.selection[active][row] = idx
            target = lst[idx]

            self.game.advance_one_action("build_settlement", target)

        elif row == "road":
            lst = state[f"available_roads_p{active}"]
            if not lst:
                return
            
            idx = self._safe_index(lst, self.selection[active][row])
            self.selection[active][row] = idx
            target = lst[idx]

            self.game.advance_one_action("build_road", target)

        elif row == "city":
            lst = state[f"available_cities_p{active}"]
            if not lst:
                return

            idx = self._safe_index(lst, self.selection[active][row])
            self.selection[active][row] = idx
            target = lst[idx]
            
            self.game.advance_one_action("build_city", target)


    # --- drawing ---
    def draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        half_y = max_y // 2

        state = self.game.get_ui_state()

        # determine highlighted map item
        highlight_id = None
        cp = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]

        if row == "village":
            lst = state[f"available_villages_p{cp}"]
            if lst:
                highlight_id = (1,lst[self.selection[cp]["village"]])
        elif row == "road":
            lst = state[f"available_roads_p{cp}"]
            if lst:
                highlight_id = (2,lst[self.selection[cp]["road"]])
        elif row == "city":
            lst = state[f"available_cities_p{cp}"]
            if lst:
                highlight_id = (1,lst[self.selection[cp]["city"]])

        # top half = inline node map
        self.draw_map(0, 0, half_y, max_x, highlight_id)

        # bottom half split: dice panel (left quarter), player panel (right 3/4)
        dice_w = max_x // 4
        self.draw_dice(half_y, 0, max_y - half_y, dice_w, state)
        self.draw_player_panel(half_y, dice_w + 1, max_y - half_y, max_x - (dice_w + 1), state)

        # footer help
        footer = "Arrows / a d to scroll — Enter to act — q to quit"
        try:
            self.stdscr.addstr(max_y - 1, max(0, (max_x - len(footer))//2), footer, self.C_DEFAULT)
        except curses.error:
            pass

        


        self.stdscr.refresh()

    def draw_map(self, y, x, h, w, highlight_id=None):
        # prototype: inline nodes like `n0. n1v n2c n3. ...` wrapped into lines to fit width
        board = self.game.board
        items = []
        for nid, node in board.nodes.items():
            occ = node.occupant
            if occ == 0:
                mark = "."
                color = self.C_DEFAULT
            elif occ == 1:
                mark = "v" if occ in (1,) else "."
                color = self.C_P1
            elif occ == 2:
                mark = "v"
                color = self.C_P2
            elif occ == 3:
                mark = "c"
                color = self.C_P1
            elif occ == 4:
                mark = "c"
                color = self.C_P2
            else:
                mark = "."
                color = self.C_DEFAULT

            # 🔥 highlight selected node
            if highlight_id == (1, nid):
                color = self.C_HL

            items.append((f"n{nid}{mark}", color))

        # Add roads inline the same way
        for rid, road in board.roads.items():
            occ = road.owner  # 0=empty, 1=p1, 2=p2
            if occ == 0:
                mark = "."
                color = self.C_DEFAULT
            elif occ == 1:
                mark = "/"
                color = self.C_P1
            elif occ == 2:
                mark = "/"
                color = self.C_P2
            else:
                mark = "."
                color = self.C_DEFAULT

            # 🔥 highlight selected road
            if highlight_id == (2, rid):
                color = self.C_HL

            items.append((f"r{rid}{mark}", color))

        # layout items inline with spacing
        row = y
        col = x
        max_col = x + w - 1
        for txt, color in items:
            txt2 = txt + " "
            if col + len(txt2) > max_col:
                row += 1
                col = x
                if row >= y + h:
                    break
            try:
                self.stdscr.addstr(row, col, txt2, color)
            except curses.error:
                pass
            col += len(txt2)

    def draw_dice(self, y, x, h, w, state):
        """
        Draws the recent dice as compact ASCII dice.
        Each roll is two dice side-by-side.
        """

        # Unicode pip
        pip = "●"

        # Predefined pip patterns for a 3x3 grid
        # (row, col) => pip position inside the 3×3 inner area
        dice_patterns = {
            1: {(1, 1)},
            2: {(0, 0), (2, 2)},
            3: {(0, 0), (1, 1), (2, 2)},
            4: {(0, 0), (0, 2), (2, 0), (2, 2)},
            5: {(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)},
            6: {(0, 0), (0, 2), (1, 0), (1, 2), (2, 0), (2, 2)},
        }

        def draw_single_die(top_y, left_x, value):
            # top border
            try:
                self.stdscr.addstr(top_y, left_x,  "┌───────┐", self.C_DICE)
            except curses.error:
                pass

            # inside pip rows
            for r in range(3):
                line = "│"
                for c in range(3):
                    if (r, c) in dice_patterns[value]:
                        line += f" {pip}"
                    else:
                        line += "  "
                line += " │"
                try:
                    self.stdscr.addstr(top_y + 1 + r, left_x, line, self.C_DICE)
                except curses.error:
                    pass

            # bottom border
            try:
                self.stdscr.addstr(top_y + 4, left_x, "└───────┘", self.C_DICE)
            except curses.error:
                pass

        # Draw header
        try:
            self.stdscr.addstr(y, x + 1, "Dice:", self.C_DICE | curses.A_BOLD)
        except curses.error:
            pass

        rolls = state.get("last_rolls", [])

        # reverse order: most recent on top
        rolls = list(reversed(rolls))

        draw_y = y + 2

        for (d1, d2) in rolls:
            if draw_y + 5 > y + h:
                break

            draw_single_die(draw_y, x + 1, d1)
            draw_single_die(draw_y, x + 10, d2)

            draw_y += 6  # space below dice

        if not rolls:
            try:
                self.stdscr.addstr(y + 2, x + 1, "(no rolls yet)", self.C_DEFAULT)
            except curses.error:
                pass

    def draw_player_panel(self, y, x, h, w, state):
        # left half = p1, right half = p2
        half_w = w // 2
        left_x = x
        right_x = x + half_w
        cp = state["current_player_id"]
        turn_str = f"Turn {state['turn_number']}"

        # Header
        try:
            self.stdscr.addstr(y, left_x + 2, "P1", self.C_P1 | (curses.A_BOLD if cp == 1 else curses.A_DIM))
            self.stdscr.addstr(y, right_x + 2, "P2", self.C_P2 | (curses.A_BOLD if cp == 2 else curses.A_DIM))
            self.stdscr.addstr(y, x + w - len(turn_str) - 2, turn_str, self.C_DEFAULT | curses.A_BOLD)
        except curses.error:
            pass

        # Rows list
        rows_y = y + 2
        labels = [
            ("Finish turn", "finish"),
            ("Build Village", "village"),
            ("Build Road", "road"),
            ("Build City", "city")
        ]

        # Explicit mapping so city → cities (not "citys")
        KEYMAP_P1 = {
            "village": "available_villages_p1",
            "road": "available_roads_p1",
            "city": "available_cities_p1"
        }
        KEYMAP_P2 = {
            "village": "available_villages_p2",
            "road": "available_roads_p2",
            "city": "available_cities_p2"
        }

        for i, (label, key) in enumerate(labels):
            row_y = rows_y + i*2

            # label left
            attr_left = self.C_HL if (self.selected_row == i and cp == 1) else self.C_DEFAULT
            try:
                self.stdscr.addstr(row_y, left_x + 1, f"{label}:", attr_left)
            except curses.error:
                pass

            # label right
            attr_right = self.C_HL if (self.selected_row == i and cp == 2) else self.C_DEFAULT
            try:
                self.stdscr.addstr(row_y, right_x + 1, f"{label}:", attr_right)
            except curses.error:
                pass

            # finish-turn rows get simple []
            if key == "finish":
                try:
                    self.stdscr.addstr(row_y, left_x + 20, "[]", attr_left)
                    self.stdscr.addstr(row_y, right_x + 20, "[]", attr_right)
                except curses.error:
                    pass
                continue

            # --- P1 LIST ---
            lst_key = KEYMAP_P1.get(key)
            lst = state.get(lst_key, [])
            sel = self._safe_index(lst, self.selection[1][key])
            self.selection[1][key] = sel

            sx = left_x + 20
            self._draw_list(row_y, sx, lst, sel, active=(cp == 1 and self.selected_row == i))

            # --- P2 LIST ---
            lst_key2 = KEYMAP_P2.get(key)
            lst2 = state.get(lst_key2, [])
            sel2 = self._safe_index(lst2, self.selection[2][key])
            self.selection[2][key] = sel2

            sx2 = right_x + 20
            self._draw_list(row_y, sx2, lst2, sel2, active=(cp == 2 and self.selected_row == i))

        # Resources section
        res_y = rows_y + len(labels)*2 + 1
        try:
            self.stdscr.addstr(res_y, left_x + 1, "Resources:", curses.A_BOLD)
        except curses.error:
            pass
        self.draw_resources(res_y + 1, left_x + 1, state["resources_p1"])

        try:
            self.stdscr.addstr(res_y, right_x + 1, "Resources:", curses.A_BOLD)
        except curses.error:
            pass
        self.draw_resources(res_y + 1, right_x + 1, state["resources_p2"])

    def draw_resources(self, y, x, resources):
        # layout:
        # Wood: W W W
        # Brick: B B
        # Wheat: H H
        # Sheep: S S
        # Ore: O
        try:
            wood = " ".join("W" for _ in range(resources.get("wood", 0)))
            brick = " ".join("B" for _ in range(resources.get("brick", 0)))
            wheat = " ".join("H" for _ in range(resources.get("wheat", 0)))
            sheep = " ".join("S" for _ in range(resources.get("sheep", 0)))
            ore = " ".join("O" for _ in range(resources.get("ore", 0)))

            self.stdscr.addstr(y, x, f"Wood: {wood}", self.C_DEFAULT)
            self.stdscr.addstr(y+1, x, f"Brick: {brick}", self.C_DEFAULT)
            self.stdscr.addstr(y+2, x, f"Wheat: {wheat}", self.C_DEFAULT)
            self.stdscr.addstr(y+3, x, f"Sheep: {sheep}", self.C_DEFAULT)
            self.stdscr.addstr(y+4, x, f"Ore: {ore}", self.C_DEFAULT)
        except curses.error:
            pass

    def _draw_list(self, row_y, sx, lst, sel, active):
        """Draws a list inside [ ... ] always correctly."""
        # Opening bracket
        try:
            self.stdscr.addstr(row_y, sx, "[", self.C_DEFAULT)
        except curses.error:
            pass
        sx += 1

        # Empty → just closing bracket
        if not lst:
            try:
                self.stdscr.addstr(row_y, sx, "]", self.C_DEFAULT)
            except curses.error:
                pass
            return

        # Non-empty: windowed
        window, start = centered_window(lst, sel, width=5)
        for iwin, val in enumerate(window):
            idx = start + iwin
            col = self.C_HL if (idx == sel and active) else self.C_DEFAULT
            text = f" {val} "
            try:
                self.stdscr.addstr(row_y, sx, text, col)
            except curses.error:
                pass
            sx += len(text)

        # Closing bracket
        try:
            self.stdscr.addstr(row_y, sx, "]", self.C_DEFAULT)
        except curses.error:
            pass



# --- entry point ---
def main(stdscr):
    # load board, players, game
    board = Board()
    board.load_from_json("data/board.json")

    p1 = Player(1)
    p2 = Player(2)
    game = Game(board, p1, p2)

    tui = TuiOverseer(stdscr, game)
    tui.run()


if __name__ == "__main__":
    curses.wrapper(main)
