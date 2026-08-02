# Fly-in Map Format Specification

Every map file for the Fly-in simulation follows a strict line-by-line configuration.

## 1. Global Rules

- Comments: Any line or inline text starting with # is ignored by the parser.

- Drone Count: The very first line of the file must define the number of drones using the syntax nb_drones: <positive_integer>.

## 2. Zone Definitions
Zones (or nodes in the graph) are defined with specific prefixes, a unique name, and integer coordinates.

- Start Zone: start_hub: <name> <x> <y> [metadata] (There must be exactly one).

- End Zone: end_hub: <name> <x> <y> [metadata] (There must be exactly one).

- Standard Zone: hub: <name> <x> <y> [metadata].  

- Naming Constraints: Zone names must be unique and can contain any valid characters except dashes (-) and spaces.  

## 3. Zone Metadata (Optional)

Metadata can be added to any zone. It must be enclosed in brackets [...] and the tags can appear in any order.

- zone=<type> (Default: normal ):
    
    - normal: Costs 1 turn to traverse.
    - priority: Costs 1 turn to traverse, but should be prioritized by the pathfinding algorithm.
    - restricted: Costs 2 turns to traverse (drones must arrive at the destination after the specified turns and cannot wait on the connection).
    - blocked: Inaccessible zone; any path passing through here is invalid.

- color=<string> (Default: none ): Used for visual representation in the terminal or GUI. Accepts any single-word string (e.g., red, blue).

- max_drones=<positive_integer> (Default: 1 ): The maximum number of drones that can occupy the zone at the same time.
    
    - Note: This limit is ignored for the start_hub and end_hub, as they have infinite capacity.

## 4. Connections (Edges)
Connections define the paths between two defined zones.

- Syntax: connection: <zoneA>-<zoneB> [metadata].

- Routing Rules: Connections are strictly bidirectional.

- Duplicates: A connection cannot be defined more than once (e.g., if a-b exists, b-a is a duplicate and thus invalid).

- Connection Metadata: * max_link_capacity=<positive_integer> (Default: 1 ): Limits how many drones can traverse this specific connection simultaneously.

## 5. Error Handling

- Any invalid zone type, syntax error, or negative capacity value must immediately halt the program.

- The program must output a clear error message indicating the specific line and the cause of the failure.  
