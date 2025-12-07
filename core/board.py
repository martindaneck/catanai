# core/board.py

from typing import List, Dict, Optional, Tuple
import json

class Node:
    """
    A settlement/city position: there is 54 on a board
    """
    def __init__(self, node_id: int):
        self.id: int = node_id
        self.hexes: List[int] = [] # Hex IDs adjacent to this node
        self.port: str = ""  # Port type if any, else empty string
        self.occupant: int = 0  # 0 = empty, 1 = player 1 settlement, 2 = player 2 settlement, 3 = player 1 city, 4 = player 2 city
        self.neighbours: List[int] = []  # Node IDs adjacent to this node - there must be a road between them, used for traversing
        self.adjacent_roads: List[int] = []  # Road IDs connected to this node

    def __repr__(self):
        return f"Node({self.id}, occupant={self.occupant}, port={self.port})"
    

class HexTile:
    """
    A resource hex (wood, brick, sheep, wheat, ore): there are 18 on a board
    """
    def __init__(self, hex_id: int, resource: str, dice_number: int):
        self.id: int = hex_id
        self.resource: str = resource
        self.dice_number: int = dice_number
        self.probability: float = 0.0  # Probability of producing resources on a roll
        self.calculate_probability()
        self.nodes: List[int] = []  # Node IDs surrounding this hex

    def __repr__(self):
        return f"HexTile({self.id}, resource={self.resource}, dice_number={self.dice_number}, probability={self.probability})"
    
    def calculate_probability(self):
        """Calculate the probability of this hex producing resources based on its dice number."""
        dice_probabilities = {
            2: 1/36,
            3: 2/36,
            4: 3/36,
            5: 4/36,
            6: 5/36,
            8: 5/36,
            9: 4/36,
            10: 3/36,
            11: 2/36,
            12: 1/36
        }
        self.probability = dice_probabilities.get(self.dice_number, 0.0)


class Road:
    """
    Represents a road connecting two nodes
    """
    def __init__(self, road_id: int, node_a: int, node_b: int):
        self.id: int = road_id
        self.nodes: Tuple[int, int] = (node_a, node_b) # Node IDs this road connects
        self.owner: int = 0  # 0 = no road, 1 = player 1, 2 = player 2

    def __repr__(self):
        return f"Road({self.id}, nodes={self.nodes}, owner={self.owner})" 
    

