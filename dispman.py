"""Display manager for Pygame.

DisplayManager manages multiple displays on a single Pygame surface, each given
a rect to draw in.  It doesn't do much: for something more interesting like
layers or automatic display placement, use a subclass.  Display is the basic
display class, and has subclasses too.

Python version: 2.
Release: 3-dev.

Licensed under the GNU Lesser General Public License, version 3; if this was
not included, you can find it here:
    https://www.gnu.org/licenses/lgpl-3.0.txt

    CLASSES

Display
ScrollingDisplay
DisplayManager
LayeredDisplayManager
SplitScreenDisplayManager
GridDisplayManager [NOT IMPLEMENTED]

TODO:
 - scroll policies
 - GridDM

"""

from math import ceil, log
from collections import OrderedDict

import pygame

from miscutil import split

_num = (int, long, float)

def _const_vel (d, *vels):
    if not hasattr(d, 'vel'):
        if isinstance(vels[0], _num):
            # just got one vel
            vels = [vels]
        else:
            vels = [list(v) for v in vels]
        vel = vels[0]
        vels = vels[1:]
        if not isinstance(vel[0], _num):
            # remove time from first vel
            vel = vel[0]
        d.t = 0
        d.real_pos = list(d.pos)
        d.vel = vel
        d.vels = vels
    vx, vy = d.vel
    x, y = d.real_pos
    x += vx
    y += vy
    d.real_pos = [x, y]
    d.pos = [int(x), int(y)]
    # get next vel if necessary
    vels = d.vels
    if vels:
        d.t += 1
        if d.t >= vels[0][1]:
            d.vel = vels.pop(0)[0]

def _damped (d, obj, inner, outer = None, speed = 0.5):
    if not hasattr(d, 'inner'):
        d_r = d.rect
        if outer is None:
            outer = d_r
        for attr, r in (('inner', inner), ('outer', outer)):
            if isinstance(r, _num):
                r = (r * d_r[2], r * d_r[3])
            if len(r) == 2:
                offset = ((d_r[2] - r[0]) / 2, (d_r[3] - r[1]) / 2)
                r = (d_r[0] + offset[0], d_r[1] + offset[1], r[0], r[1])
            setattr(d, attr, pygame.Rect(r))
        if not d.outer.contains(d.inner):
            msg = 'damped scrolling: outer rect must contain inner rect'
            raise ValueError(msg)
    p = []
    for i in (0, 1):
        # get amount to move to be in inner
        a = d.inner[i]
        b = a + d.inner[i + 2]
        o = obj.pos[i]
        x = d.pos[i]
        if o < a:
            diff = a - o
        elif o > b:
            diff = b - o
        else:
            diff = 0
        x += diff * speed
        p.append(x)
    d.pos = p

POLICY_SCROLL = {'const_vel': _const_vel, 'damped': _damped}
POLICY_CLEANUP = {}

class Display:
    """A basic display.

    CONSTRUCTOR

Display(rect, draw_fn)

rect: display area Pygame-style rect.
draw_fn: function to call to draw to the surface.  This must be of the form

    draw_fn(display, surface, dirty) -> drew

    display: this Display instance.
    surface: the surface to draw to.
    dirty: a bool indicating whether this display's area might have been drawn
           over since the last call.
    drew: whether any changes were made to the surface.

    METHODS

draw
destroy

    ATTRIBUTES

rect, draw_fn: from constructor.
dirty: whether this display may have been drawn over since the last draw.

"""

    def __init__ (self, rect, draw_fn):
        self.rect = pygame.Rect(rect)
        self.draw_fn = draw_fn
        self.dirty = True

    def draw (self, screen):
        """Draw to the given surface.

draw(screen) -> drew

screen: the Pygame surface to draw to.

drew: whether any changes were made to the surface.

"""
        drew = bool(self.draw_fn(self, screen, self.dirty))
        self.dirty = False
        return drew

    def destroy (self, *attrs):
        """Break references to some objects."""
        for attr in ('rect', 'draw_fn') + attrs:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

