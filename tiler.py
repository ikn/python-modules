"""Pygame tiler.

This module primarily consists of a Tiler class to draw and manage a tiled grid
using Pygame.

Python version: 2.
Release: 10.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

"""

from pygame.display import get_surface
from pygame.draw import line as draw_line
from pygame import Rect

def draw_rect (surface, colour, rect, width = 1):
    """Draw a rect border to a surface.

draw_rect(surface, colour, rect, width = 1)

surface: the surface to draw to.
colour: a standard (r, g, b) tuple.
rect: rect to draw; anything like (left, top, width, height).
width: (vertical, horizontal) rect border widths, or one int for
       vertical = horizontal, in pixels.

The border is drawn inside the given rect, unlike pygame.draw.rect, which draws
the lines with their centres on the rect's borders.

"""
    try:
        width[0]
    except TypeError:
        width = (width, width)
    l, t, w, h = rect
    x0 = l + width[0] / 2 + width[0] % 2 - 1
    x1 = l + w - width[0] / 2 - 1
    y0 = t + width[1] / 2 + width[1] % 2 - 1
    y1 = t + h - width[1] / 2 - 1
    points = (
        ((l, y0), (l + w - 1, y0)),
        ((x1, t), (x1, t + h - 1)),
        ((l + w - 1, y1), (l, y1)),
        ((x0, t + h - 1), (x0, t))
    )
    for i in xrange(len(points)):
        p, q = points[i]
        draw_line(surface, colour, p, q, width[not i % 2])

def fill (surface, rect, colour):
    """Fill a single colour.

Takes a standard (r, g, b) tuple.

"""
    surface.fill(colour, rect)

def border (surface, rect, data):
    """Fill with a border.

Takes (border_width, border_colour, inner_colour).  If inner_colour is omitted
or width is 0, border colour is used for the whole tile.

"""
    if len(data) == 2:
        border = data[1]
        width = 0
    else:
        width, border, inner = data
    surface.fill(border, rect)
    if width != 0:
        width *= 2
        surface.fill(inner, Rect(rect).inflate(-width, -width))

DRAW_FUNCTIONS = {'fill': fill, 'border': border}

