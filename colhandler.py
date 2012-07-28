"""A simple, exact, 2D collision handler.

'Simple' means objects are rigid and consist of axis-aligned lines, which means
no rotation or deformation.

'Exact' means collisions are not estimated, but computed exactly, which means
bullets don't go through walls, and jumping characters land on the ground
instead of hovering just above it.

Note on directions: where taken as an argument or used in a data structure, a
direction is an integer from 0 to 3, which correspond to left to bottom,
clockwise.

Python version: 2.
Release: 1-dev.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    CLASSES

Shape
BaseLine
Line
HalfLine
Rect
StaticObject
Object
CollisionHandler

"""

# TODO:
# - moving diagonally into a corner goes through it
# - handle inf/nan (from math import isinf, isnan)
# - really long loops with e < 1 when a moving object is squashed between two others
# - spatial hash


class Shape (object):
    """Base class for shapes used in the collision handler.

    CONSTRUCTOR

Shape(*lines)

lines: one or more axis-aligned solid lines, in the form
       (direction, perp, para0, para1), where:
    direction: the solid side of the line (side against which collisions can
               occur).
    perp: the position of the line on the axis perpendicular to it.
    para0, para1: the positions of the end-points of the line on the axis
                  parallel to it.

    ATTRIBUTES

obj: the object that uses this shape, or None.
lines: contains lists of lines, one per direction, in the same form as given
       without the direction element.  Don't alter this directly.  It is
       guaranteed that para0 <= para1.

It is guaranteed that any reference to a line will always be the current
reference to that line.

"""

    def __init__ (self, *lines):
        self.obj = None
        self.lines = ls = ([], [], [], [])
        for i, pr, pl0, pl1 in lines:
            if pl0 > pl1:
                pl0, pl1 = pl1, pl0
            ls[i].append([pr, pl0, pl1])

    def __getattr__ (self, attr):
        msg = '\'{0}\' object has no attribute \'{1}\''
        raise AttributeError(msg.format(self.__class__.__name__, attr))

    # here I use _ to mean private to the module, not to the class
    def _move (self, v):
        """Move the object by the given (x, y) velocity."""
        for i, ls in enumerate(self.lines):
            v_pr = v[i % 2]
            v_pl = v[(i + 1) % 2]
            for l in ls:
                l[0] += v_pr
                l[1] += v_pl
                l[2] += v_pl


class BaseLine (Shape):
    """Base class for axis-aligned lines (Shape subclass).

Takes the same arguments as Shape.

    METHODS

get_ends

    ATTRIBUTES

axis: the axis (0 or 1) parallel to the line.
a: the (x, y) co-ordinate of the end of the line with the smallest x and y.
b: the (x, y) co-ordinate of the end of the line with the greatest x and y.
line: (perp, para0, para1) for this line (see HalfLine); this is actually a
      reference to the line stored in the lines attribute.
length: the length of the line.
rect: treat this as a rect and get (left, top, right, bottom).

"""

    def __init__ (self, *lines):
        Shape.__init__(self, *lines)
        self.axis = (lines[0][0] + 1) % 2

    def __getattr__ (self, attr):
        if isinstance(self, HalfLine):
            i = self.dirn
        else:
            i = not self.axis
        pr, pl0, pl1 = self.lines[i][0]
        if attr == 'length':
            return pl1 - pl0
        elif attr == 'line':
            return self.lines[i][0]
        elif self.axis == 0:
            if attr == 'a':
                return (pl0, pr)
            elif attr == 'b':
                return (pl1, pr)
            elif attr == 'rect':
                return (pl0, pr, pl1, pr)
        else:
            if attr == 'a':
                return (pr, pl0)
            elif attr == 'b':
                return (pr, pl1)
            elif attr == 'rect':
                return (pr, pl0, pr, pl1)
        return getattr(Shape, attr)


