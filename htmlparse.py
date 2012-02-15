"""(X)HTML parser.

This module contains a loose parser for (decent) (X)HTML, with the aim being to
provide a simple interface to the element tree that results in as little code
as possible.

Depends on miscutil.

Python version: 2.
Release: 4.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    CLASSES

HTMLTextNode
HTMLDoctype
HTMLComment
HTMLTree
Selection

    FUNCTIONS

tree_from_url
fullurl

"""

import re

from miscutil import reserved_kw

try:
    from fetch import get
except ImportError:
    from urllib2 import urlopen
    get = lambda url: urlopen(url).read()

def fullurl (url, source):
    """Find the absolute URL from a given link found at a given URL.

fullurl(url, source) -> absolute_url

url: link as found on source page.
source: URL of source page.

"""
    url = url.replace('&amp;', '&')
    if '://' not in url:
        if url[:1] == '/':
            pos = source[source.find('://')+3:].find('/')
            if pos == -1:
                pos = len(source)
            else:
                pos += source.find('://')+3
        else:
            if '://' in source:
                pos = source.find('://')+3
            else:
                pos = -1
            for x in xrange(len(source)):
                if source[x] == '/':
                    pos = x+1
            if ('://' in source and pos == source.find('://')+3) or pos == -1:
                pos = len(source)+1
                source += '/'
        return source[:pos]+url
    else:
        return url

def tree_from_url (url, verbose = False):
    """Convenience function: return an HTMLTree instance for a given URL."""
    return HTMLTree(get(url), verbose)

class HTMLTextNode (object):
    """An HTML text node. Optionally takes contained text."""

    def __init__ (self, text = ''):
        if not text:
            text = ''
        self.text = text

    def __str__ (self):
        return '<{0}>'.format(type(self).__name__[4:])

    def __repr__ (self):
        text = self.text[:27] + '...' if len(self.text) > 30 else self.text
        return '<{0}: {1}>'.format(type(self).__name__[4:], repr(text))

    def out (self):
        """Source representation."""
        return self.text

class HTMLDoctype (HTMLTextNode):
    """An HTML doctype. Takes declaration string."""

    def __init__ (self, text):
        if not text:
            text = ''
        self.text = text.strip()

    def out (self):
        """Source representation."""
        return '<!doctype {0}>'.format(self.text)

class HTMLComment (HTMLTextNode):
    """An HTML comment. Optionally takes contained text."""

    def __init__ (self, text = ''):
        if not text:
            text = ''
        self.text = text.strip('!-')

    def out (self):
        """Source representation."""
        return '<!--{0}-->'.format(self.text)

_regex_comment = re.compile('(?s)<!--.*?-->')
_regex_tag_opener = re.compile('<([^\s/>="\']+)([^>]*)/?\s*>')
_regex_tag_closed = re.compile('<[^/>="\']+[^>]*/\s*>')
_regex_attrs_pattern = re.compile('([^ <>="\']+)\s*=\s*(((?P<quote>["\'])(.*?)(?P=quote))|([^ ]+))')

