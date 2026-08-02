## Main Objective

- You must design an efficient routing system that navigates a fleet of drones from a central start base to a target end location across a dynamic network.

- The primary goal is to ensure all drones reach their destination in the fewest possible simulation turns.

## Technical Constraints

- Language and Tools: The project must be written in Python 3.10 or later.  

- Type Safety and Style: The code must strictly adhere to the flake8 coding standard. It must also be completely typesafe using mypy.

- Paradigm: The project's development must be completely object-oriented.

- Prohibitions: You are strictly forbidden from using any external libraries for graph logic, such as networkx or graphlib.

- Automation: You must include a Makefile with the specific rules: install, run, debug, clean, and lint.

## Map Mechanics and Parsing

- DataReading: Your program must parse a file that defines the number of drones, a start_hub, an end_hub, standard zones, and their connections.

- Zone Types and Costs: Zones have specific types that dictate movement costs: normal costs 1 turn , restricted costs 2 turns , priority costs 1 turn , and blocked is entirely inaccessible.  

- Capacity Limits: You must adhere to the occupancy limits defined by max_drones for individual zones and max_link_capacity for connections. The start_hub and end_hub are exceptions, as they have no capacity limits.

- Error Handling: If an invalid zone type is parsed, it must raise a parsing error. Any other parsing error must halt the program and output a clear error message indicating the specific line and cause.

## Simulation and Output

- Simultaneous Movement: Drones are allowed to move simultaneously during a single turn. Your algorithm must manage these paths to avoid conflicts and deadlocks.

- Output Format: Each simulation turn must be printed as a single line listing all drone movements. The movements must follow a strict format, such as D1-roof1 D2-corridorA.  

- Visual Representation: You must provide visual feedback of the simulation, which can be achieved through colored terminal output, a graphical interface, or both.  

## Final Deliverables

- A fully working Python simulation codebase.

- A README.md file located at the root of your repository. This file must outline the project description, running instructions, resources used, AI utilization, and a detailed explanation of your algorithmic choices. 