class ScrollingDisplay (Display):
    """Display subclass to handle scrolling.

    CONSTRUCTOR

ScrollingDisplay(rect, draw_fn, pos[, policy[, args][, policy_cleanup]])

pos: the initial [x, y] position in the scrollable virtual area.
policy: a policy identifier to use, to determine how to scroll.  One of those
        in dispman.POLICY_SCROLL, or a function that takes this
        ScrollingDisplay instance then args.  If not given, don't scroll.
policy_cleanup: if policy is a function, this can be a function that takes this
                ScrollingDisplay instance to delete attributes stored by calls
                to policy.  This happens when ScrollingDisplay.set_policy is
                called to switch to a different scroll policy.
args: arguments passed to the scroll function (determined by policy) every
      call.

    POLICIES

const_vel (*vels):
    scroll at a constant velocity.

vels: one or more (velocity, start_time) tuples, where velocity is an (x, y)
      velocity to scroll at and start_time is the number of ticks (calls to
      draw) until this velocity is in effect.  These must be ordered by
      start_time.  The first argument may just be velocity (if start_time is
      also given, it is ignored).

damped (obj, inner[, outer], speed = 0.5):
    keep something in a rect with smooth motion.

obj: something with a pos attribute, which is its (x, y) position relative to
     the display.
inner: a rect relative to the display to keep the object in - if outside,
       scrolling will take place to move it inside.  This can also be
       (width, height) for a rect centred in the display, or a number giving
       the rect's size as a ratio of the display size for a centred rect.
outer: a rect relative to the display to keep the object in - it will never be
       outside this rect.  Can be (width, height) or a number like inner.  If
       not given, the display's rect is used.
speed: the speed with which the object is scrolled into inner.  Between 0 and
       1.

    METHODS

set_policy

    ATTRIBUTES

pos: the current [x, y] position in the scrollable virtual area.
policy: from constructor.

"""

    def __init__ (self, rect, draw_fn, pos, policy = None, args = (),
                  policy_cleanup = None):
        Display.__init__ (self, rect, draw_fn)
        self.pos = list(pos)
        self.policy = None
        self.set_policy(policy, args, policy_cleanup)

    def _scroll (self):
        """Update scroll position using policy."""
        if self.policy is not None:
            self._scroll_fn(self, *self._policy_args)

    def set_policy (self, policy = None, args = (), policy_cleanup = None):
        """Set the scroll policy.

Takes policy, args and policy_cleanup arguments as required by the constructor.
Call with no arguments to disable scrolling.

"""
        if policy == self.policy:
            # same policy; might want to change args/cleanup function, though
            self._policy_args = args
            if policy is not None and not isinstance(policy, basestring):
                self._policy_cleanup = policy_cleanup
            return
        # perform cleanup for current policy, if any
        if isinstance(self.policy, basestring):
            # built-in
            try:
                POLICY_CLEANUP[self.policy](self)
            except AttributeError:
                pass
        elif self.policy is not None and self._policy_cleanup is not None:
            # custom
            self._policy_cleanup(self)
            del self._policy_cleanup
        # set new policy
        self.policy = policy
        if policy is None:
            # if disabling scrolling, clean up some attributes we won't need
            try:
                del self._scroll_fn, self._policy_args
            except AttributeError:
                pass
        else:
            self._policy_args = args if args else ()
            if isinstance(policy, basestring):
                # built-in
                self._scroll_fn = POLICY_SCROLL[policy]
            else:
                # custom
                self._scroll_fn = policy
                self._policy_cleanup = policy_cleanup

    def draw (self, screen):
        self._scroll()
        return Display.draw(self, screen)

    def destroy (self):
        Display.destroy(self, 'pos', '_policy', '_scroll_fn', '_policy_args', 
                        '_policy_cleanup')

