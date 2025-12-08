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
      - Up/Down: move between rows (Finish, Village, Road, City, etc.)
      - Left/Right or mouse-wheel or 'h'/'l': scroll options for active player
      - Enter: execute selected action (for active player)
    """

    ACTION_ROWS = ["finish", "village", "road", "city", "trade_receive", "trade_give"]

    def __init__(self, stdscr, game: Game):
        self.stdscr = stdscr
        self.game = game

        # per-player selection indices for each action (keeps position when switching player)
        self.selection = {
            1: {"village": 0, "road": 0, "city": 0, "trade_receive": 0, "trade_give": 0},
            2: {"village": 0, "road": 0, "city": 0, "trade_receive": 0, "trade_give": 0},
        }
        self.selected_resource_to_receive = {
            1: None,
            2: None
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
        curses.init_pair(6, curses.COLOR_GREEN, -1)   # grass
        curses.init_pair(7, curses.COLOR_RED, -1)     # brick
        curses.init_pair(8, curses.COLOR_YELLOW, -1)  # wheat
        curses.init_pair(9, curses.COLOR_WHITE, -1)    # ore

        self.C_DEFAULT = curses.color_pair(1)
        self.C_P1 = curses.color_pair(2) | curses.A_BOLD
        self.C_P2 = curses.color_pair(3) | curses.A_BOLD
        self.C_HL = curses.color_pair(4) | curses.A_BOLD
        self.C_DICE = curses.color_pair(5) | curses.A_BOLD
        self.C_GRASS = curses.color_pair(6) | curses.A_BOLD
        self.C_BRICK = curses.color_pair(7) | curses.A_BOLD
        self.C_WHEAT = curses.color_pair(8) | curses.A_BOLD
        self.C_ORE = curses.color_pair(9) | curses.A_BOLD

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
            elif key in (curses.KEY_LEFT, ord('h')):
                self.on_left()
            elif key in (curses.KEY_RIGHT, ord('l')):
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
            lst = state["available_villages_cp"]
            idx = self._safe_index(lst, self.selection[active]["village"])
            self.selection[active]["village"] = self._safe_index(lst, idx - 1)
        elif row == "road":
            lst = state["available_roads_cp"]
            idx = self._safe_index(lst, self.selection[active]["road"])
            self.selection[active]["road"] = self._safe_index(lst, idx - 1)
        elif row == "city":
            lst = state["available_cities_cp"]
            idx = self._safe_index(lst, self.selection[active]["city"])
            self.selection[active]["city"] = self._safe_index(lst, idx - 1)
        elif row == "trade_receive":
            trade_offers = state["available_trade_offers_cp"]
            lst = list(trade_offers.keys())
            idx = self._safe_index(lst, self.selection[active]["trade_receive"])
            self.selection[active]["trade_receive"] = self._safe_index(lst, idx - 1)
            lst_list = list(lst)
            self.selected_resource_to_receive[active] = lst_list[self.selection[active]["trade_receive"]] if lst_list else None
        elif row == "trade_give":
            trade_offers = state["available_trade_offers_cp"]
            # this ungodly statement builds a list of strings like "wood x2", "sheep x3", etc.
            lst = [str(trade_offers[self.selected_resource_to_receive[active]][i][0]) + " x" + str(trade_offers[self.selected_resource_to_receive[active]][i][1]) for i in range(len(trade_offers[self.selected_resource_to_receive[active]]))] if trade_offers[self.selected_resource_to_receive[active]] else []
            idx = self._safe_index(lst, self.selection[active]["trade_give"])
            self.selection[active]["trade_give"] = self._safe_index(lst, idx - 1)

    def on_right(self):
        """Scroll right for active player's current row's selection"""
        state = self.game.get_ui_state()
        active = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]
        if row == "village":
            lst = state["available_villages_cp"]
            idx = self._safe_index(lst, self.selection[active]["village"])
            self.selection[active]["village"] = self._safe_index(lst, idx + 1)
        elif row == "road": 
            lst = state["available_roads_cp"]
            idx = self._safe_index(lst, self.selection[active]["road"])
            self.selection[active]["road"] = self._safe_index(lst, idx + 1)
        elif row == "city":
            lst = state["available_cities_cp"]
            idx = self._safe_index(lst, self.selection[active]["city"])
            self.selection[active]["city"] = self._safe_index(lst, idx + 1)
        elif row == "trade_receive":
            trade_offers = state["available_trade_offers_cp"]
            lst = list(trade_offers.keys())
            idx = self._safe_index(lst, self.selection[active]["trade_receive"])
            self.selection[active]["trade_receive"] = self._safe_index(lst, idx + 1)
            lst_list = list(lst)
            self.selected_resource_to_receive[active] = lst_list[self.selection[active]["trade_receive"]] if lst_list else None
        elif row == "trade_give":
            trade_offers = state["available_trade_offers_cp"]
            lst = [str(trade_offers[self.selected_resource_to_receive[active]][i][0]) + " x" + str(trade_offers[self.selected_resource_to_receive[active]][i][1]) for i in range(len(trade_offers[self.selected_resource_to_receive[active]]))] if trade_offers[self.selected_resource_to_receive[active]] else []
            idx = self._safe_index(lst, self.selection[active]["trade_give"])
            self.selection[active]["trade_give"] = self._safe_index(lst, idx + 1)

    def on_enter(self):
        state = self.game.get_ui_state()
        active = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]

        if row == "finish":
            self.game.advance_one_action("end_turn")
            self.game.advance_one_action("start_turn")
            # this is potentially the point where AI makes its move
            return

        if row == "village":
            lst = state["available_villages_cp"]
            if not lst:
                return
            
            idx = self._safe_index(lst, self.selection[active][row])
            self.selection[active][row] = idx
            target = lst[idx]

            self.game.advance_one_action("build_settlement", target)

        elif row == "road":
            lst = state["available_roads_cp"]
            if not lst:
                return
            
            idx = self._safe_index(lst, self.selection[active][row])
            self.selection[active][row] = idx
            target = lst[idx]

            self.game.advance_one_action("build_road", target)

        elif row == "city":
            lst = state["available_cities_cp"]
            if not lst:
                return

            idx = self._safe_index(lst, self.selection[active][row])
            self.selection[active][row] = idx
            target = lst[idx]
            
            self.game.advance_one_action("build_city", target)

        elif row == "trade_give":
            trade_offers = state["available_trade_offers_cp"]
            resource_to_receive = self.selected_resource_to_receive[active]
            if resource_to_receive is None:
                return
            lst = trade_offers[resource_to_receive] if trade_offers[resource_to_receive] else []
            if not lst:
                return

            idx = self._safe_index(lst, self.selection[active][row])
            self.selection[active][row] = idx
            resource_to_give, cost = lst[idx]
            cost = int(cost)    

            self.game.advance_one_action("trade_bank", (resource_to_receive, resource_to_give, cost))


    # --- drawing ---
    def draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        half_y = max_y // 2  
        half_y += 5

        state = self.game.get_ui_state()

        # determine highlighted map item
        highlight_id = None
        cp = state["current_player_id"]
        row = self.ACTION_ROWS[self.selected_row]

        if row == "village":
            lst = state["available_villages_cp"]
            if lst:
                highlight_id = (1,lst[self.selection[cp]["village"]])
        elif row == "road":
            lst = state["available_roads_cp"]
            if lst:
                highlight_id = (2,lst[self.selection[cp]["road"]])
        elif row == "city":
            lst = state["available_cities_cp"]
            if lst:
                highlight_id = (1,lst[self.selection[cp]["city"]])

        # top half = inline node map
        self.draw_map(0, 0, half_y, max_x, highlight_id)

        # bottom half split: dice panel (left eighth), player panel (right 7/8)
        dice_w = max_x // 8
        self.draw_dice(half_y, 0, max_y - half_y, dice_w, state)
        self.draw_player_panel(half_y, dice_w + 1, max_y - half_y, max_x - (dice_w + 1), state)

        # footer help
        footer = "Arrows or hjkl to navigate — Enter to act — q to quit"
        try:
            self.stdscr.addstr(max_y - 1, max(0, (max_x - len(footer))//2), footer, self.C_DEFAULT)
        except curses.error:
            pass

        


        self.stdscr.refresh()

    def draw_map(self, y, x, h, w, highlight_id=None):
        """
        Draws the map character by character utilizing braille dots for edges and other characters for nodes.
        """
        board = self.game.board

        # used characters for map: dots are roads, X villages, @ cities, • empty nodes, NN = hex number, r = resource
        """example layout (inaccurate):
        
              ⢀⡤•⢤⡀	⢀⡤•⢤⡀          
             •⠋ r ⠙X⠋ r ⠙@
             ⡇ NN  ⡇ NN  ⡇
             •⣄ r ⣠X⣄ r ⣠•
              ⠈⠓@⠋⠁r⠈⠓X⠋⠁
                ⡇ NN   ⡇
                •⣄ r ⣠X
                 ⠈⠓•⠋⠁
        """   

        nothing_ = ""
        newline_ = "\n"

        r = {}# road list: key: NNX where NN is road_id, X is braille char configuration; value: (char, color)
        for road_id, road in board.roads.items():
            occ = road.owner  # 0=empty, 1=p1, 2=p2

            color = self.C_HL if highlight_id == (2, road_id) else self.C_P1 if occ == 1 else self.C_P2 if occ == 2 else self.C_DEFAULT

            if road_id in (69,71,43,67,28,12,31,65,26,5,7,32,38,10,2,17,50,37,21,19,52,58,56,54):
                r.setdefault(f"{road_id:02d}1", ("⠋", color))  # -> r["691"] = ("⠋", color)
                r.setdefault(f"{road_id:02d}2", ("⢀", color))
                r.setdefault(f"{road_id:02d}3", ("⡤", color))
            elif road_id in (68,41,30,45,66,27,6,14,47,64,52,4,1,16,62,23,9,18,51,60,36,35,53,25,49):
                r.setdefault(f"{road_id:02d}1", ("⡇", color))
            else:
                r.setdefault(f"{road_id:02d}1", ("⢤", color))
                r.setdefault(f"{road_id:02d}2", ("⡀", color))
                r.setdefault(f"{road_id:02d}3", ("⠙", color))

        n = {}# nodelist: key: NN0 where NN is node_id, value: (char, color)
        for node_id, node in board.nodes.items():
            occ = node.occupant

            color = self.C_HL if highlight_id == (1, node_id) else self.C_P1 if occ in (1,3) else self.C_P2 if occ in (2,4) else  self.C_DEFAULT

            char = "•" if occ == 0 else "X" if occ in (1,2) else "@"
            n.setdefault(f"{node_id:02d}0", (char, color))

        d = {} # decoration list: key: NNX where NN is hex_id, X is 0 for decoration, 1 for left-half-of-number, 2 for right-half-of-number; value: (char, color)
        for hex_id, hex_tile in board.hexes.items():
            res = hex_tile.resource
            num = hex_tile.dice_number

            res_char = "↑" if res == "wood" else "v" if res == "sheep" else "■" if res == "brick" else "W" if res == "wheat" else "■" if res == "ore" else " "
            color = self.C_GRASS if res == "wood" else self.C_GRASS if res == "sheep" else self.C_BRICK if res == "brick" else self.C_WHEAT if res == "wheat" else self.C_ORE if res == "ore" else self.C_DEFAULT

            d.setdefault(f"{hex_id:02d}0", (res_char, color))

            num_char_1 = str(num)[0] if num >= 10 else " "
            num_char_2 = str(num)[1] if num >= 10 else str(num)
            d.setdefault(f"{hex_id:02d}1", (num_char_1, self.C_DEFAULT))
            d.setdefault(f"{hex_id:02d}2", (num_char_2, self.C_DEFAULT))

        ports = {} # port list: key: X where X is port type; value: (char, color)
        for p in range(6):
            port_char = "G" if p == 0 else "B" if p == 1 else "W" if p == 2 else "S" if p == 3 else "W" if p == 4 else "O" if p == 5 else " "
            port_color = self.C_DICE if p == 0 else self.C_BRICK if p == 1 else self.C_GRASS if p == 2 else self.C_GRASS if p == 3 else self.C_WHEAT if p == 4 else self.C_ORE if p == 5 else self.C_DEFAULT
            ports[p] = (port_char, port_color)

        map = [
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,ports[4],nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,ports[0],r["692"],r["693"],n["520"],r["701"],r["702"],nothing_,r["712"],r["713"],n["240"],r["421"],r["422"],nothing_,r["432"],r["433"],n["260"],r["441"],r["442"],nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,n["510"],r["691"],d["000"],nothing_,nothing_,r["703"],n["530"],r["711"],nothing_,nothing_,nothing_,r["423"],n["250"],r["431"],nothing_,d["020"],nothing_,r["443"],n["270"],nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,r["681"],nothing_,d["001"],d["002"],d["000"],nothing_,r["411"],nothing_,d["011"],d["012"],d["010"],nothing_,r["301"],d["020"],d["021"],d["022"],nothing_,d["020"],r["451"],nothing_,ports[5],nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,r["672"],r["673"],n["500"],r["401"],r["402"],d["000"],r["282"],r["283"],n["230"],r["291"],r["292"],nothing_,r["122"],r["123"],n["070"],r["131"],r["132"],d["020"],r["312"],r["313"],n["280"],r["461"],r["462"],nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,n["490"],r["671"],d["030"],nothing_,nothing_,r["403"],n["220"],r["281"],d["040"],d["040"],nothing_,r["293"],n["060"],r["121"],d["050"],nothing_,d["050"],r["133"],n["080"],r["311"],nothing_,nothing_,d["060"],r["463"],n["290"],nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,ports[2],r["661"],nothing_,d["031"],d["032"],nothing_,nothing_,r["271"],d["040"],d["041"],d["042"],nothing_,d["040"],r["061"],nothing_,d["051"],d["052"],nothing_,nothing_,r["141"],nothing_,d["061"],d["062"],nothing_,d["060"],r["471"],nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,r["652"],r["653"],n["480"],r["391"],r["392"],nothing_,r["262"],r["263"],n["210"],r["111"],r["112"],d["040"],r["052"],r["053"],n["000"],r["001"],r["002"],d["050"],r["072"],r["073"],n["090"],r["151"],r["152"],d["060"],r["322"],r["323"],n["300"],r["481"],r["482"],nothing_,nothing_,newline_,
            nothing_,n["470"],r["651"],d["070"],d["070"],d["070"],r["393"],n["200"],r["261"],nothing_,d["080"],nothing_,r["113"],n["050"],r["051"],nothing_,nothing_,nothing_,r["003"],n["010"],r["071"],d["090"],nothing_,nothing_,r["153"],n["100"],r["321"],d["100"],d["100"],d["100"],r["483"],n["310"],nothing_,newline_,
            nothing_,r["641"],nothing_,d["071"],d["072"],nothing_,nothing_,r["251"],nothing_,d["081"],d["082"],nothing_,d["080"],r["041"],nothing_,nothing_,nothing_,nothing_,nothing_,r["011"],nothing_,d["091"],d["092"],d["090"],nothing_,r["161"],nothing_,d["101"],d["102"],d["100"],nothing_,r["491"],ports[0],newline_,
            nothing_,n["460"],r["631"],r["632"],d["070"],r["382"],r["383"],n["190"],r["241"],r["242"],nothing_,r["102"],r["103"],n["040"],r["031"],r["032"],nothing_,r["022"],r["023"],n["020"],r["081"],r["082"],nothing_,r["172"],r["173"],n["110"],r["331"],r["332"],d["100"],r["502"],r["503"],n["320"],nothing_,newline_,
            nothing_,nothing_,nothing_,r["633"],n["450"],r["381"],d["110"],nothing_,nothing_,r["243"],n["180"],r["101"],nothing_,d["120"],nothing_,r["033"],n["030"],r["021"],nothing_,nothing_,d["130"],r["083"],n["120"],r["171"],nothing_,nothing_,d["140"],r["333"],n["330"],r["501"],nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,ports[1],r["621"],d["110"],d["111"],d["112"],d["110"],d["110"],r["231"],nothing_,d["121"],d["122"],nothing_,nothing_,r["091"],d["130"],d["131"],d["132"],nothing_,nothing_,r["181"],d["140"],d["141"],d["142"],d["140"],nothing_,r["511"],nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,n["440"],r["611"],r["612"],d["110"],r["372"],r["373"],n["170"],r["221"],r["222"],d["120"],r["212"],r["213"],n["150"],r["201"],r["202"],d["130"],r["192"],r["193"],n["130"],r["341"],r["342"],d["140"],r["522"],r["523"],n["340"],nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,r["613"],n["430"],r["371"],nothing_,d["150"],nothing_,r["223"],n["160"],r["211"],d["160"],nothing_,d["160"],r["203"],n["140"],r["191"],nothing_,d["170"],nothing_,r["343"],n["350"],r["521"],nothing_,ports[3],nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,r["601"],d["150"],d["151"],d["152"],d["150"],nothing_,r["361"],d["160"],d["161"],d["162"],d["160"],d["160"],r["351"],nothing_,d["171"],d["172"],d["170"],nothing_,r["531"],nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,n["420"],r["591"],r["592"],d["150"],r["582"],r["583"],n["400"],r["571"],r["572"],nothing_,r["562"],r["563"],n["380"],r["551"],r["552"],nothing_,r["542"],r["543"],n["360"],nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,ports[0],nothing_,r["593"],n["410"],r["581"],nothing_,nothing_,nothing_,r["573"],n["390"],r["561"],ports[0],nothing_,nothing_,r["553"],n["370"],r["541"],nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
            nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,nothing_,newline_,
        ]
        
        for item in map:
            if item == nothing_:
                self.stdscr.addstr(y, x, " ", self.C_DEFAULT)
                x += 1
            elif item == newline_:
                y += 1
                x = 0
            else:
                char, color = item
                try:
                    self.stdscr.addstr(y, x, char, color)
                except curses.error:
                    pass
                x += 1


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
        """
        top line looks like "{CP} bunch of space {OP} a little less space Turn: N" CP and OP are colored
        the left three-quarters is for current player, right quarter for opponent
        this panel is divided into 4 horizontal sections (columns):
        1. Available main actions (row labels 1-4)
        2. Player resources (5 lines)
        3. Trade offers (row labels 5-6)
        4. Opponent info (Opponent's resources)

        Each action row shows available options in [ ... ] with current selection highlighted.
        """
        # determine widths by percentage
        col_1_w = int(w * 0.30)
        col_2_w = int(w * 0.25)
        col_3_w = int(w * 0.28)
        col_4_w = w - (col_1_w + col_2_w + col_3_w)  # remainder

        cp = state["current_player_id"]
        op = 2 if cp == 1 else 1
        
        # header line
        header = f"{' ' * (w - 10)} Turn: {state['turn_number']}"
        try:
            self.stdscr.addstr(y, x, header, self.C_DEFAULT)
            self.stdscr.addstr(y, x, f"P{cp}", self.C_P1 if cp == 1 else self.C_P2)
            self.stdscr.addstr(y, x + w - col_4_w, f"P{op}", self.C_P1 if op == 1 else self.C_P2)
        except curses.error:
            pass

        # --- Columns start at y + 2 ---
        left_x = x
        right_x = x + w - col_4_w
        top_y = y

        start_y = top_y + 2

        # --- Column 1: Actions ---
        action_labels = ["Finish Turn", "Build Village", "Build Road", "Build City"]
        action_keys = ["finish", "village", "road", "city"]

        try:
            self.stdscr.addstr(start_y, left_x + 1, "Actions:", curses.A_BOLD)
        except curses.error:
            pass

        for i, (label, key) in enumerate(zip(action_labels, action_keys)):
            row_y = start_y + i * 2
            active = (self.selected_row == i)
            attr = self.C_HL if active else self.C_DEFAULT

            # Draw label
            try:
                self.stdscr.addstr(row_y + 1, left_x + 1, f"{label}:", attr)
            except curses.error:
                pass

            # Draw list for village/road/city
            if key != "finish":
                if key == "city":
                    lst = state.get(f"available_cities_cp", [])
                else:
                    lst = state.get(f"available_{key}s_cp", [])
                sel = self._safe_index(lst, self.selection[cp][key])
                self.selection[cp][key] = sel
                self._draw_list(row_y + 1, left_x + col_1_w // 2 - 2, lst, sel, active=active)
            else:
                try:
                    self.stdscr.addstr(row_y + 1, left_x + col_1_w // 2 - 2, "[]", attr)
                except curses.error:
                    pass

        # --- Column 2: Resources ---
        res_y = start_y
        try:
            self.stdscr.addstr(res_y, left_x + col_1_w + 1, "Resources:", curses.A_BOLD)
        except curses.error:
            pass
        self.draw_resources(res_y + 1, left_x + col_1_w + 1, state[f"resources_cp"])

        # --- Column 3: Trade Receive ---
        trade_y = start_y
        try:
            self.stdscr.addstr(trade_y, left_x + col_1_w + col_2_w + 1, "Trade Receive:", curses.A_BOLD)
        except curses.error:
            pass

        trade_offers = state["available_trade_offers_cp"]
        lst_receive = list(trade_offers.keys())
        sel_receive = self._safe_index(lst_receive, self.selection[cp]["trade_receive"])
        self.selection[cp]["trade_receive"] = sel_receive
        self.selected_resource_to_receive[cp] = lst_receive[sel_receive] if lst_receive else None
        self._draw_list(trade_y + 1, left_x + col_1_w + col_2_w + 1, lst_receive, sel_receive,
                        active=(True))

        # --- Column 3: Trade Give ---
        try:
            self.stdscr.addstr(trade_y + 4, left_x + col_1_w + col_2_w + 1, "Trade Give:", curses.A_BOLD)
        except curses.error:
            pass

        if self.selected_resource_to_receive[cp] and trade_offers.get(self.selected_resource_to_receive[cp]):
            lst_give = [f"{res} x{amt}" for res, amt in trade_offers[self.selected_resource_to_receive[cp]]]
        else:
            lst_give = []
        sel_give = self._safe_index(lst_give, self.selection[cp]["trade_give"])
        self.selection[cp]["trade_give"] = sel_give
        self._draw_list(trade_y + 5, left_x + col_1_w + col_2_w + 1, lst_give, sel_give,
                        active=(self.selected_row == 5))

        # --- Column 4: Opponent Resources ---
        try:
            self.stdscr.addstr(start_y, right_x + 1, f"P{op} Resources:", curses.A_BOLD)
        except curses.error:
            pass
        self.draw_resources(start_y + 1, right_x + 1, state[f"resources_op"])

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
