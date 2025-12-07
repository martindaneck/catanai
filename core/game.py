# core/game.py

import random
from typing import List, Dict

from .board import Board
from .player import Player, MAX_VILLAGES, MAX_CITIES, MAX_ROADS



class Game:
    """
    Runs a full game of Catan between 2 players exactly.

    Board functions as the single source of truth for the game state.
    Both player 1 and player 2 mutate the board state via their actions.
    Game class handles turn order, dice rolls, production, and win condition,
    manages itself, dictates the game, board and player interactions.
    """

    def __init__(self, board: Board, p1: Player, p2: Player):
        self.board = board
        self.p1 = p1
        self.p2 = p2
        
        self.current_player_id = 1  # Player 1 starts
        self.turn_number = 0
        self.last_roll: List[tuple[int, int]] = []  # stores last dice roll(s), including re-rolls when 7s

        self.initial_buildings_placed = { # track initial placements - turn_number: [village_placed, road_placed]
            0: [False, False], 
            1: [False, False], 
            2: [False, False], 
            3: [False, False]}

        # longest road tracking
        self.longest_road_owner = 0 # 0 if no one, 1 if p1, 2 if p2
        self.longest_road_length = 5  # Minimum length to claim longest road

        # win condition
        self.finished = False
        self.winner = 0  # 0 if tie, 1 if p1, 2 if p2


    ### basic helper methods ###
    def get_player(self, player_id: int) -> Player:
        return self.p1 if player_id == 1 else self.p2
    
    def switch_player(self):
        self.current_player_id = 2 if self.current_player_id == 1 else 1

    ### dice rolling and production ###
    def roll_dice(self) -> list[tuple[int, int]]:
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        
        # if 7, append to return and roll again
        if die1 + die2 == 7:
            return [(die1, die2)] + self.roll_dice()
        else:
            return [(die1, die2)]
        
    def distribute_resources(self, roll: List[tuple[int, int]]):
        ## sums the last roll (because it's the only one non-7)
        total = roll[-1][0] + roll[-1][1] 
    
        production_events = self.board.get_production_for_roll(total)
        for player_id, resource in production_events:
            self.get_player(player_id).add_resource(resource)

    def handle_bank_trade(self, player: Player, offered: str, wanted: str, cost: int) -> bool:
        player.resources[offered] -= cost
        player.resources[wanted] += 1
        return True

    #############################    
    ### core game progression ###
    #############################
    def turn_start(self):
        """runs at the start of each turn"""
        self.turn_number += 1     # <- this number is how manyeth turn it is this turn

        if self.turn_number >= 4:
            # roll dice and distribute resources
            roll = self.roll_dice()
            self.distribute_resources(roll)
            self.last_roll = roll # store for UI display

        

        current_player = self.get_player(self.current_player_id)

        


    def perform_build_action(self, action_type: str, target_id: int) -> bool:
        """
        Game calls this to have the current player attempt build something.
        Returns True if successful, False otherwise.
        """
        current_player = self.get_player(self.current_player_id)

        if action_type == "build_settlement":
            if self.turn_number < 4:
                free_village = self.initial_buildings_placed[self.turn_number][0] == False
            else:
                free_village = False
            success = current_player.build_settlement(self.board, target_id, free_village)
            if self.turn_number < 4:
                self.initial_buildings_placed[self.turn_number][0] = success 
        elif action_type == "build_city":
            success = current_player.build_city(self.board, target_id)
        elif action_type == "build_road":
            if self.turn_number < 4:
                free_road = self.initial_buildings_placed[self.turn_number][1] == False
            else:
                free_road = False
            success = current_player.build_road(self.board, target_id, free_road)
            if self.turn_number < 4:
                self.initial_buildings_placed[self.turn_number][1] = success
        else:
            success = False  # unknown action

        return success
    

    ### win condition and scoring ###
    def calculate_victory_points(self, player: Player) -> int:
        points = 0
        points += player.built["settlements"]  # 1 point each
        points += player.built["cities"] * 2   # 2 points each

        # longest road
        if self.longest_road_owner == player.id:
            points += 2

        return points
    
    def update_longest_road(self):
        """
        Check both players' longest roads and update the game state if needed.
        """
        p1_road_length = self.board.calculate_longest_road(self.p1.id)
        p2_road_length = self.board.calculate_longest_road(self.p2.id)

        if p1_road_length >= self.longest_road_length and p1_road_length > p2_road_length:
            self.longest_road_owner = 1
            self.longest_road_length = p1_road_length
        elif p2_road_length >= self.longest_road_length and p2_road_length > p1_road_length:
            self.longest_road_owner = 2
            self.longest_road_length = p2_road_length
        # if tie or neither exceeds current longest, no change
    
    def check_win_condition(self):
        """
        Game ends when a player maxes all 3 structures
        Winner = whoever has more points at that time
        """

        def is_finished(p: Player) -> bool:
            return (
                p.built["settlements"] >= MAX_VILLAGES and
                p.built["cities"] >= MAX_CITIES and
                p.built["roads"] >= MAX_ROADS
            )
        
        p1_finished = is_finished(self.p1)
        p2_finished = is_finished(self.p2)

        if not (p1_finished or p2_finished):
            return  # game continues

        # If we reach this point, the game is finished
        self.finished = True
        
        p1_points = self.calculate_victory_points(self.p1)
        p2_points = self.calculate_victory_points(self.p2) 

        if p1_points > p2_points:
            self.winner = 1
        elif p2_points > p1_points:
            self.winner = 2
        else:
            self.winner = 0  # tie


    ### main single turn execution ###
    def advance_one_action(self, action_type: str, target_id):
        """
        External interface to advance the game by exactly one action.

        Human UI or AI agent calls
        game.advance_one_action(action_type, target_id).
        example: game.advance_one_action("build_settlement", node_id)

        action type is "start_turn" for starting the turn (rolling dice, distributing resources)
        action_type is one of "build_settlement", "build_city", "build_road"
        to attempt to perform that action on target_id.
        action_type is "end_turn" for ending the turn and switching to the next player
        action_type is "trade_bank" for trading with the bank, target_id is a tuple (offered_resource, wanted_resource, cost)

        After something is built, check for win condition and end the game if met.

        Returns True if action was successful, False otherwise.
        """
        if self.finished:
            return False  # game already over

        current_player = self.get_player(self.current_player_id)

        success = False

        if action_type == "start_turn":
            self.turn_start()
            success = True
        elif action_type in {"build_settlement", "build_city", "build_road"}:
            success = self.perform_build_action(action_type, target_id)
            if success and action_type in {"build_road", "build_settlement"}:
                self.update_longest_road()
            if success:
                self.check_win_condition() # also finishes the game if win condition met
        elif action_type == "end_turn": # do not switch when the turn number is 1. turn order is P1, P2, P2, P1 for turns 0-3 to set up initial placements
            if self.turn_number != 1:
                self.switch_player()
            success = True
        elif action_type == "trade_bank":
            offered, wanted, cost = target_id  # unpack tuple
            success = self.handle_bank_trade(current_player, offered, wanted, cost)
        else:
            success = False  # unknown action

        return success


    ##### Longest Road Calculation #####
    
    def update_longest_road(self):
        """
        Compute longest road for both players.
        Apply Catan rules:
        - Roads cannot pass THROUGH opponents' settlements.
        - Roads still count on the open side if only one endpoint is blocked.
        - If tie: longest_road_owner = 0.
        """

        p1_len = self._compute_longest_road_for_player(1)
        p2_len = self._compute_longest_road_for_player(2)

        # No one reaches minimum threshold
        best = max(p1_len, p2_len)
        if best < self.longest_road_length:
            self.longest_road_owner = 0
            return

        # Tie
        if p1_len == p2_len:
            self.longest_road_owner = 0
            return

        # Unique winner
        if p1_len > p2_len:
            self.longest_road_owner = 1
        else:
            self.longest_road_owner = 2


    def _player_road_graph(self, player_id: int):
        """
        Build adjacency list for player's road graph.
        Cannot pass THROUGH an opponent settlement.
        But roads touching a blocked node still count from the free endpoint.
        """
        if player_id == 1:
            blocked = {2, 4}   # opponent has 2 (settlement) or 4 (city)
        else:
            blocked = {1, 3}

        adj = {}

        for road in self.board.roads.values():
            if road.owner != player_id:
                continue

            a, b = road.nodes
            a_blocked = self.board.nodes[a].occupant in blocked
            b_blocked = self.board.nodes[b].occupant in blocked

            # Both ends blocked → unusable
            if a_blocked and b_blocked:
                continue

            # If A is not blocked, add A → B
            if not a_blocked:
                adj.setdefault(a, []).append(b)

            # If B is not blocked, add B → A
            if not b_blocked:
                adj.setdefault(b, []).append(a)

        return adj
    

    def _dfs_longest_path(self, graph, current, visited_edges):
        """
        DFS computing longest simple path through edges.
        graph[node] = list of connected nodes.
        visited_edges = set of (min(a,b), max(a,b)) tuples.
        """
        best = 0

        for nxt in graph.get(current, []):
            edge = (min(current, nxt), max(current, nxt))
            if edge in visited_edges:
                continue

            visited_edges.add(edge)
            length = 1 + self._dfs_longest_path(graph, nxt, visited_edges)
            visited_edges.remove(edge)

            if length > best:
                best = length

        return best
    

    def _compute_longest_road_for_player(self, player_id: int) -> int:
        graph = self._player_road_graph(player_id)

        if not graph:
            return 0

        longest = 0

        # Try starting from every node in the player's graph
        for node in graph:
            length = self._dfs_longest_path(graph, node, set())
            if length > longest:
                longest = length

        return longest



      
    ##### GAME STATE QUERY METHODS #####
    
    def get_ui_state(self) -> Dict:
        """
        Return a JSON-serializable snapshot intended for the TUI.
        {
            "current_player_id": int,
            "turn_number": int,
            "last_rolls": [(d1,d2), ...],             # list of tuples for current turn (may be empty)
            "resources_cp": {res: count, ...},
            "resources_op": {res: count, ...},
            "available_villages_cp": [node_ids...],
            "available_roads_cp": [road_ids...],
            "available_cities_cp": [node_ids...],
            "available_trade_offers_cp": {offered_resource: [(wanted_resource, cost), ...], ...},
        }
        """
        cp = self.p1 if self.current_player_id == 1 else self.p2
        p1 = self.p1
        p2 = self.p2
        op = self.p2 if self.current_player_id == 1 else self.p1

        # fetch lists from players (pass board where needed)
        if self.turn_number < 4:
            free_village = self.initial_buildings_placed[self.turn_number][0] == False
        else:
            free_village = False

        if self.turn_number < 4:
            free_road = self.initial_buildings_placed[self.turn_number][1] == False
        else:
            free_road = False

        av_v_cp = sorted(cp.get_available_settlement_spots(
            self.board, free_village)) if self.current_player_id == 1 else []

        av_r_cp = sorted(cp.get_available_road_spots(
            self.board, free_road)) if self.current_player_id == 1 else []
        av_r_op = sorted(op.get_available_road_spots(
            self.board, free_road)) if self.current_player_id == 2 else []

        av_c_cp = sorted(cp.get_available_city_spots(self.board)) if self.current_player_id == 1 else []

        av_to_cp = cp.get_available_trade_offers(self.board) if self.current_player_id == 1 else {}


        state = {
            "current_player_id": self.current_player_id,
            "turn_number": self.turn_number,
            "last_rolls": list(self.last_roll),  # copy safe
            "resources_cp": dict(cp.resources),
            "resources_op": dict(op.resources),
            "available_villages_cp": av_v_cp,
            "available_roads_cp": av_r_cp,
            "available_cities_cp": av_c_cp,
            "available_trade_offers_cp": av_to_cp,
        }
        return state