class DisplayManager:
    """Basic display manager.

    CONSTRUCTOR

DisplayManager([screen])

screen: the Pygame surface to draw to; defaults to the return value of
        pygame.display.get_surface.

    METHODS

open_display
close_display
resize
draw

    ATTRIBUTES

screen: from constructor.
displays: list of open displays.

"""

    def __init__ (self, screen = None):
        if screen is None:
            self.screen = pygame.display.get_surface()
        else:
            self.screen = screen
        self.displays = []

    def open_display (self, *display_args, **kw):
        """Create a new display.

open_display(*display_args, cls = Display) -> display

display_args: positional arguments to pass to the created display.
cls (keyword-only): the display class to use.

display: the created display.

Displays are automatically cropped to fit in the screen; if the rect given is
outside the screen entirely, ValueError is raised.

"""
        # first display argument is always rect; crop it to fit on the screen
        rect = pygame.Rect(display_args[0]).clip(self.screen.get_rect())
        if any(rect.colliderect(d.rect) for d in self.displays):
            raise ValueError('rect overlaps other displays')
        if rect.w == rect.h == 0:
            raise ValueError('rect outside of screen')
        # create display
        new_disp = kw.get('cls', Display)(rect, *display_args[1:])
        self.displays.append(new_disp)
        return new_disp

    def close_display (self, display):
        """Destroy the given display and remove it from the screen.

Doesn't draw over the display.

"""
        display.destroy()
        self.displays.remove(display)

    def resize (self, error_on_crop = False):
        """Notify the display manager that the surface size has changed.

resize(error_on_crop = False) -> changed

error_on_crop: whether to throw an exception (ValueError) if this operation
               will change the size or position of any display.  If a display
               is completely outside the new surface rect, ValueError is thrown
               regardless of this argument.

changed: a list of displays whose sizes or positions have changed.

"""
        screen_rect = self.screen.get_rect()
        changed = []
        rects = []
        for display in self.displays:
            # find display rect cropped to fit in new screen rect
            rect = display.rect.clip(screen_rect)
            if rect != display.rect:
                if rect.w == rect.h == 0:
                    raise ValueError('display outside of screen')
                elif error_on_crop:
                    raise ValueError('display size changed')
                else:
                    changed.append(display)
                    rects.append(rect)
        # only make changes once we've checked for any errors
        for display, rect in zip(changed, rects):
            display.rect = rect
        return changed

    def draw (self):
        """Tell every display to draw

Returns whether any changes were made to any screens.

"""
        screen = self.screen
        dirty = False
        for display in self.displays:
            dirty |= display.draw(screen)
        return dirty

class LayeredDisplayManager (DisplayManager):
    """DisplayManager subclass that handles displays in multiple layers.

    ATTRIBUTES

layers: a {z-index: displays} dict (collections.OrderedDict).

"""

    def __init__ (self, screen = None):
        DisplayManager.__init__(self, screen)
        self.layers = OrderedDict()

    def open_display (self, z, *display_args, **kw):
        """Create a new display.

Displays are automatically cropped to fit in the screen; if the rect given is
outside the screen entirely, ValueError is raised.  ValueError is also raised
if the display would overlap any existing ones in the same layer (same
z-index).

open_display(z, *display_args, cls = Display) -> display

z: the z-index of the layer to draw the display to.  Lower z-indexes are lower
   down (drawn first).
display_args: positional arguments to pass to the created display.
cls (keyword-only): the display class to use.

display: the created display.

"""
        if z in self.layers:
            layer = self.layers[z]
        else:
            # new layer
            self.layers[z] = layer = []
            l = self.layers
            # resort layers
            self.layers = OrderedDict((z, l[z]) for z in sorted(l))
        # first display argument is always rect
        rect = pygame.Rect(display_args[0])
        if any(rect.colliderect(d.rect) for d in layer):
            raise ValueError('rect overlaps other displays in the same layer')
        new_disp = DisplayManager.open_display(self, rect, *display_args[1:],
                                               **kw)
        self.displays.append(new_disp)
        layer.append(new_disp)
        # set some attributes on the display
        new_disp.z = z
        overlaps = []
        overlapped = []
        for layer, displays in self.layers.iteritems():
            if layer != z:
                for display in displays:
                    if display.rect.colliderect(rect):
                        if layer < z:
                            # get displays this one overlaps
                            display.overlapped.append(new_disp)
                            overlaps.append(display)
                        elif layer > z:
                            # get displays that overlap this one
                            display.overlaps.append(new_disp)
                            overlapped.append(display)
        new_disp.overlaps = overlaps
        new_disp.overlapped = overlapped
        return new_disp

    def close_display (self, display):
        """Destroy the given display and remove it from the screen.
Doesn't draw over the display.

"""
        z = display.z
        self.layers[z].remove(display)
        # remove layer if empty now
        if not self.layers[z]:
            del self.layers[z]
        # remove display from overlaps/overlapped lists
        for disp in display.overlaps:
            disp.overlapped.remove(display)
        for disp in display.overlapped:
            disp.overlaps.remove(display)
            disp.dirty = True
        # this class stores some extra attributes in displays
        display.destroy('overlaps', 'overlapped')
        self.displays.remove(display)

    def draw (self):
        """Tell every display to draw, in layer order."""
        screen = self.screen
        dirty = False
        for z, displays in self.layers.iteritems():
            for display in displays:
                drew = display.draw(screen)
                # if made changes to the surface
                if drew:
                    # set any displays that overlap this one dirty
                    for d in display.overlapped:
                        d.dirty = True
                dirty |= drew
        return dirty

