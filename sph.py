"""Spatial hash implementiation.

Use the Hash class.

Python version: 2.
Release: 1.

Licensed under the GNU Lesser General Public License, version 3; if this was
not included, you can find it here:
    https://www.gnu.org/licenses/lgpl-3.0.txt

"""

class Hash:
    """A two-dimensional spatial hash.

Hash(size, box_size, ignore_oob = False)

size: (x, y) tuple, dimensions of the region (world) objects might be in.
box_size: (x, y) tuple, the size of boxes to split the world up into; or an int
          x, representing (x, x).
ignore_oob: whether to ignore attempted additions of objects outside the given
            world size (else just put them in edge boxes).

If ignore_oob is False and a lot of objects are ending up out-of-bounds, you
should increase the world size.

"""

    def __init__ (self, size, box_size, ignore_oob = False):
        self.x, self.y = size
        try:
            self.bx, self.by = box_size
        except TypeError:
            self.bx = self.by = box_size
        self.ignore_oob = ignore_oob
        self.w = self.x / self.bx
        self.h = self.y / self.by
        # create grid
        self.grid = []
        for y in xrange(self.h):
            self.grid.append([])
            for x in xrange(self.w):
                self.grid[y].append(set())
            self.grid[y] = tuple(self.grid[y])
        self.grid = tuple(self.grid)
        self.objs = {}
        if not self.ignore_oob:
            self.oob = set()
            self.objs_oob = {}

    def __str__ (self):
        n = len(self.objs.keys())
        return '<Hash: {0}*{1}, {2} object{3}>'.format(self.w, self.h, n, '' if n == 1 else 's')

    def __repr__ (self):
        return '\n'.join('|'.join(', '.join(str(id(obj)) for obj in x) for x in y) for y in self.grid)

    def __contains__ (self, obj):
        return obj in self.objs

    def get_rect (self, box = None):
        """Get the rectangle the given box covers."""
        if box is None:
            return 0, 0, self.x, self.y
        try:
            x, y = box
            x, y = int(x), int(y)
        except TypeError:
            raise TypeError('argument must be an (x, y) tuple')
        if x >= self.w or y >= self.h or x < 0 or y < 0:
            raise ValueError('{0} out of bounds'.format((x, y)))
        x0, y0 = x * self.bx, y * self.by
        x1 = self.x if x + 1 >= self.w else x0 + self.bx
        y1 = self.y if y + 1 >= self.h else y0 + self.by
        w, h = x1 - x0, y1 - y0
        return x0, y0, w, h

    def boxes_in_rect (self, rect):
        """Return a list of boxes partially contained by the given rect."""
        x0, y0, w, h = rect
        x1, y1 = x0 + w, y0 + h
        # calculate box range
        x, y = x0 / self.bx, y0 / self.by
        xmax = x1 / self.bx - (x1 % self.bx == 0)
        ymax = y1 / self.by - (y1 % self.by == 0)
        # compile result
        boxes = []
        if not (x > self.w or y > self.h or xmax < 0 or ymax < 0):
            for j in xrange(min(max(y, 0), self.h - 1), max(min(ymax + 1, self.h), 1)):
                for i in xrange(min(max(x, 0), self.w - 1), max(min(xmax + 1, self.w), 1)):
                    boxes.append((i, j))
        if self.ignore_oob:
            return boxes
        else:
            oob = x < 0 or xmax > self.w or y < 0 or ymax > self.h
            return boxes, oob

    def add (self, obj, *rects):
        """Add an object to the hash.

add(obj, *rects)

obj: the object.
*rects: the rectangle(s) describing the object's position; (x, y, w, h), where
    x: x co-ordinate of the edge with the smallest x co-ordinate
    y: y co-ordinate of the edge with the smallest y co-ordinate
    w: width
    h: height

"""
        if obj in self.objs:
            self.rm(obj)
        self.objs[obj] = set()
        oob = False
        for rect in rects:
            boxes = self.boxes_in_rect(rect)
            if not self.ignore_oob:
                boxes, temp = boxes
                oob |= temp
            for i, j in boxes:
                self.grid[j][i].add(obj)
                self.objs[obj].add((i, j))
        if oob:
            self.oob.add(obj)
        self.objs_oob[obj] = oob

    def rm (self, obj):
        """Remove the given object from the boxes it has been placed in."""
        try:
            boxes = self.objs.pop(obj)
        except KeyError:
            return
        for x, y in boxes:
            self.grid[y][x].remove(obj)
        if not self.ignore_oob:
            if self.objs_oob.pop(obj):
                self.oob.remove(obj)

    def homes (self, *objs):
        """Return a set of the boxes the given objects are in."""
        boxes = set()
        oob = False
        for obj in set(objs):
            try:
                boxes = boxes | self.objs[obj]
                if not self.ignore_oob:
                    oob |= self.objs_oob[obj]
            except KeyError:
                pass
        if self.ignore_oob:
            return boxes
        else:
            return boxes, oob

    def tenants (self, *boxes):
        """Return a set of objects in the given boxes.

The arguments should be (x, y) tuples (as returned by all methods that purport
to return boxes).

"""
        objs = set()
        for x, y in set(boxes):
            try:
                if x < 0 or y < 0:
                    raise IndexError
                for obj in self.grid[y][x]:
                    objs.add(obj)
            except IndexError:
                pass
        return objs

    def objs_in_rect (self, rect):
        """Return a set of objects that share a box with the given rect."""
        boxes = self.boxes_in_rect(rect)
        if not self.ignore_oob:
            boxes, oob = boxes
        objs = self.tenants(*boxes)
        if not self.ignore_oob and oob:
            objs |= self.oob
        return objs

    def neighbours (self, *objs):
        """Return a set of objects that share a box with any of the given objects.

None of the given objects are in the return list.

"""
        given = set(objs)
        boxes = self.homes(*given)
        if not self.ignore_oob:
            boxes, oob = boxes
        objs = self.tenants(*boxes)
        if not self.ignore_oob and oob:
            objs |= self.oob
        return objs - given

    def community (self, *objs):
        """Return the stuff you probably need to pay attention to.

Takes a list of objects and compiles a list of their boxes.  Then, we
recursively look through the objects in those boxes and add any boxes they're
in that aren't in our list yet, until we have every box connected to the given
objects.

The return value is a (boxes, objs) tuple, which are sets of all found boxes
and all found objects respectively.

"""
        objs = set(objs)
        new_objs = set(objs)
        boxes = set()
        oob = False
        while 1:
            if not new_objs:
                break
            # get new
            new_boxes = self.homes(*new_objs)
            if not self.ignore_oob:
                new_boxes, new_oob = new_boxes
            new_boxes -= boxes
            new_objs = self.tenants(*new_boxes)
            if not self.ignore_oob and new_oob and not oob:
                new_objs |= self.oob
            new_objs -= objs
            # add to master sets
            boxes |= new_boxes
            objs |= new_objs
            oob |= new_oob
        if self.ignore_oob:
            return boxes, objs
        else:
            return boxes, objs, oob
