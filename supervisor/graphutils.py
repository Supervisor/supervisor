from collections import defaultdict
 
class Graph():
    def __init__(self,vertices):
        self.graph = defaultdict(list)
        self.V = vertices
 
    def addEdge(self,u,v):
        self.graph[u].append(v)

    def cyclic(self):
        """Return True if the directed graph has a cycle.
        The graph must be represented as a dictionary mapping vertices to
        iterables of neighbouring vertices. For example:

        >>> cyclic({1: (2,), 2: (3,), 3: (1,)})
        True
        >>> cyclic({1: (2,), 2: (3,), 3: (4,)})
        False

        """
        path = set()
        visited = set()

        def visit(vertex):
            if vertex in visited:
                return False
            visited.add(vertex)
            path.add(vertex)
            for neighbour in self.graph.get(vertex, ()):
                if neighbour in path or visit(neighbour):
                    return True
            path.remove(vertex)
            return False

        return any(visit(v) for v in self.graph)