class SplitScreenDisplayManager (DisplayManager):
    """Automatically arrange displays in a splitscreen format.

    CONSTRUCTOR

SplitScreenDisplayManager([screen], expand = True[, ratio], split = 0, pos = 0,
                          padding = 0)

screen: the Pygame surface to draw to; defaults to the return value of
        pygame.display.get_surface.
expand: some rows/columns may have one display fewer than the maximum; set
        expand to True to make those displays use up the free space (so some
        displays are larger than others).
ratio: the aspect ratio (width / height) to aim for when arranging displays;
       defaults to the aspect ratio of screen.
split: which axis to split the surface into first: 0 for rows, 1 for columns,
       None to choose which fits best.
pos: the position of rows/columns with fewer displays: <0 for top/left, 0 for
     centre, >0 for bottom/right.
padding: the proportion of padding to place between displays in rows/columns
         with fewer, as opposed to at the sides.  0 has no space between
         displays, 1 has no space between displays and the edges of the
         surface.

Displays are arranged such that the amount of free space is minimised, and the
aspect ratio of displays is near the given ratio argument (both before
expanding some displays as necessary).

    METHODS

lock
unlock

    ATTRIBUTES

locked: whether this display manager is currently locked.

"""

    def __init__ (self, screen = None, expand = True, ratio = None, split = 0,
                  pos = 0, padding = 0):
        DisplayManager.__init__(self, screen)
        self.expand = expand
        self.ratio = ratio
        self.split = split
        self.pos = pos
        self.padding = padding
        self.locked = False

    def _optimal_splits (self, split_axis):
        """Find the optimal number of rows/columns (as given) of displays."""
        n = len(self.displays)
        size = self.screen.get_size()
        # sizes in directions of first/second split
        s1 = size[split_axis]
        s2 = size[not split_axis]
        ratio = self.ratio
        # use screen aspect ratio if no preferred one given
        if ratio is None:
            ratio = float(size[0]) / size[1]
        error = []
        for splits in xrange(1, n + 1):
            # maximal number of displays per row/column
            per_split = ceil(float(n) / splits)
            # minimise unused space (as a fraction of the screen)
            space_e = abs(1 - float(n) / (splits * per_split))
            # and ratio (we care about proportionality, so use log)
            disp_ratio = float(s1 * splits) / (s2 * per_split)
            if split_axis == 1:
                # inverted if splitting into columns
                disp_ratio = 1 / disp_ratio
            ratio_e = abs(log(disp_ratio / ratio))
            # adjust using some constants
            e = space_e + ratio_e
            error.append((e, splits))
        return min(error)

    def _arrange_displays (self):
        """Compute and apply optimal display rects.

Returns displays whose rects were changed.

"""
        if self.locked:
            self._changed = True
            return []
        n = len(self.displays)
        if n == 0:
            return []
        # find the optimal number of initial splits (rows/columns)
        data = []
        # if not given, check splitting into both rows and columns
        for axis in ((0, 1) if self.split is None else (self.split,)):
            data.append(self._optimal_splits(axis) + (axis,))
        error, splits, axis = min(data)
        # determine distribution of displays over splits
        per_split = int(ceil(float(n) / splits))
        num_unfilled = splits * per_split - n
        num_filled = splits - num_unfilled
        # decide display sizes
        screen_size = self.screen.get_size()
        split_sizes = split(screen_size[not axis], splits)
        to_fill = screen_size[axis]
        filled_sizes = split(to_fill, per_split)
        if self.expand:
            unfilled_sizes = split(to_fill, per_split - 1)
        else:
            unfilled_sizes = filled_sizes[:-1]
        # decide where unfilled splits go
        if self.pos < 0:
            filled = [False] * num_unfilled + [True] * num_filled
        elif self.pos < 0:
            filled = [True] * num_filled + [False] * num_unfilled
        else:
            filled = ([True] * (num_filled / 2) + [False] * num_unfilled +
                      [True] * (num_filled - num_filled / 2))
        # determine allocation of padding in unfilled splits
        padding = to_fill - sum(unfilled_sizes)
        inner_padding = int(self.padding * padding)
        outer_padding = padding - inner_padding
        padding = [outer_padding / 2] + split(inner_padding, per_split - 2)
        # construct rects and assign to displays
        displays = self.displays[:]
        changed = []
        x = 0
        #print n, axis, splits, split_sizes, filled_sizes, unfilled_sizes, filled
        for i in xrange(splits):
            y = 0
            for j in xrange(per_split + filled[i] - 1):
                display = displays.pop()
                if not filled[i]:
                    # this split is unfilled: include padding
                    y += padding[j]
                sizes = (unfilled_sizes, filled_sizes)[filled[i]]
                # construct rect
                if axis == 1:
                    rect = [x, y, split_sizes[i], sizes[j]]
                else:
                    rect = [y, x, sizes[j], split_sizes[i]]
                rect = pygame.Rect(rect)
                if rect != display.rect:
                    changed.append(display)
                    display.rect = rect
                y += sizes[j]
            x += split_sizes[i]
        return changed

    def open_display (self, *display_args, **kw):
        """Create a new display.

open_display(*display_args, cls = Display) -> (display, changed)

display_args: positional arguments to pass to the created display, not
              including rect (the first argument).
cls (keyword-only): the display class to use.

display: the created display.
changed: a list of displays whose rects changed as a result of rearranging the
         existing displays.

"""
        new_disp = kw.get('cls', Display)((0, 0, 0, 0), *display_args)
        self.displays.append(new_disp)
        return (new_disp, self._arrange_displays())

    def close_display (self, display):
        """Destroy the given display and remove it from the screen.

Doesn't draw over the display.  Returns a list of displays whose rects changed
as a result of rearranging them.

"""
        DisplayManager.close_display(self, display)
        return self._arrange_displays()

    def resize (self):
        """Notify the display manager that the surface size has changed.

Returns a list of displays whose rects changed as a result of rearranging them.

"""
        return self._arrange_displays()

    def draw (self):
        if self.locked:
            raise Exception('this display manager is locked')
        return DisplayManager.draw(self)

    def lock (self):
        """Lock this display manager.

When locked, the arrangement of displays is not calculated when one is added or
removed, and drawing is disabled.  This is used before adding multiple
displays, to save doing extra processing between additions.

"""
        self.locked = True
        self._changed = False

    def unlock (self):
        """Unlock this display manager.

Returns a list of displays whose rects changed as a result of rearranging them.

"""
        if self.locked:
            self.locked = False
            if self._changed:
                return self._arrange_displays()
        return []

class GridDisplayManager:
    pass
