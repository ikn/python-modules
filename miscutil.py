"""Miscellaneous stuff.

Python version: 2.
Release: 6.

    CLASSES

Out

    FUNCTIONS

split
greedy
fit
startwith
parse_time
nice_time

    DATA

reserved_kw: list of Python reserved keywords

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

"""

from calendar import monthrange
from time import localtime, ctime, time
from re import match

class Out:
    """A generic .write-able class.

Pass a function to act as a write method.  This is useful for, for example,
piping stuff that gets sent to sys.stdout to your own write function.  If no
argument is given, write does nothing.

A function to act as a flush method can be passed as a second argument; if it
is not, Out.flush() does nothing.

"""

    def __init__ (self, write_function = None, flush_function = None):
        if write_function is None:
            self.write = lambda *args: None
        elif not hasattr(write_function, '__call__'):
            raise TypeError('argument must be callable')
        else:
            self.write = write_function
        if flush_function is None:
            self.flush = lambda *args: None
        elif not hasattr(flush_function, '__call__'):
            raise TypeError('argument must be callable')
        else:
            self.flush = flush_function

def split (size, intervals):
    """Split a region into integer-sized intervals.

split(size, intervals) -> size_list

size: the size of the region to split.
intervals: the number of intervals to use.

size_list: a list of sizes for each interval in turn.

"""
    intervals = max(intervals, 0)
    if intervals == 0:
        return []
    if intervals == 1:
        return [size]
    avg = float(size) / intervals
    base = int(avg)
    diff = avg - base
    sizes = []
    current_diff = 0
    for i in xrange(intervals):
        # add up excess bits
        current_diff += diff
        # when we have 1, add it on
        if current_diff >= 1:
            sizes.append(base + 1)
            current_diff -= 1
        else:
            sizes.append(base)
    # adjust first interval (probably only by 1, if any)
    sizes[0] += size - sum(sizes)
    return sizes

def greedy (sets, universe = None):
    """Greedy algorithm for set covering.

greedy(sets[, universe]) -> result set

"""
    set2int, int2orig, temp, sets = [], {}, sets, []
    for s in temp:
        t = set(s)
        sets.append(t)
        set2int.append(t)
        int2orig[set2int.index(t)] = s
    if universe is None:
        # take union of sets
        universe = set()
        for s in sets:
            universe = universe.union(s)
    else:
        universe = set(universe)
    result = []
    covered = set()
    while True:
        # find set with most uncovered elements
        uncovered = universe.difference(covered)
        num_uncovered = 0
        has_most = None
        for s in sets:
            i = len(s.intersection(uncovered))
            if i > num_uncovered:
                num_uncovered = i
                has_most = s
        if num_uncovered == 0:
            raise Exception('union of sets isn\'t universe')
        else:
            result.append(int2orig[set2int.index(s)])
            sets.remove(s)
        covered = covered.union(s)
        if covered == universe:
            return result

def fit (string, length, char = ' ', pos = 0, end = ''):
    """Grow or shrink a string to be a specified length.

fit(string, length, char = ' ', pos = 0, end = '') -> string

The string is either padded to make it large enough or truncated on the right
to make it small enough.

char: string (gets truncated to one character) to use to expand the string.
pos: alignment of the string when padding: 0 left, 1 centre biased left, 2
     centre biased right, 3 right (bias is for odd total padding length).
end: string to suffix the string with if it must be shortened.

"""
    if not isinstance(string, basestring):
        string = str(string)
    if not isinstance(char, basestring):
        char = str(char)
    if not isinstance(end, basestring):
        end = str(end)
    if not char:
        raise ValueError('char cannot have zero length')
    length = max(int(length), 0)
    pos = min(max(int(pos), 0), 3)
    if not end:
        end = ''
    l = len(string)
    if l > length:
        n = length - len(end)
        if n < 0:
            raise ValueError('ending string cannot be longer than required length')
        string = string[:length - len(end)] + end
    elif l < length:
        char = char[:1]
        n = length - l
        if pos == 0:
            a = 0
        elif pos == 1:
            a = n / 2
        elif pos == 2:
            a = (n - 1) / 2 + 1
        else:
            a = n
        b = n - a
        string = a * char + string + b * char
    return string

def startwith (pool, term, case_sensitive = True, unique = False):
    """Look in a set of strings for ones that start with a given string.

startwith(pool, term, case_sensitive = True, unique = False) -> match(es)

pool: the set of strings to search in.
term: the string to match against.
case_sensitive: whether to do case-sensitive matching.
unique: whether to require exactly one match; ValueError is raised if this is
        not the case.

match(es): if unique is True and there is one match, return it; otherwise,
           return a list of matching strings from pool.

"""
    if case_sensitive:
        matches = [x for x in pool if x.startswith(term)]
    else:
        tl = term.lower()
        matches = [x for x in pool if x.lower().startswith(tl)]
    if unique:
        if len(matches) > 1:
            raise ValueError('more than one match')
        elif matches:
            return matches[0]
        else:
            raise ValueError('no matches')
    else:
        return matches

PREFIX_TIME = {
    's': 1,
    'm': 60,
    'h': 3600,
    'd': 86400,
    'w': 604800,
    'mo': 86400 * monthrange(*localtime()[:2])[1]
}
# construct a sorted dict, sort of
TIME_PREFIX = dict((str(v), k) for k, v in PREFIX_TIME.iteritems())
TIME_PREFIX_ORDER = sorted(PREFIX_TIME.values(), reverse = True)

def parse_time (s):
    """Parse time period."""
    s = s.strip().lower()
    neg = s[0] == '-'
    if neg:
        s = s[1:].strip()
    m = match('-?(\d+)([smhdwm])', s)
    if m is None:
        raise ValueError('invalid time format')
    else:
        n, s = m.groups()
        return int(n) * PREFIX_TIME[s] * (-1 if neg else 1)

def nice_time (t):
    """Convert time period in seconds to an abbreviated, readable time."""
    t = int(t)
    result = ''
    for i in TIME_PREFIX_ORDER:
        if t == 0:
            break
        if t < i:
            continue
        result += str(t / i) + TIME_PREFIX[str(i)]
        t %= i
    if not result:
        result = '0' + 's'
    return result

reserved_kw = ['and', 'del', 'from', 'not', 'while', 'as', 'elif', 'global',
               'or', 'with', 'assert', 'else', 'if', 'pass', 'yield', 'break',
               'except', 'import', 'print', 'class', 'exec', 'in', 'raise',
               'continue', 'finally', 'is', 'return', 'def', 'for', 'lambda',
               'try', 'nonlocal', 'True', 'False', 'None']