class Tiler:
    def __init__ (self, w, h, draw_tile = 'fill', tile_data = (255, 255, 255),
        gap = 1, border = 0, line = (200, 200, 200), mode = 'fit', align = 0,
        offset = (0, 0), homogeneous = True, overflow = 'shrink',
        track_tiles = True):
        """Draw a grid of tiles.

Tiler(w, h, draw_tile = 'fill', tile_data = (255, 255, 255), gap = 1,
    line = (200, 200, 200), mode = 'fit', align = 0, offset = (0, 0),
    homogeneous = True, overflow = 'shrink', track_tiles = True)

w: number of columns of tiles.
h: number of rows of tiles.
draw_tile: a function that takes (surface, rect, data) arguments if track_tiles
           is True, else (surface, rect, column, row); it should draw a tile in
           the rect on the surface using the data or tile row and column.
           This can also be string representing a preset function, one of those
           in tiler.DRAW_FUNCTIONS.
tile_data: default data to store for tiles, used in calling draw_tile.
gap: (vertical, horizontal) width of gap between tiles, or one int for
     vertical = horizontal, in pixels.
border: (vertical, horizontal) outer border width, or one int for
        vertical = horizontal, in pixels.
line: RGB colour tuple for grid lines including border, or None (leave gaps but
      draw nothing).
mode: one of:
    'stretch': fill surface in both dimensions.
    'fit': square tiles, fill surface in larger dimension (show all tiles).
    'zoom': square tiles, fill surface in smaller dimension (don't show all
            tiles).
    ('tile', width[, height]): give tiles these dimensions; if not given,
                               height = width.
    ('grid', width[, height]): give entire grid these dimensions; if not given,
                               height = width.
align: (x, y) grid alignment or one int for x = y, where for each:
    < 0: left/top;
    0: centre;
    > 0: right/bottom.
offset: (x, y) pixel offest for grid.
homogeneous: when drawing, give all tiles the same width/height, potentially
             leaving gaps outside the grid or going outside the given boundary.
overflow: used when homogeneous = True; one of 'shrink' (stay inside the given
          boundary and leave gaps), 'grow' (draw outside the given boundary) or
          'crop' (stay inside the given boundary without leaving gaps by not
          drawing parts of edge tiles (right and bottom)).
track_tiles: whether to keep an internal dataset for the tiles pertaining to
             their appearance.  If False, any such data needs to be kept track
             of manually, and the tile_data argument is ignored.  This setting
             affects the arguments given to draw_tile and the arguments
             accepted by Tiler.change.

Typical use just means calling Tiler.change as necessary and Tiler.draw_changed
to update the display.  Tiler.draw_changed will draw the whole grid on the
first call; to do this again, call Tiler.reset, or call Tiler.draw directly
instead of going through Tiler.draw_changed.  Tiler.reset should also be called
if you pass different surface and size arguments to Tiler.draw_changed.

    METHODS

draw
change
draw_changed
reset

    ATTRIBUTES

All of the following attributes are as passed to the constructor (not always
exactly, but representing the same information - given border = 1, for example,
the border attribute will be (1, 1)).

track_tiles:
    do not change.
w/h:
    do not change if track_tiles is True; otherwise, the grid rect may change,
    so you might need to draw over the rect last returned from Tiler.draw, and
    you will need to call Tiler.reset.
gap/border/line:
    call Tiler.reset after changing.
mode/align/offset/homogeneous/overflow:
    after changing, the grid rect may change, so you might need to draw over
    the rect last returned from Tiler.draw, and you will need to call
    Tiler.reset.
draw_tile:
    if you want the new draw method to affect all tiles immediately rather than
    just as they are changed, call Tiler.reset.

"""
        self.w = w
        self.h = h
        if not hasattr(draw_tile, '__call__'):
            try:
                self.draw_tile = DRAW_FUNCTIONS[draw_tile]
            except KeyError:
                raise ValueError('draw_tile must be a function or element of'
                                 'DRAW_FUNCTIONS')
        else:
            self.draw_tile = draw_tile
        self.track_tiles = track_tiles
        if self.track_tiles:
            self._tiles = [[tile_data] * h for x in xrange(w)]
        try:
            gap[0]
        except TypeError:
            self.gap = (gap, gap)
        else:
            self.gap = gap
        try:
            border[0]
        except TypeError:
            self.border = (border, border)
        else:
            self.border = border
        self.line = line
        if mode[0] in ('tile', 'grid') and len(mode) == 2:
            mode = tuple(mode) + (mode[1],)
        self.mode = mode
        try:
            align[0]
        except TypeError:
            self.align = (align, align)
        else:
            self.align = align
        self.offset = offset
        self.homogeneous = homogeneous
        self.overflow = overflow
        self.reset()
        self._tile_rects = None
        self._cache = {}
        self._cache_dim = None

    def _align (self, target, grid):
        # use align and offset to calculate grid top-left corner position
        tl = []
        for i in (0, 1):
            align = self.align[i]
            if align < 0:
                tl.append(0)
            elif align == 0:
                tl.append(int(round((target[i] - grid[i]) / 2)))
            else:
                tl.append(int(round(target[i] - grid[i])))
            tl[i] += self.offset[i]
        return tl

    def _grid_size (self, ws, hs):
        # return grid rect on surface
        # calculate dimensions
        m = self.mode
        if m == 'stretch':
            w = ws
            h = hs
        elif m in ('fit', 'zoom'):
            # calculate tile dimensions that fit
            choose_big = m == 'zoom'
            x = (ws - self._lines[0]) / float(self.w)
            y = (hs - self._lines[1]) / float(self.h)
            # then choose the right one
            size = (x, y)[choose_big ^ (x > y)]
            w = int(round(size * self.w + self._lines[0]))
            h = int(round(size * self.h + self._lines[1]))
        elif m[0] == 'tile':
            w = int(m[1]) * self.w + self._lines[0]
            h = int(m[2]) * self.h + self._lines[1]
        elif m[0] == 'grid':
            w = int(m[1])
            h = int(m[2])
        return self._align((ws, hs), (w, h)) + [w, h]

    def _tile_sizes (self, surface_size, grid_rect):
        # calculate tile sizes for a given grid rect
        ws, hs = surface_size
        l, t, w, h = grid_rect
        calc = True
        if self.homogeneous:
            # reduce to tile area
            w -= self._lines[0]
            h -= self._lines[1]
            calc = False
            # integer division
            tile_sizes = [w / self.w, h / self.h]
            w_prev = w
            h_prev = h
            if self.overflow in ('grow', 'crop'):
                tile_sizes[0] += 1
                tile_sizes[1] += 1
            if self.overflow == 'crop':
                hg_tile_sizes = tile_sizes
                w += self._lines[0]
                h += self._lines[1]
                calc = True
            else:
                # get new grid position if necessary
                w = self.w * tile_sizes[0]
                h = self.h * tile_sizes[1]
                if w != w_prev or h != h_prev:
                    w += self._lines[0]
                    h += self._lines[1]
                    l, t = self._align((ws, hs), (w, h))
                else:
                    w += self._lines[0]
                    h += self._lines[1]
        if calc:
            # calculate individual row and col sizes
            tiles_size = (w - self._lines[0], h - self._lines[1])
            x = tiles_size[0] / float(self.w)
            y = tiles_size[1] / float(self.h)
            tile_sizes = []
            for i in (0, 1):
                avg = (x, y)[i]
                base = int(avg)
                diff = avg - base
                sizes = []
                total_diff = 0
                for j in xrange((self.w, self.h)[i]):
                    total_diff += diff
                    if total_diff >= 1:
                        sizes.append(base + 1)
                        total_diff -= 1
                    else:
                        sizes.append(base)
                # adjust first tile (probably only by 1px, if any)
                sizes[0] += tiles_size[i] - sum(sizes)
                tile_sizes.append(sizes)
            if self.homogeneous and self.overflow == 'crop':
                tile_sizes[0] = [hg_tile_sizes[0]] * self.w
                tile_sizes[1] = [hg_tile_sizes[1]] * self.h
                for i in (0, 1):
                    n = 0
                    tile_size = hg_tile_sizes[i]
                    # when we remove a tile entirely, add up the gap not needed
                    gaps_excess = 0
                    while 1:
                        # remove / reduce size of end tiles
                        # until we're within the allotted size
                        excess = sum(tile_sizes[i]) - tiles_size[i]
                        if excess > 0:
                            n -= 1
                            new_size = tile_size - excess
                            if new_size <= 0:
                                new_size = 0
                                gaps_excess += self.gap[i]
                            tile_sizes[i][n] = new_size
                        else:
                            break
                    # give space from unused gaps to visible tiles
                    while gaps_excess > 0:
                        diff = hg_tile_sizes[i] - tile_sizes[i][n]
                        diff = min(gaps_excess, diff)
                        tile_sizes[i][n] += diff
                        gaps_excess -= diff + self.gap[i]
                        n += 1
        return tile_sizes, (l, t, w, h)

    def _call_cacheable (self, method, *args, **kw):
        try:
            return self._cache[method]
        except KeyError:
            result = getattr(self, method)(*args, **kw)
            self._cache[method] = result
            return result

    def _draw_tiles (self, surface, tile_sizes, t = 0, l = 0, *tiles):
        hg = type(tile_sizes[0]) is int
        b = self.border
        g = self.gap
        x = l + b[0]
        if tiles:
            # draw some tiles
            y = t + b[1]
            last_i = last_j = 0
            for i, j in sorted(tiles):
                w, h = tile_sizes
                if j < last_j:
                    last_j = 0
                    y = t + b[1]
                if hg:
                    x += (tile_sizes[0] + g[0]) * (i - last_i)
                    y += (tile_sizes[1] + g[1]) * (j - last_j)
                else:
                    x += sum(tile_sizes[0][last_i:i]) + g[0] * (i - last_i)
                    y += sum(tile_sizes[1][last_j:j]) + g[1] * (j - last_j)
                    w = w[i]
                    h = h[j]
                self._draw_tile_wrapper(surface, (x, y, w, h), i, j)
                last_i = i
                last_j = j
        else:
            # draw all tiles
            for i in xrange(self.w):
                y = t + b[1]
                for j in xrange(self.h):
                    w, h = tile_sizes
                    if not hg:
                        w = w[i]
                        h = h[j]
                    self._draw_tile_wrapper(surface, (x, y, w, h), i, j)
                    y += h + g[1]
                x += w + g[0]

    def _draw_lines (self, surface, grid_rect, tile_sizes):
        # draw border and grid lines
        c = self.line
        if c is None:
            # don't draw lines
            return
        l, t, w, h = grid_rect
        hg = type(tile_sizes[0]) is int
        b = self.border
        g = self.gap
        tl = (t, l)
        crop = self.homogeneous and self.overflow == 'crop'
        # draw border
        draw_rect(surface, c, (l, t, w, h), b)
        for i in (0, 1):
            if g[i]:
                # draw grid lines on one axis
                pos = tl[not i] + b[i] + g[i] / 2 + g[i] % 2 - 1
                start = tl[i] + b[not i]
                end = tl[i] + (h, w)[i] - b[not i] - 1
                if not hg:
                    max_size = tile_sizes[i][0]
                for j in xrange((self.w, self.h)[i] - 1):
                    tile_size = tile_sizes[i]
                    if not hg:
                        if crop and tile_sizes[i][j] < max_size:
                            break
                        tile_size = tile_size[j]
                    pos += tile_size
                    if i:
                        draw_line(surface, c, (start, pos), (end, pos), g[i])
                    else:
                        draw_line(surface, c, (pos, start), (pos, end), g[i])
                    pos += g[i]

    def draw (self, surface = None, *tiles, **kw):
        """Draw grid to a surface.

Tiler.draw([surface][, *tiles][, size]) -> rect

surface: surface to draw to; defaults to the current display.
tiles: tiles to draw; (column, row) tuples; if none are given, everything is
       drawn.
size (keyword-only): work out the grid size using this (width, height) target
                     area, instead of the surface size.

rect: (left, top, width, height) rectangle representing the grid.

"""
        if surface is None:
            surface = get_surface()
        if 'size' in kw and kw['size'] is not None:
            ws, hs = kw['size'][:2]
        else:
            ws, hs = surface.get_size()
        # purge cache if surface size has changed
        if (ws, hs) != self._cache_dim:
            self._cache = {}
            self._cache_dim = (ws, hs)
        # compute
        l, t, w, h = self._call_cacheable('_grid_size', ws, hs)
        tile_sizes, (l, t, w, h) = self._call_cacheable('_tile_sizes',
                                                        (ws, hs), (l, t, w, h))
        # draw
        self._draw_tiles(surface, tile_sizes, t, l, *tiles)
        if tiles:
            if self._changed is None:
                self._changed = set()
            else:
                # remove drawn tiles from changed list
                self._changed -= set(tiles)
        else:
            self._draw_lines(surface, (l, t, w, h), tile_sizes)
            self._changed = set()
        # return rect grid is in
        return (l, t, w, h)

    def _draw_tile_wrapper (self, surface, rect, i, j):
        # used to store drawn tile rects for draw_changed to return
        if self._tile_rects is not None:
            self._tile_rects.append(rect)
        if self.track_tiles:
            self.draw_tile(surface, rect, self._tiles[i][j])
        else:
            self.draw_tile(surface, rect, i, j)

    def change (self, *args):
        """Change a tile's draw data.

Takes any number of positional arguments, where each represents a tile to
change.  Each is a (column, row[, data]) tuple, where data is only needed if
track_tiles is True.

Alternatively, if only one tile needs to be changed, the arguments can be
(column, row[, data]) for that tile.

"""
        if len(args) == 0:
            return
        if isinstance(args[0], int):
            # one tile
            args = (args,)
        for data in args:
            i = int(data[0])
            j = int(data[1])
            if self.track_tiles:
                self._tiles[i][j] = data[2]
            if self._changed is not None:
                self._changed.add((i, j))

    def draw_changed (self, surface = None, size = None):
        """Draw all tiles changed (through Tiler.change) since last drawn.

draw_changed([surface][, size])

surface: surface to draw to; defaults to the current display.
size: work out the grid size using this (width, height) target area, instead of
      the surface size.

If the whole grid was redrawn, the grid rect is returned.  If no tiles were
drawn, None is returned.  If some tiles were drawn, a list of rects is
returned, with the first the grid rect and all subsequent ones the redrawn
tiles.

"""
        if self._changed is None:
            return self.draw(surface, size = size)
        elif self._changed:
            self._tile_rects = []
            rect = self.draw(surface, *self._changed, size = size)
            temp = self._tile_rects
            self._tile_rects = None
            return [rect] + temp

    def reset (self):
        """Reset some stuff."""
        # calculate total non-tile area on grid in each dimension
        size = (self.w, self.h)
        self._lines = [self.gap[i] * (size[i] - 1) + 2 * self.border[i]
                       for i in (0, 1)]
        # tell draw_changed to draw everything
        self._changed = None
        # purge cached results
        self._cache = {}