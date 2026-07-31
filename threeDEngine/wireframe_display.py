from . import wireframe as wf
import pygame
import numpy as np

class ProjectionViewer:
    """ Displays a wireframe model on a pygame screen """

    def __init__(self, panel, label, dimensions, pos):
        self.width, self.height = dimensions
        self.x, self.y = pos
        self.surf = pygame.Surface((self.width, self.height))
        self.panel = panel
        self.background = (30, 30, 30)
        self.wireframes = {}
        self.displayNodes = False
        self.displayEdges = False
        self.displayTextures = True
        self.nodeColor = (230, 230, 230)
        self.edgeColor = (150, 150, 150)
        self.nodeRadius = 1.3
        self.label = label
        panel.add(self)

    def prepare(self):
        pass

    
    def translateAll(self, vector):
        """ Translate all wireframes by the given vector """
        matrix = wf.Wireframe.transltionMatrix(*vector)
        for wireframe in self.wireframes.values():
            wireframe.transform(matrix)

    def scaleAll(self, scale):
        """ Scale all wireframes by scale """
        matrix = wf.Wireframe.scaleMatrix(scale, scale, scale)
        for wireframe in self.wireframes.values():
            wireframe.transform(matrix)
    def rotateAll(self, axis, theta):
        rotateFunction = 'rotate' + axis + 'Matrix'

        for wireframe in self.wireframes.values():
            x, y, z = wireframe.findCenter()
            wireframe.transform(wf.Wireframe.changeOrigin((x, y, z)))
            wireframe.transform(getattr(wf.Wireframe, rotateFunction)(theta))
            wireframe.transform(wf.Wireframe.changeOrigin((-x, -y, -z)))

    def rotateFrame(wireframe, axis, theta):
        x, y, z = wireframe.findCenter()
        wireframe.transform(wf.Wireframe.changeOrigin((x, y, z)))
        wireframe.transform(getattr(wf.Wireframe, ('rotate' + axis + 'Matrix'))(theta))
        wireframe.transform(wf.Wireframe.changeOrigin((-x, -y, -z)))

    def initTexture(wireframe, texturePath):
        wireframe.texture = pygame.image.load(texturePath)
        wireframe.texturePixels = pygame.surfarray.array3d(wireframe.texture)

    def drawTexture(self, wireframe):
        """Rasterize the equirectangular texture onto the visible sphere cells."""
        texture_pixels = wireframe.texturePixels if wireframe.texture is None else pygame.surfarray.array3d(wireframe.texture)
        texture_width, texture_height = wireframe.texture.get_size() if wireframe.texture is not None else wireframe.texture.get_size()
        sectors = 36
        rows = len(wireframe.nodes) // sectors
        cells = []

        for row in range(rows - 1):
            for sector in range(sectors):
                next_sector = (sector + 1) % sectors
                top_left = row * sectors + sector
                top_right = row * sectors + next_sector
                bottom_left = (row + 1) * sectors + sector
                bottom_right = (row + 1) * sectors + next_sector
                indices = (top_left, top_right, bottom_right, bottom_left)
                depth = sum(wireframe.nodes[index][2] for index in indices) / 4
                if depth > 0:
                    cells.append((depth, indices, row, sector))

        # Paint distant cells first so nearer parts of the sphere cover them.
        for _, (top_left, top_right, bottom_right, bottom_left), row, sector in sorted(cells):
            u0 = sector / sectors
            u1 = (sector + 1) / sectors
            v0 = row / (rows - 1)
            v1 = (row + 1) / (rows - 1)
            self._drawTexturedTriangle(
                wireframe, texture_pixels, texture_width, texture_height,
                (top_left, top_right, bottom_right),
                ((u0, v0), (u1, v0), (u1, v1)),
            )
            self._drawTexturedTriangle(
                wireframe, texture_pixels, texture_width, texture_height,
                (top_left, bottom_right, bottom_left),
                ((u0, v0), (u1, v1), (u0, v1)),
            )

    def _drawTexturedTriangle(self, wireframe, texture_pixels, texture_width,
                              texture_height, indices, uvs):
        points = [wireframe.nodes[index] for index in indices]
        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]
        left = max(0, int(min(x_values)))
        right = min(self.width - 1, int(max(x_values)))
        top = max(0, int(min(y_values)))
        bottom = min(self.height - 1, int(max(y_values)))
        if left > right or top > bottom:
            return

        x0, y0 = points[0][:2]
        x1, y1 = points[1][:2]
        x2, y2 = points[2][:2]
        denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denominator) < 1e-6:
            return

        grid_x, grid_y = np.meshgrid(
            np.arange(left, right + 1) + 0.5,
            np.arange(top, bottom + 1) + 0.5,
            indexing="ij",
        )
        weight0 = ((y1 - y2) * (grid_x - x2) + (x2 - x1) * (grid_y - y2)) / denominator
        weight1 = ((y2 - y0) * (grid_x - x2) + (x0 - x2) * (grid_y - y2)) / denominator
        weight2 = 1 - weight0 - weight1
        mask = (weight0 >= 0) & (weight1 >= 0) & (weight2 >= 0)
        if not np.any(mask):
            return

        u = weight0 * uvs[0][0] + weight1 * uvs[1][0] + weight2 * uvs[2][0]
        v = weight0 * uvs[0][1] + weight1 * uvs[1][1] + weight2 * uvs[2][1]
        texture_x = np.clip((u * (texture_width - 1)).astype(int), 0, texture_width - 1)
        texture_y = np.clip((v * (texture_height - 1)).astype(int), 0, texture_height - 1)
        screen_pixels = pygame.surfarray.pixels3d(self.surf)
        screen_pixels[left:right + 1, top:bottom + 1][mask] = texture_pixels[texture_x, texture_y][mask]
        del screen_pixels


    def addWireframe(self, name, wireframe):
        self.wireframes[name] = wireframe
    def draw(self):
        """ Draw the wireframe """
        for wireframe in self.wireframes.values():
            if self.displayTextures:
                self.drawTexture(wireframe)

            if self.displayEdges:
                for n1, n2 in wireframe.edges:
                    if wireframe.nodes[n1][2] > 0 and wireframe.nodes[n2][2] > 0:
                        pygame.draw.line(self.screen, self.edgeColor, wireframe.nodes[n1][:2], wireframe.nodes[n2][:2], 1)
            if self.displayNodes:
                for node in wireframe.nodes:
                    pygame.draw.circle(self.screen, self.nodeColor, (int(node[0]), int(node[1])), self.nodeRadius, 0)

        self.panel.surf.blit(self.surf, (self.x, self.y))

    