class HTMLTree (object):
    """An (X)HTML tree.

Optionally takes an HTML string.  If no argument is passed, an empty tree is
created.

        METHODS

    READ

has_attr
attr_match
prev_sibling
next_sibling
get_textnodes
get_elements
source
out
selection

    WRITE

set_tag
append
insert
remove

    ATTRIBUTES

nodes: list of children (HTMLTree, HTMLTextNode, HTMLDoctype or HTMLComment).
parent: parent HTMLTree, or None.
tag: top-level tag, or None.
attrs: attribute dict (exists iff tag is not None).
self_closing: whether the tag is self-closing (exists iff tag is not None).

All nodes are also put in attributes:
 - HTMLTree -> HTMLTree.tag  (if either singular or plural (+ 's') is a Python
               reserved keyword, look at '_' + HTMLTree.tag)
 - HTMLTextNode -> textnode
 - HTMLDoctype -> doctype
 - HTMLComment -> comment

Then these are found in lists at self.string + 's', and, if only one, also at
self.string.


    EXAMPLE

t = HTMLTree('<!-- some comment -->\n<p><a href="link">text</a></p>'
             '<p>sample</p>')

then:
 - t.comment is t.nodes[0] and t.comments is [t.comment]
 - t.textnode is HTMLTextNode('\n')
 - t.ps is a list of two HTMLTrees with tag = 'p' and t.p does not exist
 - t.ps[0]._a is an HTMLTree with tag = 'a', since 'as' = 'a' + 's' is a
   reserved keyword; t.ps[0]._as is [t.ps[0]._a]

"""

    def __init__ (self, raw = None, verbose = False, comment_store = None,
                  root_offset = 0, source = None):
        if not raw:
            raw = ''
        self._source = source or raw
        self._source_start = root_offset
        self._source_end = root_offset + len(raw)
        self.parent = None
        self.tag = None
        self._set_nodes = set()
        if not self._source:
            self.nodes = []
            return
        if comment_store is None:
            # escape tags in comments (top-level only)
            try:
                comments = re.finditer(_regex_comment, raw)
            except TypeError:
                # raw has invalid type; set empty
                self.nodes = []
                return
            comment_store = []
            for match in comments:
                a, b = match.start() + 1, match.end() - 1
                comment_store.append((a, b, raw[a:b]))
                raw = raw[:a] + raw[a:b].replace('<', '*').replace('>', '*') + raw[b:]
        full_raw = raw

        self.nodes = []
        rest = raw
        while rest:
            tag_start = len(full_raw) - len(rest) + root_offset
            if verbose:
                print '\t', id(self), repr(rest)
            raw = rest
            # look for starting tag
            match = re.search(_regex_tag_opener, raw)
            if match is None:
                if verbose:
                    print 'no tag:', repr(raw)
                node = HTMLTextNode(raw)
                node.parent = self
                self.nodes.append(node)
                break
            elif verbose:
                print 'tag opener:', match.groups()
            # everything before first tag is a text node
            node = HTMLTextNode(raw[:match.start()])
            node.parent = self
            self.nodes.append(node)
            raw = raw[match.start():]
            # check if self-closing with XHTML-style syntax
            tag = match.group(1).lower()
            end = match.end() - match.start()
            if re.match(_regex_tag_closed, raw) is not None:
                attrs, content = match.group(2), None
                rest = raw[end:]
                if verbose:
                    print 'xhtml-style self-close:', repr(attrs)
            # check if a comment
            elif re.match(_regex_comment, raw) is not None:
                node = HTMLComment(comment_store.pop(0)[2])
                node.parent = self
                self.nodes.append(node)
                rest = raw[end:]
                continue
            else:
                t = re.escape(tag)
                this_tag_full = re.compile('(?is)<({0})([^>]*)>(.*?)(</{0}>)'.format(t))
                this_tag_full_greedy = re.compile('(?is)<({0})([^>]*)>(.*)(</{0}>)'.format(t))
                this_tag_opener = re.compile('(?i)<{0}[^>]*>'.format(t))
                this_tag_closer = re.compile('(?i)</{0}>'.format(t))
                rest = raw
                greedy = False
                while True:
                    # get full tag and contents
                    search = re.match(this_tag_full_greedy if greedy else this_tag_full, raw)
                    if search is None:
                        # doesn't close
                        attrs, tagl = match.group(2), tag.lower()
                        content, rest, attrs = self._parse_not_closing(raw, tag, match, 0)
                        if verbose:
                            print 'no closing tag (1):', repr(attrs), repr(content)
                        break
                    # check we have the right closing tag
                    opened = len(re.findall(this_tag_opener, search.group(3)))
                    closed = len(re.findall(this_tag_closer, search.group(3)))
                    if opened == closed:
                        # we do
                        if verbose:
                            print 'normal tag:', search.groups(), match.group(1)
                        tag, attrs, content = search.group(1), search.group(2), search.group(3)
                        rest = rest[search.end():]
                        break
                    else:
                        # we don't: start again without that last closing tag in the string
                        next = re.search(this_tag_closer, (rest if greedy else raw)[search.end():])
                        if next is None:
                            # doesn't close
                            content, rest, attrs = self._parse_not_closing(raw, tag, match, 1)
                            if verbose:
                                print 'no closing tag (2):', repr(attrs), repr(content)
                            break
                        if greedy:
                            raw = rest[:search.end() + next.end()]
                        else:
                            # now grow raw to include the next closing tag
                            greedy = True
                            raw = raw[:search.end() + next.end()]
            # sort out attrs
            if tag == '!doctype':
                node = HTMLDoctype(attrs)
                node.parent = self
                self.nodes.append(node)
                continue
            temp = {}
            for i in re.finditer(_regex_attrs_pattern, attrs):
                if i.group(6) is None:
                    val = i.group(5)
                else:
                    val = i.group(6)
                if val in ('""', '\'\''):
                    val = ''
                temp[i.group(1).lower()] = val
            # take comments from source rather than raw
            tag_end = len(full_raw) - len(rest) + root_offset
            not_mine = []
            i = 0
            try:
                while comment_store[i][0] < tag_start:
                    i += 1
                while tag_start < comment_store[i][0] < tag_end:
                    not_mine.append(comment_store.pop(i))
            except IndexError:
                pass
            # parse content
            offset = root_offset + (0 if content is None else full_raw.find(content))
            if tag in self._TEXT_ONLY:
                e = HTMLTree()
                e.set_tag(tag, temp, content)
                e.append(HTMLTextNode(content))
                e._source = self._source
                e._source_start = offset
                e._source_end = offset + len(content)
                e._set_attrs()
            else:
                e = HTMLTree(content, verbose, not_mine, offset, self._source)
                e.set_tag(tag, temp, content)
            e.parent = self
            self.nodes.append(e)
        # remove empty text nodes
        i = 0
        while i < len(self.nodes):
            if type(self.nodes[i]).__name__ == 'HTMLTextNode':
                if self.nodes[i].text == '':
                    self.nodes.pop(i)
                    continue
            i += 1
        # assign children to attributes
        self._set_attrs()

    _HEAD_ELEMENTS = ('body', 'base', 'link', 'meta', 'title', 'style', 'script')
    _CANNOT_CONTAIN = {
        'head': ('body',),
        'base': _HEAD_ELEMENTS,
        'link': _HEAD_ELEMENTS,
        'meta': _HEAD_ELEMENTS,
        'thead': ('tbody',),
        'tbody': ('tfoot',),
        'tr': ('tbody', 'tfoot', 'tr'),
        'th': ('th',),
        'td': ('td',),
        'dt': ('dd',),
        'dd': ('dt',),
        'p': ('p',),
        'li': ('li',),
        'option': ('option',),
        'param': ('param',)
    }
    _EXTEND = ('html', 'body', 'tfoot') + tuple(_CANNOT_CONTAIN)
    _TEXT_ONLY = ('script', 'style', 'pre')

    def _parse_not_closing (self, raw, tag, match, which):
        # to avoid code duplication (we need this in two locations in __init__)
        # doesn't close
        attrs, tagl = match.group(2), tag.lower()
        if tagl in self._EXTEND:
            # extend to end of parent
            if tagl in self._CANNOT_CONTAIN:
                # restrict extension to start of a tag that's not allowed in this one
                start, end = match.end() - 1 + which, len(raw) - which
                for x in self._CANNOT_CONTAIN[tag.lower()]:
                    search = re.search('(?i)<{0}[^>]*>'.format(x), raw[start:])
                    if search is not None:
                        end = start + search.start()
                        if end == start:
                            break
                content, rest = raw[start:end], raw[end:]
            else:
                content, rest = raw[match.end():], ''
        else:
            # self-closing
            content, rest = None, raw[match.end():]
        return content, rest, attrs

    def _set_attrs (self):
        # put children in attributes for easy access
        for attr in self._set_nodes:
            delattr(self, attr)
        self._set_nodes = set()
        for node in self.nodes:
            # determine attribute name
            if type(node).__name__ == 'HTMLTree':
                name = node.tag
            else:
                name = type(node).__name__[4:].lower()
            if name in reserved_kw or name + 's' in reserved_kw:
                # workaround as can't use reserved keywords
                name = '_' + name
            # remove single if exists
            if hasattr(self, name):
                delattr(self, name)
                self._set_nodes.remove(name)
            # add to existing multi if possible
            if hasattr(self, name + 's'):
                tag_list = getattr(self, name + 's')
            else:
                tag_list = []
            tag_list.append(node)
            # set attribute(s)
            setattr(self, name + 's', tag_list)
            self._set_nodes.add(name + 's')
            if len(tag_list) == 1:
                setattr(self, name, tag_list[0])
                self._set_nodes.add(name)

    def __str__ (self):
        return '<{0}>'.format('Tree' if self.tag is None else self.tag)

    def __repr__ (self):
        tag = '' if self.tag is None else ': <{0}>'.format(self.tag)
        nodes = ', '.join(str(node) for node in self.nodes)
        return '<Tree{0}: ({1})>'.format(tag, nodes)

    def has_attr (self, attr):
        """Check whether an attribute is defined.

has_attr(attr) -> is_defined

Case-insensitive.  Returns False if this instance has no tag.

"""
        if self.tag is None:
            return False
        if attr.lower() not in self.attrs:
            return False
        return True

    def attr_match (self, attr, value):
        """Check whether an attribute of the element has some value.

attr_match(attr, value) -> is_a_match

Case-insensitive.  Returns False if this instance has no tag or the attribute
isn't defined.

"""
        if not self.has_attr(attr):
            return False
        return self.attrs[attr.lower()].lower() == value.lower()

    def prev_sibling (self):
        """Return the next sibling of this element.

If this element has no parent or no preceding element in its parent, returns
None.

"""
        if self.parent is None:
            return None
        index = self.parent.nodes.index(self) - 1
        while type(self.parent.nodes[index]) is not type(self):
            index -= 1
            if index < 0:
                return None
        return self.parent.nodes[index]

    def next_sibling (self):
        """Return the next sibling of this element.

If this element has no parent or no following element in its parent, returns
None.

"""
        if self.parent is None:
            return None
        index = self.parent.nodes.index(self) + 1
        try:
            while type(self.parent.nodes[index]) is not type(self):
                index += 1
        except IndexError:
            return None
        return self.parent.nodes[index]

    def get_textnodes (self, deep = True):
        """Return a list of text nodes in the tree.

get_textnodes (deep = True) -> HTMLTextNode_list

deep: search inside elements recursively; if False, return value is the same as
      self.textnodes.

Ordered as in HTML source.

"""
        result = []
        for node in self.nodes:
            if deep and type(node) is type(self):
                result += node.get_textnodes()
            elif type(node).__name__ == 'HTMLTextNode':
                result.append(node)
        return result

    def get_elements (self, tag = '*', deep = True):
        """Get a list of elements in the tree.

get_elements(tag = '*', deep = True) -> HTMLTree_list

tag: '*' to select any element, else a tag name.
deep: search inside elements recursively.

Ordered as in HTML source, parent before child.  Includes the tree itself if it
has a tag, first in the returned list.

"""
        # first add every tag
        result = []
        if self.tag is not None:
            result.append(self)
        for node in self.nodes:
            if type(node) is type(self):
                if deep:
                    result += node.get_elements(tag, deep)
                else:
                    result.append(node)
        # then remove unwanted tags
        if tag != '*':
            temp, result = result[:], []
            for node in temp:
                if node.tag == tag:
                    result.append(node)
        return result

    def source (self):
        """Get the original source string of this element."""
        return self._source[self._source_start:self._source_end]

    def out (self, comments = True, xhtml = False):
        """Return a string representation.

out(comments = True, xhtml = False) -> string

comments: whether to include HTML comments in the output.
xhtml: whether to use xhtml-style closing tags.

This compiles the tree into valid HTML, similar to the raw input (barring
comments if passed as False) if the input is valid and the tree has not been
edited.  Differences may include the character used around attribute values
and the order of attributes.

"""
        # opening tag
        if self.tag is None:
            s = ''
        else:
            attrs = ''
            if self.attrs:
                for attr, val in self.attrs.iteritems():
                    q = '\'' if '"' in val else '"'
                    attrs += ' {0}={1}{2}{1}'.format(attr, q, val)
            slash = ' /' if self.self_closing and xhtml else ''
            s = '<{0}{1}{2}>'.format(self.tag, attrs, slash)
        # child nodes
        print self.nodes
        for node in self.nodes:
            if type(node) is HTMLTree:
                s += node.out(comments, xhtml)
            else:
                s += node.out()
        # closing tag
        if self.tag is not None:
            s += '</{0}>'.format(self.tag)
        return s


    def selection (self, expr):
        """Return a Selection object for an expression.

selection(expr) -> element_list

A convenience function to apply a CSS-style selection expression to this tree
and return a list of matching elements.  See the Selection class for details on
what selector combinations can be used.

"""
        return Selection(self, expr).selection

    def set_tag (self, tag, attrs, self_closing = False):
        """Set the root tag for the tree.

set_tag(tag, attrs, self_closing = False)

tag: string tag name.
attrs: attribute dictionary.
self_closing: whether the tag self-closes; can only be True if the tag has no
              children.

"""
        self.tag = tag.lower()
        self.attrs = dict(((k.lower(), v) for k, v in attrs.iteritems()))
        self.self_closing = False if self.nodes else self_closing

    def append (self, node, *more_nodes):
        """Add one or more nodes to the end of the tree."""
        if type(node) not in (HTMLTextNode, HTMLDoctype, HTMLComment, HTMLTree):
            raise TypeError('node must be an HTML element')
        if type(node) is HTMLTree and not hasattr(node, 'tag'):
            raise ValueError('all child nodes must have a defined top-level tag')
        self.nodes.append(node)
        try:
            for node in more_nodes:
                self.append(node)
        except (TypeError, ValueError):
            self._set_attrs()
            raise
        self._set_attrs()

    def insert (self, index, node):
        """Insert a node into the tree.

insert(index, node)

index: the position to insert the node; integers out of range are handled like
       (by, even) list.insert.
node: the node to add.

"""
        if type(node) not in (HTMLTextNode, HTMLDoctype, HTMLComment, HTMLTree):
            raise TypeError('node must be an HTML element')
        if type(node) is HTMLTree and not hasattr(node, 'tag'):
            raise ValueError('all child nodes must have a defined top-level tag')
        try:
            self.nodes.insert(index, node)
        except TypeError:
            raise TypeError('index must be an integer')
        self._set_attrs()

    def remove (self, node, *more_nodes):
        """Delete one or more nodes from the tree.

Requires the node to remove or its index in HTMLTree.nodes.

"""
        if type(node) is int:
            try:
                self.nodes.pop(node)
            except IndexError:
                raise ValueError('no node exists at position {0}'.format(node))
        else:
            try:
                self.nodes.remove(node)
            except ValueError:
                raise ValueError('given node does not exist')
        try:
            for node in more_nodes:
                self.remove(node)
        except ValueError:
            self._set_attrs()
            raise
        self._set_attrs()

