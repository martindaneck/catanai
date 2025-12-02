# core/board.py

from typing import List, Dict, Optional, Tuple


class Node:
    """
    A settlement/city position: there is 54 on a board
    """
    def __init__(self, node_id: int):
        self.id: int = node_id
        self.hexes: List[int] = []
        self.port: Optional[str] = None
        self.occupant: int = 0  # 0 = empty, 1 = player 1 settlement, 2 = player 2 settlement, 3 = player 1 city, 4 = player 2 city
        self.neighbors: List[int] = []  # adjacent nodes via roads

    def __repr__(self):
        return f"Node({self.id}, occupant={self.occupant}, port={self.port})"
    

class HexTile:
    """
    A resource hex (wood, brick, sheep, wheat, ore): there are 18 on a board
    """
    def __init__(self, hex_id: int, resource: str, dice_number: int, probability: float):
        self.id: int = hex_id
        self.resource: str = resource
        self.dice_number: int = dice_number
        self.probability: float = probability
        self.nodes: List[int] = []  # Node IDs surrounding this hex

    def __repr__(self):
        return f"HexTile({self.id}, resource={self.resource}, dice_number={self.dice_number}, probability={self.probability})"
    

class Board:
    """
    Represents the full state of the board:
    nodes, hexes, and roads
    """
    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.hexes: Dict[int, HexTile] = {}
        self.roads: Dict[Tuple[int, int], int] = {}  #{(n1, n2): owner}   0 = no road, 1 = player 1 road, 2 = player 2 road

    # --- Initialization ---

    def load_from_json(self, path:str):
        """Load nodes, hexes, ports and adjacency from a JSON."""
        raise NotImplementedError("Method load_from_json is not implemented yet.")
    

    # --- Game State Logic ---

    def can_build_settlement(self, node_id: int, player: int) -> bool:
        """Check if a player can build a settlement at the given node."""
        raise NotImplementedError("Method can_build_settlement is not implemented yet.")
    
    def can_build_city(self, node_id: int, player: int) -> bool:
        """Check if a player can build a city at the given node."""
        raise NotImplementedError("Method can_build_city is not implemented yet.")
    
    def can_build_road(self, n1: int, n2: int, player: int) -> bool:
        """Check if a player can build a road between the given nodes."""
        raise NotImplementedError("Method can_build_road is not implemented yet.")
    

    # --- mutating state ---

    def build_settlement(self, node_id: int, player: int):
        """Build a settlement at the given node for the player."""
        raise NotImplementedError("Method build_settlement is not implemented yet.")
    
    def build_city(self, node_id: int, player: int):
        """Upgrade a settlement to a city at the given node for the player."""
        raise NotImplementedError("Method build_city is not implemented yet.")
    
    def build_road(self, n1: int, n2: int, player: int):
        """Build a road between the given nodes for the player."""
        raise NotImplementedError("Method build_road is not implemented yet.")
    

    # --- Query ---

    def get_production_for_roll(self, dice_roll: int) -> List[Tuple[int, str]]:
        """Get a mapping of player to resources produced for a given dice roll.
        Returns a list of tuples (player, resource).
        """
        raise NotImplementedError("Method get_production_for_roll is not implemented yet.")
    
    def get_available_actions(self, player: int):
        """Enumerate all available actions for the given player."""
        raise NotImplementedError("Method get_available_actions is not implemented yet.")


    # --- Utility ---

    def print_summary(self):
        print("Nodes:")
        for n in self.nodes.values():
            print(" ", n)
        print("\nHexes:")
        for h in self.hexes.values():
            print(" ", h)