class Line (BaseLine):
    """Axis-aligned line with two solid sides (BaseLine subclass).

    CONSTRUCTOR

Line(x, y)

x: x co-ordinate for a line parallel to the y-axis, or (x0, x1) for a line
   parallel to the x-axis.
y: y co-ordinate for a line parallel to the x-axis, or (y0, y1) for a line
   parallel to the y-axis.

"""

    def __init__ (self, x, y):
        try:
            pl0, pl1 = x
        except TypeError:
            pl0, pl1 = y
            pr = x
            i = 0
        else:
            pr = y
            i = 1
        BaseLine.__init__(self, (i, pr, pl0, pl1), (i + 2, pr, pl0, pl1))

    def __str__ (self):
        pr, pl0, pl1 = self.lines[not self.axis][0]
        if self.axis == 0:
            l = ((pl0, pl1), pr)
        else:
            l = (pr, (pl0, pl1))
        return 'Line{0}'.format(l)

    __repr__ = __str__


class HalfLine (BaseLine):
    """Axis-aligned line with one solid side (BaseLine subclass).

    CONSTRUCTOR

HalfLine(dirn, perp, para0, para1)

dirn, perp, para0, para1: as taken by Shape for a line.

    ATTRIBUTES

dirn: as given.

"""

    def __init__ (self, dirn, perp, para0, para1):
        BaseLine.__init__(self, (dirn, perp, para0, para1))
        self.dirn = dirn

    def __str__ (self):
        pr, pl0, pl1 = self.lines[self.dirn][0]
        return 'HalfLine{0}'.format((self.dirn, pr, pl0, pl1))

    __repr__ = __str__


class Rect (Shape):
    """Axis-aligned solid rectangle (Shape subclass).

    CONSTRUCTOR

Rect(x0, y0, x1, y1)

x0, y0: co-ordinates of the corner with the smallest x and y.
x1, y1: co-ordinates of the corner with the greatest x and y.

    ATTRIBUTES

top_left, top_right, bottom_right, bottom_left: the (x, y) co-ordinates of
    corners of the rect; left and top have the smallest x and y respectively.
left, top, right, bottom: the positions of sides of the rect on the axis
                          perpendicular to them.
centre: the (x, y) co-ordinates of the centre of the rect.
width, height: the rect's width and height.
size: (width, height).
area: the rect's area.
rect: (left, top, right, bottom).
pgrect: (left, top, width, height).

"""

    _side_names = {'left': 0, 'top': 1, 'right': 2, 'bottom': 3}

    def __init__ (self, x0, y0, x1, y1):
        Shape.__init__(self, (0, x0, y0, y1), (1, y0, x0, x1), (2, x1, y0, y1),
                       (3, y1, x0, x1))

    def __str__ (self):
        return 'Rect{0}'.format(self.rect)

    __repr__ = __str__

    def __getattr__ (self, attr):
        sides = [lines[0][0] for lines in self.lines]
        if attr in ('top_left', 'top_right', 'bottom_right', 'bottom_left'):
            y, x = attr.split('_')
            return (sides[self._side_names[x]], sides[self._side_names[y]])
        elif attr in ('left', 'top', 'right', 'bottom'):
            return sides[self._side_names[attr]]
        elif attr == 'centre':
            left, top, right, bottom = sides
            return (left + float(right - left) / 2,
                    top + float(bottom - top) / 2)
        elif attr == 'width':
            return sides[2] - sides[0]
        elif attr == 'height':
            return sides[3] - sides[1]
        elif attr == 'size':
            return (sides[2] - sides[0], sides[3] - sides[1])
        elif attr == 'area':
            return (sides[2] - sides[0]) * (sides[3] - sides[1])
        elif attr == 'rect':
            return tuple(sides)
        elif attr == 'pgrect':
            ir = lambda x: int(round(x))
            left, top = sides[0], sides[1]
            return (left, top, sides[2] - left, sides[3] - top)
        return getattr(Shape, attr)