class Board:
    """
    Represents the full state of the board:
    nodes, hexes, and roads
    """
    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.hexes: Dict[int, HexTile] = {}
        self.roads: Dict[int, Road] = {}
        self.ports: Dict[int, str] = {} # node_id to port type mapping

    # --- Initialization ---

    def load_from_json(self, path:str):
        """
        Populate the board from a JSON file, the nodes, hexes, and roads
        """
        with open(path, 'r') as f:
            data = json.load(f)
        
        # load hexes
        for hex_data in data['resource_hexes']:
            hex_tile = HexTile(hex_data['id'], hex_data['type'], hex_data['dice_number'])
            hex_tile.nodes = hex_data['village_spots']
            self.hexes[hex_tile.id] = hex_tile
        
        # load nodes
        for node_data in data['village_spots']:
            node = Node(node_data['id'])
            node.hexes = node_data['adjacent_hexes']
            node.adjacent_roads = node_data['adjacent_roads']
            node.occupant = 0  # Initially unoccupied
            node.port = node_data["port"]
            self.nodes[node.id] = node

        # load roads and link neighbours
        for road_data in data['roads']:
            road = Road(road_data['id'], road_data["village_ids"][0], road_data['village_ids'][1])
            road.owner = 0  # Initially unowned
            self.roads[road.id] = road

            # link neighbours
            node_a, node_b = road.nodes
            self.nodes[node_a].neighbours.append(node_b)
            self.nodes[node_b].neighbours.append(node_a)

        # link ports
        for port_data in data['ports']:
            port_type = port_data['type']
            village_ids = port_data['village_ids']
            for village_id in village_ids:
                self.nodes[village_id].port = port_type
                self.ports[village_id] = port_type

    # --- Game State Logic ---

    def settlement_is_legal(self, node_id: int, player: int, start_of_the_game: bool) -> bool:
        """
        Check if a player can build a settlement at the given node.
        
        if it's the first or second turn, they can build anywhere,
        otherwise they must follow the standard rules:
        - The node must be unoccupied.
        - The node must be connected to a road owned by the player.
        """
        node = self.nodes[node_id]
        if start_of_the_game:
            return node.occupant == 0  # Can build if unoccupied
        # else
        # check if node is occupied
        if node.occupant != 0:
            return False
        # check if node is connected to a road owned by the player
        connected_to_road = any(
            self.roads[road_id].owner == player
            for road_id in node.adjacent_roads
        )
        
        return connected_to_road


    
    def city_is_legal(self, node_id: int, player: int) -> bool:
        """
        Check if a player can build a city at the given node.
        
        - The node must be occupied by the player's settlement.
        """
        node = self.nodes[node_id]
        # Can build a city if the player has a settlement there
        return node.occupant == player
    
    
    def road_is_legal(self, road_id: int, player: int) -> bool:
        """
        Check if a player can build a road between the given nodes.
        
        - The road must be unowned.
        - The road must be connected to a settlement/city owned by the player.
        """
        road = self.roads[road_id]

        # Check if the road is unowned
        if road.owner != 0:
            return False
        
        # Check if either end of the road is connected to a settlement/city owned by the player
        node_a, node_b = road.nodes
        node_a_occupant = self.nodes[node_a].occupant
        node_b_occupant = self.nodes[node_b].occupant
        if node_a_occupant == player or node_b_occupant == player:
            return True
        
        # Check if the road is connected to a player's road
        connected_to_player_road = any(
            self.roads[adj_road_id].owner == player
            for adj_road_id in self.nodes[node_a].adjacent_roads + self.nodes[node_b].adjacent_roads
        )
        return connected_to_player_road

    def list_legal_settlement_spots(self, player: int, start_of_the_game: bool) -> List[int]:
        """
        List all legal spots for the player to build a settlement.
        """
        legal_spots = []
        for node_id in self.nodes:
            if self.settlement_is_legal(node_id, player, start_of_the_game):
                legal_spots.append(node_id)
        return legal_spots
    
    def list_legal_city_spots(self, player: int) -> List[int]:
        """
        List all legal spots for the player to build a city.
        """
        legal_spots = []
        for node_id in self.nodes:
            if self.city_is_legal(node_id, player):
                legal_spots.append(node_id)
        return legal_spots
    
    def list_legal_road_spots(self, player: int) -> List[int]:
        """
        List all legal spots for the player to build a road.
        """
        legal_spots = []
        for road_id in self.roads:
            if self.road_is_legal(road_id, player):
                legal_spots.append(road_id)
        return legal_spots
        
    

    # --- mutating state ---

    def set_settlement(self, node_id: int, player: int):
        """
        Build a settlement at the given node for the player.
        """
        node = self.nodes[node_id]
        node.occupant = player  # 1 = player 1 settlement, 2 = player 2 settlement
    
    def set_city(self, node_id: int, player: int):
        """
        Upgrade a settlement to a city at the given node for the player.
        """
        node = self.nodes[node_id]
        if node.occupant == player:
            node.occupant += 2  # 3 = player 1 city, 4 = player 2 city
    
    def set_road(self, road_id: int, player: int):
        """
        Build a road between the given nodes for the player.
        """
        road = self.roads[road_id]
        road.owner = player  # 1 = player 1, 2 = player 2
    

    # --- Query ---

    def get_production_for_roll(self, dice_roll: int) -> List[Tuple[int, str]]:
        """
        Get a mapping of player to resources produced for a given dice roll.
        Returns a list of tuples (player, resource).

        for each hex, that the dice number matches the dice roll:
        - for each node around the hex:
            - if occupied by a settlement, give 1 resource to the player
            - if occupied by a city, give 2 resources to the player
        """
        production: List[Tuple[int, str]] = []
        for hex_tile in self.hexes.values(): # check each hex
            if hex_tile.dice_number != dice_roll:
                continue  
            for node_id in hex_tile.nodes: # check each node around the hex
                node = self.nodes[node_id]
                if node.occupant == 0: # unoccupied, exit for loop
                    continue  # unoccupied
                resource = hex_tile.resource
                if node.occupant in [1, 2]:  # settlement
                    production.append((node.occupant, resource))
                elif node.occupant in [3, 4]:  # city
                    production.append((node.occupant - 2, resource))  # city produces 2 resources
                    production.append((node.occupant - 2, resource))
                    
        return production
    
    def get_available_actions(self, player: int):
        """
        Enumerate all available actions for the given player.
        """
        actions = {
            "build_settlement": self.list_legal_settlement_spots(player, False),
            "build_city": self.list_legal_city_spots(player),
            "build_road": self.list_legal_road_spots(player),
        }
        return actions

    # --- Utility ---

    def print_summary(self):
        print("Nodes:")
        for n in self.nodes.values():
            print(" ", n)
        print("\nHexes:")
        for h in self.hexes.values():
            print(" ", h)