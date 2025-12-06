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
            if lst:
                self.selection[active]["village"] = max(0, self.selection[active]["village"] - 1)
        elif row == "road":
            lst = state[f"available_roads_p{active}"]
            if lst:
                self.selection[active]["road"] = max(0, self.selection[active]["road"] - 1)
        elif row == "city":
            lst = state[f"available_cities_p{active}"]
            if lst:
                self.selection[active]["city"] = max(0, self.selection[active]["city"] - 1)

    def on_right(self):
        """Scroll right for active player's current row's selection"""
        state = self.game.get_ui_state()
        active = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]
        if row == "village":
            lst = state[f"available_villages_p{active}"]
            if lst:
                self.selection[active]["village"] = min(len(lst)-1, self.selection[active]["village"] + 1)
        elif row == "road":
            lst = state[f"available_roads_p{active}"]
            if lst:
                self.selection[active]["road"] = min(len(lst)-1, self.selection[active]["road"] + 1)
        elif row == "city":
            lst = state[f"available_cities_p{active}"]
            if lst:
                self.selection[active]["city"] = min(len(lst)-1, self.selection[active]["city"] + 1)

    def on_enter(self):
        """Execute action for active player"""
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
            idx = self.selection[active]["village"]
            target = lst[idx]
            self.game.advance_one_action("build_settlement", target)
            # update longest road can be triggered by game logic already if you call update there

        if row == "road":
            lst = state[f"available_roads_p{active}"]
            if not lst:
                return
            idx = self.selection[active]["road"]
            target = lst[idx]
            self.game.advance_one_action("build_road", target)

        if row == "city":
            lst = state[f"available_cities_p{active}"]
            if not lst:
                return
            idx = self.selection[active]["city"]
            target = lst[idx]
            self.game.advance_one_action("build_city", target)

    # --- drawing ---
    def draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        half_y = max_y // 2

        state = self.game.get_ui_state()

        # top half = inline node map
        self.draw_map(0, 0, half_y, max_x)

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

    def draw_map(self, y, x, h, w):
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
        # draws last_rolls list vertically
        rolls = state.get("last_rolls", [])
        try:
            self.stdscr.addstr(y, x + 1, "Dice:", self.C_DICE | curses.A_BOLD)
        except curses.error:
            pass
        r = y + 2
        for d in rolls:
            if r >= y + h:
                break
            text = f"{d[0]} + {d[1]}"
            try:
                self.stdscr.addstr(r, x + 1, text, self.C_DICE)
            except curses.error:
                pass
            r += 1
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

        # Header names
        try:
            self.stdscr.addstr(y, left_x + 2, "P1", self.C_P1 | (curses.A_BOLD if cp == 1 else curses.A_DIM))
            self.stdscr.addstr(y, right_x + 2, "P2", self.C_P2 | (curses.A_BOLD if cp == 2 else curses.A_DIM))
            self.stdscr.addstr(y, x + w - len(turn_str) - 2, turn_str, self.C_DEFAULT | curses.A_BOLD)

        except curses.error:
            pass

        # Rows: Finish | Build Village | Build Road | Build City | Resources
        rows_y = y + 2
        labels = [("Finish turn", "finish"), ("Build Village", "village"), ("Build Road", "road"), ("Build City", "city")]

        for i, (label, key) in enumerate(labels):
            row_y = rows_y + i*2
            # left column (P1)
            is_selected = (self.selected_row == i)
            attr = self.C_HL if (is_selected and cp == 1) else self.C_DEFAULT
            try:
                self.stdscr.addstr(row_y, left_x + 1, f"{label}:", attr)
            except curses.error:
                pass

            # right column (P2)
            is_selected_p2 = (self.selected_row == i)
            attr2 = self.C_HL if (is_selected_p2 and cp == 2) else self.C_DEFAULT
            try:
                self.stdscr.addstr(row_y, right_x + 1, f"{label}:", attr2)
            except curses.error:
                pass

            # draw options lists if active player matches column
            # P1 options
            lst_key_p1 = {
                "village": "available_villages_p1",
                "road": "available_roads_p1",
                "city": "available_cities_p1"
            }.get(key, None)

            if key == "finish":
                # show [] box
                try:
                    self.stdscr.addstr(row_y, left_x + 20, "[]", attr)
                    self.stdscr.addstr(row_y, right_x + 20, "[]", attr2)
                except curses.error:
                    pass
            else:
                if lst_key_p1:
                    lst1 = state.get(lst_key_p1, [])
                    sel1 = self.selection[1][key]
                    window1, start1 = centered_window(lst1, sel1, width=5)
                    sx = left_x + 20
                    for iwin, val in enumerate(window1):
                        global_idx = start1 + iwin
                        if global_idx == sel1 and cp == 1 and self.selected_row == i:
                            # highlighted selected
                            try:
                                self.stdscr.addstr(row_y, sx, f" {val} ", self.C_HL)
                            except curses.error:
                                pass
                        else:
                            try:
                                self.stdscr.addstr(row_y, sx, f" {val} ", self.C_DEFAULT)
                            except curses.error:
                                pass
                        sx += len(f" {val} ")
                # P2 options
                lst_key_p2 = {
                    "village": "available_villages_p2",
                    "road": "available_roads_p2",
                    "city": "available_cities_p2"
                }.get(key, None)
                if lst_key_p2:
                    lst2 = state.get(lst_key_p2, [])
                    sel2 = self.selection[2][key]
                    window2, start2 = centered_window(lst2, sel2, width=5)
                    sx2 = right_x + 20
                    for iwin, val in enumerate(window2):
                        global_idx = start2 + iwin
                        if global_idx == sel2 and cp == 2 and self.selected_row == i:
                            try:
                                self.stdscr.addstr(row_y, sx2, f" {val} ", self.C_HL)
                            except curses.error:
                                pass
                        else:
                            try:
                                self.stdscr.addstr(row_y, sx2, f" {val} ", self.C_DEFAULT)
                            except curses.error:
                                pass
                        sx2 += len(f" {val} ")

        # Resources area below
        res_y = rows_y + len(labels)*2 + 1
        try:
            self.stdscr.addstr(res_y, left_x + 1, "Resources:", curses.A_BOLD)
        except curses.error:
            pass
        # P1 resources
        r1 = state["resources_p1"]
        self.draw_resources(res_y + 1, left_x + 1, r1)
        # P2 resources
        try:
            self.stdscr.addstr(res_y, right_x + 1, "Resources:", curses.A_BOLD)
        except curses.error:
            pass
        r2 = state["resources_p2"]
        self.draw_resources(res_y + 1, right_x + 1, r2)

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
