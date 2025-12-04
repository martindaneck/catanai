# core/game.py

import random
from typing import List, Dict

from core.board import Board
from core.player import Player, MAX_VILLAGES, MAX_CITIES, MAX_ROADS



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
        self.start_of_the_game = True  # special rules for initial turns

        # longest road tracking
        self.longest_road_owner = None
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


    #############################    
    ### core game progression ###
    #############################
    def turn_start(self):
        """runs at the start of each turn"""
        

        if not self.start_of_the_game:
            # roll dice and distribute resources
            roll = self.roll_dice()
            self.distribute_resources(roll)


        self.turn_number += 1

        if self.turn_number == 5: # turns 1-4 are initial placement, so on turn 5 we end it 
            self.start_of_the_game = False

        current_player = self.get_player(self.current_player_id)

        


    def perform_build_action(self, action_type: str, target_id: int) -> bool:
        """
        Game calls this to have the current player attempt build something.
        Returns True if successful, False otherwise.
        """
        current_player = self.get_player(self.current_player_id)

        if action_type == "build_settlement":
            success = current_player.build_settlement(self.board, target_id, self.start_of_the_game)
        elif action_type == "build_city":
            success = current_player.build_city(self.board, target_id)
        elif action_type == "build_road":
            success = current_player.build_road(self.board, target_id, self.start_of_the_game)
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
    def advance_one_action(self, action_type: str, target_id: int = -1):
        """
        External interface to advance the game by exactly one action.

        Human UI or AI agent calls
        game.advance_one_action(action_type, target_id).
        example: game.advance_one_action("build_settlement", node_id)

        action type is "start_turn" for starting the turn (rolling dice, distributing resources)
        action_type is one of "build_settlement", "build_city", "build_road"
        to attempt to perform that action on target_id.
        action_type is "end_turn" for ending the turn and switching to the next player

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
            if success:
                self.check_win_condition() # also finishes the game if win condition met
        elif action_type == "end_turn":
            self.switch_player()
            success = True
        else:
            success = False  # unknown action

        return success

      