class StaticObject (object):
    """An object that can collide but cannot move.

    CONSTRUCTOR

StaticObject(shape, elast = 0, frict = 0, group = 1)

shape: a Shape (subclass) instance.
elast: the elasticity of collisions with this object.  When a collision occurs,
       the product of the elasticities of the colliding objects is the ratio of
       the speed in the collision direction retained afterwards.  The value
       should be between 0 (no bounce) and 1 (no speed loss).  Values > 1
       (speed increase) are supported, but can easily lead to very large
       speeds, so watch out for position and velocity values of inf or nan.
frict: the friction of collisions with this object.  The product of frictions
       of the colliding objects gives the maximum reduction in speed difference
       perpendicular to the collision direction.  Should be 0 (no effect) or
       above.
layer: the object's collision layer(s).  This is an integer; objects o1 and o2
       will only collide if o1.layer & o2.layer is not 0.  This means that an
       object with a layer of 0 will collide with nothing, and an object with
       a layer of -1 will collide with anything else.

    ATTRIBUTES

shape: as given; if you change this, call the CollisionHandler's reinit method
       before the next update.
elast, frict, layer: as given; change directly as necessary.

"""

    def __init__ (self, shape, elast = 0, frict = 0, layer = 1):
        shape.obj = self
        self.shape = shape
        self.elast = elast
        self.frict = frict
        self.layer = layer

    def __str__ (self):
        return 'StaticObject{0}'.format((self.shape, self.elast))

    __repr__ = __str__


class Object (StaticObject):
    """An object that can collide and move (StaticObject subclass).

    CONSTRUCTOR

Object(mass, shape, vel = [0, 0], ...)

mass: the object's mass; used in determining the outcome of collisions.  This
      is a positive non-zero number, or None for infinite mass, which denotes a
      static object.
vel: the object's (x, y) velocity.
...: further arguments taken by StaticObject.

    ATTRIBUTES

mass, vel: as given; change these directly as necessary.

"""

    def __init__ (self, mass, shape, vel = [0, 0], *args, **kw):
        self.mass = mass
        self.vel = vel
        StaticObject.__init__(self, shape, *args, **kw)

    def __str__ (self):
        return 'Object{0}'.format((self.mass, self.shape, self.elast))

    __repr__ = __str__

    def __setattr__ (self, attr, val):
        if attr == 'vel':
            val = list(val)
        StaticObject.__setattr__(self, attr, val)