class Selection (object):
    """Select matching elements from in an HTMLTree instance.

Selection(tree, expr)

tree: a valid HTMLTree instance.
expr: a CSS-style selection.

Currently, all sensible CSS 2.1 selectors (including combinators) as defined in
the W3C specification are supported.  That is, certain pseudo-selectors are not
supported:
 - Those referring to pseudo-elements (:first-line, :first-letter), since the
resulting list must contain only elements in the original HTMLTree.
 - Those that depend on user interaction (:hover, :focus, :active), as they
   just don't make sense in this context.


    ATTRIBUTES

expr: the given expression with nice whitespace.
expr_split: the expression split by combinators.
expr_parse: the given expression in a fully parsed format (invalid/unrecognised
            selectors between combinators are represented by None).
selection: the resulting list of matching elements.

"""
    # TODO:
    # :nth-child(an+b|even|odd)
    # :nth-of-type
    # :nth-last-of-type
    # :last-child
    # :first-of-type
    # :last-of-type
    # :only-child
    # :only-of-type
    # :empty
    # :not
    # [attr^=val]
    # [attr$=val]
    # [attr*=val]

    def __init__ (self, tree, expr):
        # TODO: A ~ B
        try:
            expr = str(expr)
        except (TypeError, ValueError):
            raise TypeError('selector must be a string')
        # split comma-separate selectors
        temp = expr.split(',')
        if len(temp) > 1:
            self.__init__(tree, temp[0])
            for selector in temp[1:]:
                self.selection = set(self.selection).union(set(type(self)(tree, selector).selection))
            return
        # nice-ify whitespace
        expr = expr.strip().lower()
        expr = re.sub('\s+', ' ', expr)
        expr = re.sub(' ?(\+|>) ?', '\\1', expr)
        self.expr = expr
        # separate by ' ', '+', '>'
        selectors = []
        last = 0
        for i in xrange(len(expr)):
            if expr[i] in (' ', '+', '>'):
                if selectors:
                    selectors[-1] = (selectors[-1], expr[last:i])
                else:
                    selectors.append(expr[last:i])
                selectors.append(expr[i])
                last = i + 1
        if selectors:
            selectors[-1] = (selectors[-1], expr[last:])
        else:
            selectors = [expr]
        self.expr_split = selectors
        # construct selection
        self.expr_parsed = []
        for selector in selectors:
            if type(selector).__name__ == 'str':
                parsed = self._parse_simple_expr(selector)
                result = set(self._simple_select(tree, parsed))
            else:
                tree_mod, selector = selector
                self.expr_parsed.append(tree_mod)
                parsed = self._parse_simple_expr(selector)
                temp, result = result, set()
                # select starting from every tree in this level's selection
                for tree in temp:
                    deep = tree_mod != '>'
                    if tree_mod == '+':
                        tree = tree.next_sibling()
                        if tree is not None:
                            if self._simple_match(tree, parsed):
                                result.add(tree)
                    else:
                        result = result.union(set(self._simple_select(tree, parsed, deep)))
            self.expr_parsed.append(parsed)
        self.selection = list(result)

    def _parse_simple_expr (self, expr):
        if expr == '':
            return None
        # validate
        match = re.match('(\*|\w+)?((\[\w+((~|\|)?=(?P<quote>[\'"])[\w\-_]+'
                         '(?P=quote))?\])|(:first-(child|line|letter))|'
                         '\.[\w\-_]+|#[\w\-_]+)*', expr)
        if match is None or match.end() < len(expr):
            return None
        # split up
        split = []
        last = 0
        for i in xrange(len(expr)):
            if expr[i] in (':', '[', '.', '#'):
                split.append(expr[last:i])
                last = i
        split.append(expr[last:])
        if not split[0]:
            split[0] = '*'
        if split[0][0] in (':', '[', '.', '#'):
            split = ['*'] + split
        return split

    def _reduce_by_expr (self, expr, trees):
        split, result = expr, trees
        for expr in split[1:]:
            if not result:
                # nothing left to eliminate
                break
            rm = set()
            for element in result:
                if expr[0] == '.':
                    if element.has_attr('class'):
                        b = expr[1:] in (x.lower() for x in re.split('\\s+', element.attrs['class']))
                    else:
                        b = False
                elif expr[0] == '#':
                    b = element.attr_match('id', expr[1:])
                elif expr == ':first-child':
                    if element.parent is None:
                        b = True
                    else:
                        for e in element.parent.nodes:
                            if type(e) is type(element):
                                b = element is e
                                break
                elif expr[0] =='[':
                    if '=' in expr:
                        sep2 = expr.find('=')
                        sep1 = max(expr.find('~'), expr.find('|'))
                        if sep1 == -1:
                            sep1 = sep2
                        attr, mid, val = expr[1:sep1], expr[sep1:sep2], expr[sep2 + 2:-2]
                        if mid == '':
                            b = element.attr_match(attr, val)
                        elif mid == '|':
                            if element.has_attr(attr):
                                b = (element.attrs[attr].split('-')[0].lower() == val)
                            else:
                                b = False
                        elif mid == '~':
                            if element.has_attr(attr):
                                b = val in (x.lower() for x in re.split('\\s+', element.attrs[attr]))
                            else:
                                b = False
                    else:
                        b = element.has_attr(expr[1:-1])
                if not b:
                    rm.add(element)
            for element in rm:
                result.remove(element)
        return result

    def _simple_match (self, tree, expr):
        if expr is None:
            return False
        return bool(self._reduce_by_expr(expr, [tree]))

    def _simple_select (self, tree, expr, deep = True):
        if expr is None:
            return []
        # get elements that match the 'main' part of the selection (* or a tag name)
        result = set(tree.get_elements(expr[0], deep))
        # eliminate ones that don't match
        result = self._reduce_by_expr(expr, result)
        return result
