import numpy as np

class Sphere:
    def __init__(self, center, radius, texture_path=None):
        self.x, self.y, self.z = center
        self._sec_count = 36
        self._stack_count = 19
        self.radius = radius
        self.nodes = []
           
    def buildVertices(self):
        sec_step = 2 * np.pi / self._sec_count
        stack_step = np.pi / self._stack_count
        theta = 2 * np.pi * (sec_step/self._sec_count)
        phi = np.pi / 2 - np.pi * (stack_step/self._stack_count)

        for i in range(self._stack_count):
            theta = np.pi / 2 - i * stack_step
            xy = self.radius * np.cos(theta)
            z = self.radius * np.sin(theta)

            for j in range(self._sec_count):
                phi = j * sec_step
                x = xy * np.cos(phi) + self.x 
                y = xy * np.sin(phi) + self.y
                self.nodes.append((x, y, z))
        return self.nodes

    def buildEdges(self):
        edges = []
        for i in range(self._stack_count):
            for j in range(self._sec_count):
                current = i * self._sec_count + j
                next_longitude = i * self._sec_count + ((j + 1) % self._sec_count)
                edges.append((current, next_longitude))

                if i < self._stack_count - 1:
                    next_stack = (i + 1) * self._sec_count + j
                    edges.append((current, next_stack))

        return edges



           
class Edge:
    def __init__(self, start, end):
        self.start = start
        self.end = end

class Wireframe:
    def __init__(self):
        self.nodes = np.zeros((0, 4))
        self.edges = []
        self.texture_map = []
        self.center = (0,0,0)
        image = None
        self.texture = None
        self.texturePixels = None

    def addNodes(self, node_array):
        ones_column = np.ones((len(node_array), 1))
        ones_added = np.hstack((node_array, ones_column))
        self.nodes = np.vstack((self.nodes, ones_added))
    
    def addTexture(self, shape):
        self.nodeColor = shape.buildTexture()

    def addEdges(self, edgeList):
        self.edges += edgeList

    def transltionMatrix(dx=0, dy=0, dz=0):
        return np.array([[1, 0, 0, 0],
                         [0, 1, 0, 0],
                         [0, 0, 1, 0],
                         [dx, dy, dz, 1]])

    def scaleMatrix(sx=0, sy=0, sz=0):
        return np.array([[sx, 0, 0, 0],
                         [0, sy, 0, 0],
                         [0, 0, sz, 0],
                         [0, 0, 0, 1]])
    def transform(self, matrix):
        self.nodes = np.dot(self.nodes, matrix)
    def findCenter(self):
        """ Find the center of the wireframe """
        num_nodes = len(self.nodes)
        meanx = sum(node[0] for node in self.nodes) / num_nodes
        meany = sum(node[1] for node in self.nodes) / num_nodes
        meanz = sum(node[2] for node in self.nodes) / num_nodes
        return (meanx, meany, meanz)
    def rotateXMatrix(radians):
        """ Rotate the wireframe about the X axis by radians """
        c = np.cos(radians)
        s = np.sin(radians)
        return np.array([[1, 0, 0, 0],
                         [0, c, -s, 0],
                         [0, s, c, 0],
                         [0, 0, 0, 1]])
    
    def rotateYMatrix(radians):
        """ Rotate the wireframe about the Y axis by radians """
        c = np.cos(radians)
        s = np.sin(radians)
        return np.array([[c, 0, s, 0],
                         [0, 1, 0, 0],
                         [-s, 0, c, 0],
                         [0, 0, 0, 1]])
    def rotateZMatrix(radians):
        """ Rotate the wireframe about the Z axis by radians """
        c = np.cos(radians)
        s = np.sin(radians)
        return np.array([[c, -s, 0, 0],
                         [s, c, 0, 0],
                         [0, 0, 1, 0],
                         [0, 0, 0, 1]])

    def changeOrigin(center):
        dx, dy, dz = center
        return np.array([[1, 0, 0, 0],
                         [0, 1, 0, 0],
                         [0, 0, 1, 0],
                         [-dx, -dy, -dz, 1]])

    def outputNodes(self):
        print ("\n --- Nodes ---")
        for i, (x, y, z, _) in enumerate(self.nodes):
            print (" %d: (%d, %d, %d)" % (i, x, y, z))
            
    def outputEdges(self):
        print ("\n --- Edges ---")
        for i, (node1, node2) in enumerate(self.edges):
            print (" %d: %d -> %d" % (i, node1, node2))


if __name__ == "__main__":
    cube_nodes = [(x,y,z) for x in (0,1) for y in (0,1) for z in (0,1)]
    cube = Wireframe()
    cube.addNodes(np.array(cube_nodes))
    cube.addEdges([(n,n+4) for n in range(0,4)])
    cube.addEdges([(n,n+1) for n in range(0,8,2)])
    cube.addEdges([(n,n+2) for n in (0,1,4,5)])
    cube.outputNodes()
    cube.outputEdges()
