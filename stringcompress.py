"""String compression.

This module does two things: encoding and (very simple) compression of strings.
Encoding is general-purpose, and converts a string from one character set to
any other.  Compression, on the other hand, has a very specific use case: you
will only see significant gains for strings consisting of a small number of
different characters, especially when you know to a high degree of accuracy
what those characters will be.

This is useful for, for example, games, where you often have data in a specific
format like this - lists of numbers, say.  If the numbers are small, treat each
as a separate character by passing the list through the chr builtin, and
compress as a string of characters in the known range.  If they're large, join
them by some separator (' ', say) and compress as a string of characters in
'0123456789 '.

Python version: 2.
Release: 1.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    FUNCTIONS

s_to_x
x_to_s
base_b_to_10
base_10_to_b
convert_x_base
encode
decode
compress
decompress

    DATA

printable: list of printable ASCII characters, excluding whitespace
byte_chars: list of characters in Python bytestrings (length 256)

"""

import string
from math import log
from itertools import takewhile

printable = [c for c in string.printable if c not in string.whitespace]
byte_chars = [chr(i) for i in xrange(256)]

def s_to_x (s, chars):
    """Convert a string to a list of integers.

s_to_x(s, chars) -> x

s: string to convert.
chars: a list of characters that s may contain, without repetitions.

x: a list of integers corresponding to the characters of s by taking the index
   of the character in chars.

"""
    char_to_digit = dict((c, i) for i, c in enumerate(chars))
    return [char_to_digit[c] for c in s]

def x_to_s (x, chars):
    """Convert a list of integers to a string.

x_to_s(x, chars) -> s

The reverse of s_to_x.

"""
    return ''.join(chars[d] for d in x)

def base_b_to_10 (l, base):
    """Convert a list of digits in the given base to a base-10 integer.

base_b_to_10(l, base) -> x

l: list of digits.
base: the base of the digits in l.

x: base-10 integer.

"""
    n = len(l)
    return sum(d * base ** (n - i - 1) for i, d in enumerate(l))

def base_10_to_b (x, base):
    """Convert a base-10 integer to a list a digits in the given base.

base_10_to_b(x, base) -> l

The reverse of base_b_to_10.

"""
    # append digits from high to low
    l = []
    if x != 0:
        for i in xrange(int(log(x) / log(base)), -1, -1):
            order = base ** i
            l.append(x / order)
            x %= order
    return l

def convert_x_base (x, base1, base2):
    """Change the base of a list of digits.

convert_x_base(x, base1, base2) -> y

x: the list of digits to convert.
base1: the base of x.
base2: the base to convert to.

y: a list of digits in base2 of value equal to x.

"""
    # convert to base 10
    x = base_b_to_10(x, base1)
    # convert from base 10
    return base_10_to_b(x, base2)

def encode (s, from_chars = byte_chars, to_chars = printable,
            allow_no_sep = True):
    """Encode a string from one character set to another.

encode(s, from_chars = byte_chars, to_chars = printable, allow_no_sep = True)
    -> new_string

s: the string to encode.
from_chars: a list of the characters in s (and possibly more).
to_chars: a list of the characters to construct the output out of.
allow_no_sep: the output has two parts: the number of initial zero-values in s
              followed by the rest of s, separated by a separating character.
              The separator is omitted if there are no initial zeroes; passing
              False for this argument disables this behaviour.  You should only
              care about this argument if you expect to modify the encoded
              string.

This process is not symmetric with swapped arguments (for reasons outlined
above).  To obtain the original string, use decode.

"""
    # reserve first character as separator
    sep = to_chars[0]
    to_chars = to_chars[1:]
    # convert to from_chars indices
    x = s_to_x(s, from_chars)
    # store number of leading 0s
    zeroes = len(list(takewhile(lambda d: d == 0, x)))
    x = x[zeroes:]
    # convert to to_chars indices
    zeroes = base_10_to_b(zeroes, len(to_chars))
    x = convert_x_base(x, len(from_chars), len(to_chars))
    # convert to to_chars string
    s = x_to_s(zeroes, to_chars) + sep + x_to_s(x, to_chars)
    if allow_no_sep and s[0] == sep:
        return s[1:]
    else:
        return s

def decode (s, to_chars = byte_chars, from_chars = printable):
    """Decode a string encoded with encode.

decode(s, to_chars = byte_chars, from_chars = printable) -> original_string

s: the encoded string.
to_chars: the value used as the from_chars argument to encode.
from_chars: the value used as the to_chars argument to encode.

The string can be decoded for either value of allow_no_sep passed to encode.

"""
    # reserve first character as separator
    sep = from_chars[0]
    from_chars = from_chars[1:]
    # extract zeroes and to_chars
    try:
        zeroes, s = s.split(sep)
    except ValueError:
        zeroes = ''
    # convert to from_chars indices
    x = s_to_x(s, from_chars)
    zeroes = s_to_x(zeroes, from_chars)
    # convert to to_chars indices
    from_base = len(from_chars)
    zeroes = [0] * base_b_to_10(zeroes, from_base)
    x = zeroes + convert_x_base(x, from_base, len(to_chars))
    # convert to to_chars string
    return x_to_s(x, to_chars)

def compress (s, to_chars = printable, from_chars_container = byte_chars):
    """Compress a string.

compress(s, to_chars = printable, from_chars_container = byte_chars)
    -> compressed_string

s: the string to compress.
to_chars: a list or string of the characters the output should be made up of.
          If this contains repeated characters, the original string might not
          be recoverable.
from_chars_container: a list or string of the characters that might appear in
                      the string to compress. If this contains repeated
                      characters, the output might be larger.

The results are mostly determined by the choice of from_chars_container.  This
should be the smallest possible list, with characters in order of likely
appearance, the most likely first.

Additionally, for short strings (where an extra 2-3 characters matters), it is
more important that the first character of from_chars_container is not equal to
the first character of s than it is for this to be the most likely character to
appear.  In this case, make the first character the least likely to be first,
followed by the most likely to appear, and so on.

"""
    from_chars = list(set(s))
    if len(from_chars) >= 2 and from_chars[0] == s[0]:
        # switch first two from_chars characters to avoid tracking zeroes
        from_chars[0], from_chars[1] = from_chars[1], from_chars[0]
    # do whichever's better: encoding from from_chars and embedding from_chars,
    # or encoding from from_chars_container and embedding nothing
    s1 = encode(s, from_chars, to_chars)
    s2 = encode(s, from_chars_container, to_chars)
    chars_store = encode(from_chars, from_chars_container, to_chars, False)
    s1 += to_chars[0] + chars_store
    return (s1, s2)[len(s2) < len(s1)]

def decompress (s, from_chars = printable, to_chars_container = byte_chars):
    """Decompress a string compressed with compress.

decompress(s, from_chars = printable, to_chars_container = byte_chars)
    -> original_string

s: the compressed string.
from_chars: the value used as the to_chars argument to compress.
to_chars_container: the value used as the from_chars_container argument to
                    compress.

It is important that the order of elements in arguments that were passed to
compress is the same as given here.

"""
    sep = from_chars[0]
    n = s.count(sep)
    if n > 1:
        # includes encoded to_chars
        l = s.split(sep)
        s = sep.join(l[:n - 1])
        to_chars = sep.join(l[n - 1:])
        # decode using to_chars_container
        to_chars = decode(to_chars, to_chars_container, from_chars)
    else:
        to_chars = to_chars_container
    # decode string
    return decode(s, to_chars, from_chars)