class CollisionHandler (object):
    """Handle collisions for Object and StaticObject instances.

Don't alter the properties of objects during callbacks.

    CONSTRUCTOR

CollisionHandler(objs, before_cb = None, after_cb, touching_cb = None, err = 0)

objs: list of (Static)Object instances for this CollisionHandler to handle.
before_cb: a function to call when two objects collide, before the collision
           has been processed.  Arguments given are
           (o1, o2, dirn, i1, i2, data), where:
    o1, o2: the colliding objects.
    dirn: the direction of the line on o1 that collides (that of o2 is the
          opposite).
    i1, i2: the respective indices of the colliding line in each object's shape
            - that is, the line for o1 is o1.shape.lines[i][i1], and similar
            for o2.
    data: a two-element list, [elast, frict], where these are the combined
          elasticity and friction that will be used for the collision.  You can
          modify the elements of this list to change the values that will be
          used.
           The callback can return True to skip handling this collision (the
           objects will pass through each other).
after_cb: a function to call when two objects collide, after the collision has
          been processed.  Arguments given are (o1, o2, dirn, i1, i2, impulse),
          where most are as for before_cb, and impulse is the magnitude of the
          impulse (change in momentum) generated by the collision (taking the
          effect of friction into account).
touching_cb: a function to call whenever two objects are touching after all
             collisions have been handled.  This may be called in the same
             call to update as col_cb for the same objects, if they are still
             touching, but may not if they move apart before the end of the
             update.  Arguments are (o1, o2, dirn, i1, i2) as passed to col_cb.
err: the maximum distance objects can be from each other and still be
     considered to be touching.  This only matters if their combined elasticity
     is non-zero (otherwise, it is easy to be at 0 distance).  Regardless of
     this value, objects only start touching if they collide at some point.

    METHODS

reinit
update

    ATTRIBUTES

objs: as given; if you change this, call the reinit method before the next
      update.
before_cb, after_cb, touching_cb, err: as given; change as necessary.

"""

    def __init__ (self, objs, before_cb = None, after_cb = None,
                  touching_cb = None, err = 0):
        self.objs = objs
        self.before_cb = before_cb
        self.after_cb = after_cb
        self.touching_cb = touching_cb
        self.err = err
        self.reinit()

    def _cache_shapes (self):
        """Store shapes and their lines from all objects."""
        # lines are same format as shape lines, but (line, obj, line_id)
        # instead of line in moving_lines, and (is_static, line, obj, line_id)
        # in lines
        self._moving_shapes = moving_shapes = []
        self._static_shapes = static_shapes = []
        self._moving_lines = moving_lines = ([], [], [], [])
        self._lines = lines = ([], [], [], [])
        for o in self.objs:
            s = o.shape
            if isinstance(o, Object):
                moving_shapes.append(s)
                for i, ls in enumerate(s.lines):
                    for l_i, l in enumerate(ls):
                        moving_lines[i].append((l, o, l_i))
                        lines[i].append((False, l, o, l_i))
            else:
                static_shapes.append(s)
                for i, ls in enumerate(s.lines):
                    for l_i, l in enumerate(ls):
                        lines[i].append((True, l, o, l_i))

    def _fix_colliding (self, rtn_success = True):
        """Ensure objects aren't overlapping (see reinit)."""
        moving_shapes = self._moving_shapes
        shapes = moving_shapes + self._static_shapes
        resolved = dict((s, []) for s in moving_shapes)
        success = None
        while True:
            # get all overlapping objects
            overlaps = []
            checked = set()
            for s1 in moving_shapes:
                checked.add(s1)
                for s2 in shapes:
                    # don't check the same collision twice
                    if s2 in checked:
                        continue
                    # don't check previously resolved collisions either
                    if not rtn_success and s2 in resolved[s1]:
                        continue
                    # treat lines as rects
                    l1, t1, r1, b1 = s1.rect
                    l2, t2, r2, b2 = s2.rect
                    # check we have to move to resolve this
                    ds = (r2 - l1, b2 - t1, r1 - l2, b1 - t2)
                    d = min(ds)
                    if d > 0:
                        # overlap: add all movement possibilities
                        for i, d in enumerate(ds):
                            v = [0, 0]
                            v[i % 2] = (1 if i < 2 else -1) * d
                            overlaps.append((d, v, s1, s2, i % 2))
            if not overlaps:
                # done
                success = True
                break
            # get the shortest movement we haven't done yet (count as the same
            # if both shapes and the axis of movement are the same)
            overlaps.sort()
            if overlaps:
                while True:
                    if not overlaps:
                        # still have overlapping, but have previously resolved all
                        # remaining collisions, so we've failed
                        success = False
                        break
                    v, s1, s2, axis = overlaps.pop(0)[1:]
                    if (s2, axis) not in resolved[s1]:
                        break
                    elif (s1, axis) not in resolved[s2]:
                        s1, s2 = s2, s1
                        v[axis] *= -1
                        break
            if success is False:
                break
            s1._move(v)
            resolved[s1].append((s2, axis))
        return success

    def _update_contact (self):
        """Determine which surfaces are in contact."""
        # touching is an {(i, o1, i1, o2, i2): (l1, l2)} dict
        self._touching = touching = {}
        lines = self._lines
        err = self.err
        checked = set()
        for i, moving_ls in enumerate(self._moving_lines):
            axis = i % 2 # axis in which the collision occurs
            j = (i + 2) % 4
            ls = lines[j]
            for l1, o1, i1 in moving_ls:
                checked.add((i, o1, i1))
                l1pr, l1pl0, l1pl1 = l1
                for static, l2, o2, i2 in ls:
                    # don't check the same collision twice
                    if (j, o2, i2) in checked:
                        continue
                    # don't check an object against itself
                    if o2 is o1:
                        continue
                    # if touching,
                    l2pr, l2pl0, l2pl1 = l2
                    if l1pr == l2pr and l1pl0 < l2pl1 and \
                       l2pl1 > l1pl0:
                        # add to dict
                        touching[(i, o1, i1, o2, i2)] = (l1, l2)

    def reinit (self, rtn_success = True):
        """Update some things when shapes are suddenly changed.

Call this when you make any change that adds or removes objects or changes the
size or position of existing objects.

reinit(rtn_success = True) -> success

rtn_success: whether to return success (if True, this function may take
             longer).  If False, the return value may be None (but may also
             still be a bool, in which case the success has been determined).

success: one of the things this method does is try to ensure that no objects
         that can collide with each other are overlapping; success indicates
         whether this was possible.  The attempt is deemed to have failed if
         resolving the situation require pushing an object more than half of
         the way through another.

"""
        self._cache_shapes()
        success = self._fix_colliding()
        self._update_contact()
        return success

    def update (self):
        """Move all objects by their current velocities, handling collisions.

Afterwards, velocities and positions of objects may have changed.

"""
        before_cb = self.before_cb
        after_cb = self.after_cb
        moving_shapes = self._moving_shapes
        moving_lines = self._moving_lines
        lines = self._lines
        touching = self._touching
        remaining_vel = dict((s, list(s.obj.vel)) for s in moving_shapes)
        total_tr = 1
        while True:
            # find all collisions that may happen
            collisions = []
            checked = set()
            for i, moving_ls in enumerate(moving_lines):
                axis = i % 2 # axis in which the collision occurs
                dirn = 1 if i >= 2 else -1
                j = (i + 2) % 4
                ls = lines[j]
                for l1, o1, i1 in moving_ls:
                    checked.add((i, o1, i1))
                    # get velocity of l1
                    v1 = remaining_vel[o1.shape]
                    v1pr = dirn * v1[axis]
                    v1pl = v1[not axis]
                    # get start/end positions for l1
                    l10pr, l10pl0, l10pl1 = l1
                    l10pr *= dirn
                    l11pr = l10pr + v1pr
                    l11pl0 = l10pl0 + v1pl
                    l11pl1 = l10pl1 + v1pl
                    for static, l2, o2, i2 in ls:
                        # don't check the same collision twice
                        if (j, o2, i2) in checked:
                            continue
                        # don't check an object against itself
                        if o2 is o1:
                            continue
                        # don't check if in different layers
                        if not (o2.layer & o1.layer):
                            continue
                        # get velocity of l2
                        v2 = [0, 0] if static else remaining_vel[o2.shape]
                        v2pr = dirn * v2[axis]
                        v2pl = v2[not axis]
                        # don't collide if not moving towards each other
                        if v1pr <= v2pr:
                            continue
                        # get start/end positions for l2
                        l20pr, l20pl0, l20pl1 = l2
                        l20pr *= dirn
                        l21pr = l20pr + v2pr
                        l21pl0 = l20pl0 + v2pl
                        l21pl1 = l20pl1 + v2pl
                        # don't collide if don't move past each other
                        if l10pr > l20pr or l11pr <= l21pr:
                            continue
                        # get ratio of distance moved before collision
                        d = l11pr - l10pr - l21pr + l20pr
                        # d = 0 sometimes because of floating-point errors,
                        # even though the previous check implies d > 0
                        if d == 0:
                            continue
                        t = float(l20pr - l10pr) / (l11pr - l10pr - l21pr + \
                                                    l20pr)
                        # get line endpoints at t
                        l1tpl0 = l10pl0 + t * v1pl
                        l1tpl1 = l10pl1 + t * v1pl
                        l2tpl0 = l20pl0 + t * v2pl
                        l2tpl1 = l20pl1 + t * v2pl
                        # don't collide if endpoints don't overlap at t
                        if l1tpl1 <= l2tpl0 or l2tpl1 <= l1tpl0:
                            continue
                        # found a collision
                        collisions.append((t, i, j, static, o1, i2, l1, v1, o2,
                                           i2, l2, v2))
            if collisions:
                # get first collision
                if before_cb:
                    # call before_cb
                    collisions.sort()
                    while True:
                        t, i, j, static, o1, \
                            i1, l1, v1r, o2, i2, l2, v2r = collisions.pop(0)
                        e = o1.elast * o2.elast
                        f = o1.frict * o2.frict
                        data = [e, f]
                        if before_cb(o1, o2, i, i1, i2, data):
                            # ignore this collision
                            if not collisions:
                                # no collisions left
                                t = 1
                                break
                        else:
                            # we have a collision to handle
                            e, f = data
                            collisions = True
                            break
                else:
                    t, i, j, static, \
                        o1, i1, l1, v1r, o2, i2, l2, v2r = min(collisions)
                    e = o1.elast * o2.elast
                    f = o1.frict * o2.frict
                # add to touching list (avoid symmetric duplicates)
                k = (i, o1, i1, o2, i2)
                k2 = (j, o2, i2, o1, i1)
                if k2 in touching:
                    k = k2
                touching[k] = (l1, l2)
            else:
                # no collisions
                t = 1
            # move all objects up to first collision, if any
            tr = 1 - t
            total_tr *= tr
            if t != 0:
                for s in moving_shapes:
                    vx, vy = remaining_vel[s]
                    if not (vx == vy == 0):
                        s._move((vx * t, vy * t))
                        if tr != 0:
                            v = remaining_vel[s]
                            v[0] = vx * tr
                            v[1] = vy * tr
            if collisions:
                # handle first collision
                axis = i % 2
                m1, v1 = float(o1.mass), o1.vel
                if static:
                    # parallel
                    u1pl = v1[axis]
                    v1[axis] = -e * u1pl
                    v1r[axis] *= -e
                    dvpl = abs(u1pl + e * u1pl)
                    Ipl = m1 * dvpl
                    if f != 0:
                        # perpendicular
                        u1pr = v1[not axis]
                        d = 1 if u1pr > 0 else -1
                        v1pr = d * u1pr - f * dvpl
                        v1pr = d * max(v1pr, 0)
                        v1[not axis] = v1pr
                        v1r[not axis] = v1pr * total_tr
                        Ipr = m1 * abs(v1pr - u1pr)
                    else:
                        Ipr = 0
                else:
                    # floating point errors can cause the objects not to be in
                    # the same place, which leads to bad things, so adjust them
                    l1_pr, l2_pr = l1[0], l2[0]
                    if l1_pr != l2_pr:
                        v = [0, 0]
                        v[axis] = l2_pr - l1_pr
                        o1.shape._move(v)
                    # parallel
                    v2 = o2.vel
                    u1pl, u2pl, m2 = v1[axis], v2[axis], o2.mass
                    p0 = m1 * u1pl + m2 * u2pl
                    m = m1 + m2
                    v1pl = (p0 + (u2pl - u1pl) * e * m2) / m
                    v2pl = (p0 + (u1pl - u2pl) * e * m1) / m
                    v1[axis], v2[axis] = v1pl, v2pl
                    v1r[axis], v2r[axis] = v1pl * total_tr, v2pl * total_tr
                    Ipl = m1 * abs(v1pl - u1pl)
                    if f != 0:
                        # perpendicular
                        u1pr, u2pr = v1[not axis], v2[not axis]
                        Ipr = 2 * f * Ipl
                        # relative to velocity of centre of mass frame
                        v0 = (m1 * u1pr + m2 * u2pr) / m
                        for m, upr, v, vr in ((m1, u1pr, v1, v1r),
                                              (m2, u2pr, v2, v2r)):
                            d = 1 if upr > v0 else -1
                            vpr = d * (upr - v0) - Ipr / m
                            vpr = d * max(vpr, 0) + v0
                            v[not axis] = vpr
                            vr[not axis] = vpr * total_tr
                        Ipr = m * abs(vpr - upr) # might be different
                    else:
                        Ipr = 0
                # call after_cb
                if after_cb:
                    I = 2 * (Ipr * Ipr + Ipl * Ipl) ** .5
                    after_cb(o1, o2, i, i1, i2, I)
            else:
                # done
                break
        # update touching surfaces
        touching_cb = self.touching_cb
        err = self.err
        rm = []
        for k, (l1, l2) in touching.iteritems():
            i, o1, i1, o2, i2 = k
            l1pr, l1pl0, l1pl1 = l1
            l2pr, l2pl0, l2pl1 = l2
            if abs(l1pr - l2pr) > err or l1pl0 >= l2pl1 or l1pl1 <= l2pl0:
                rm.append(k)
            elif touching_cb:
                # still touching
                touching_cb(o1, o2, i, i1, i2)
        for k in rm:
            del touching[k]
