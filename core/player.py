from typing import List, Dict, Set, TYPE_CHECKING

from .board import Board

# Resource costs for convenience
SETTLEMENT_COST = {
    "brick": 1,
    "wood": 1,
    "sheep": 1,
    "wheat": 1
}

CITY_COST = {
    "wheat": 2,
    "ore": 3
}

ROAD_COST = {
    "brick": 1,
    "wood": 1
}

MAX_VILLAGES, MAX_CITIES, MAX_ROADS = 5, 4, 15

class Player:
    """
    Simple player model for both human and ai agents.

    Holds resources and performs actions that mutate the board state.

    The evolutionary agents will extend this class,
    (they will be calling these methods).
    """

    def __init__(self, player_id: int):
        self.id = player_id
        self.resources: Dict[str, int] = {
            "brick": 0,
            "wood": 0,
            "sheep": 0,
            "wheat": 0,
            "ore": 0
        }
        self.built: Dict[str, int] = {
            "settlements": 0,
            "cities": 0,
            "roads": 0
        }
        self.ports: Set[str] = set() # resource types for which the player has ports (e.g., "brick", "wood", or "generic" for 3:1 port)

    ## resource helpers

    def add_resource(self, resource: str, amount: int = 1):
        self.resources[resource] += amount

    def has_resources(self, cost: Dict[str, int]) -> bool:
        return all(self.resources[r] >= amt for r, amt in cost.items())
    
    def deduct_resources(self, cost: Dict[str, int]):
        for r, amt in cost.items():
            self.resources[r] -= amt

    ## legality checkings

    def can_build_settlement(self, board: Board, node_id: int, free_settlement: bool) -> bool:  
        if self.built["settlements"] >= MAX_VILLAGES:
            return False
        if not board.settlement_is_legal(node_id, self.id, free_settlement):
            return False
        return self.has_resources(SETTLEMENT_COST) if not free_settlement else True
    
    def can_build_city(self, board: Board, node_id: int) -> bool:
        if self.built["cities"] >= MAX_CITIES:
            return False
        if not board.city_is_legal(node_id, self.id):
            return False
        return self.has_resources(CITY_COST)

    def can_build_road(self, board: Board, road_id: int, free_road: bool) -> bool:
        if self.built["roads"] >= MAX_ROADS:
            return False
        if not board.road_is_legal(road_id, self.id):
            return False
        return self.has_resources(ROAD_COST) if not free_road else True
    
    ## action methods

    def build_settlement(self, board: Board, node_id: int, free_settlement: bool) -> bool:
        # this theoretically shouldn't happen, but just in case (this method is called only for legal node_ids, if none, it won't be called)
        if not self.can_build_settlement(board, node_id, free_settlement): 
            return False

        if not free_settlement:
            self.deduct_resources(SETTLEMENT_COST)

        board.set_settlement(node_id, self.id)

        self.built["settlements"] += 1

        return True
    
    
    def build_city(self, board: Board, node_id: int) -> bool:
        # this theoretically shouldn't happen, but just in case (this method is called only for legal node_ids, if none, it won't be called)
        if not self.can_build_city(board, node_id):
            return False
        
        self.deduct_resources(CITY_COST)

        board.set_city(node_id, self.id)

        self.built["cities"] += 1
        self.built["settlements"] -= 1

        return True
    

    def build_road(self, board: Board, road_id: int, free_road: bool) -> bool:
        # this theoretically shouldn't happen, but just in case (this method is called only for legal node_ids, if none, it won't be called)
        if not self.can_build_road(board, road_id, free_road):
            return False

        if not free_road:
            self.deduct_resources(ROAD_COST)

        board.set_road(road_id, self.id)

        self.built["roads"] += 1

        return True
    

    ## query methods


    def get_available_settlement_spots(self, board: Board, free_settlement: bool) -> List[int]:
        if self.built["settlements"] >= MAX_VILLAGES:
            return []
        return board.list_legal_settlement_spots(self.id, free_settlement) if self.has_resources(SETTLEMENT_COST) or free_settlement else []


    def get_available_city_spots(self, board: Board) -> List[int]:
        if self.built["cities"] >= MAX_CITIES:
            return []
        return board.list_legal_city_spots(self.id) if self.has_resources(CITY_COST) else []

    def get_available_road_spots(self, board: Board, free_road: bool) -> List[int]:
        if self.built["roads"] >= MAX_ROADS:
            return []
        return board.list_legal_road_spots(self.id) if self.has_resources(ROAD_COST) or free_road else []
    


    def get_owned_settlements(self, board: Board):
        return [
            n.id 
            for n in board.nodes.values() 
            if n.occupant == self.id 
        ]
    
    def get_owned_cities(self, board: Board):
        return [
            n.id 
            for n in board.nodes.values() 
            if n.occupant == self.id + 2
        ]
    
    def get_owned_roads(self, board: Board):
        return [
            r.id 
            for r in board.roads.values() 
            if r.owner == self.id
        ]