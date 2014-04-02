"""Streaming RSS feed management.

This is an early release, and is buggy, undocumented and lacking in features.

Python version: 3.
Release: 2.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

"""

"""
TODO:
    feed: support optional attrs; __*item__() with validation
    add items to a feed
        set feed pubDate, lastBuildDate
        full attr support
            validate (error on unknown)
            source, enclosure, category aren't text
        expiry options: remove old items by age/cutoff date/number of items
            can return removed items/store in another file/file object
    custom temp dir
    support file obj instead of filename, somehow
"""

import time
import os
import tempfile
from uuid import uuid4 as uuid
from xml.etree import ElementTree as ET
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesImpl as Attrs

FEED_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S %Z'
FEED_DEFAULTS = {'docs': 'http://blogs.law.harvard.edu/tech/rss'}


def _prep_item (item):
    item = dict(item)
    if 'title' not in item and 'description' not in item:
        raise ValueError('feed item must have title or description')
    date = item['pubDate'] if 'pubDate' in item else time.localtime()
    if isinstance(date, time.struct_time):
        date = time.strftime(FEED_DATE_FORMAT, date)
    if 'guid' not in item:
        item['guid'] = uuid().hex
    item.setdefault('pubDate', date)
    return item


class Feed (dict):
    """RSS feed, supporting the very basics of RSS 2.0.

f: filename to read from/write to.
title: feed title.
link: feed website URL.
desc: feed description.

This is a dict of feed attributes ('title', 'link', etc.).

    ATTRIBUTES

f: as given.

"""

    """Feed attributes supported by this implementation."""
    SUPPORTED_ATTRS = ('title', 'link', 'desc')

    def __init__ (self, f, title, link, desc):
        dict.__init__(self)
        self.update({'title': title, 'link': link, 'desc': desc})
        self.f = f
        self.create()

    def _read (self):
        try:
            i = ET.iterparse(self.f, ('start', 'end'))
        except FileNotFoundError:
            self._create()
            i = ET.iterparse(self.f, ('start', 'end'))
        return i

    def feed_items (self):
        """Read items from the feed.

This is a generator, and each item is a dict as taken by Feed.add.

"""
        i = self._read()
        parents = []
        for event, elem in i:
            if elem.tag == 'item' and parents and parents[-1].tag == 'channel':
                # feed item
                if event == 'end':
                    yield {child.tag: child.text for child in elem}
                elem.clear()
            # track parent elements
            elif event == 'start':
                parents.append(elem)
            else: # event == 'end'
                if not parents or parents[-1] is not elem:
                    print([p.tag for p in parents], elem.tag)
                    raise ValueError('feed XML is malformed')
                parents.pop()
                # will be cleared as a parent

            # clear all parents of the current element
            # need to do this to ensure memory usage doesn't increase
            for p in parents:
                p.clear()

    def _create (self):
        with open(self.f, 'w') as f:
            FeedWriter(f, self).end()

    def create (self, overwrite=False):
        """Write an empty feed to disk.

This writes general feed attributes without any items to the file specified by
Feed.f.

"""
        if (overwrite or not isinstance(self.f, str) or
            not os.path.isfile(self.f)):
            self._create()

    def add (self, *items):
        """Add any number of items to the feed on disk.

items: feed items, each a dict of feed item elements with string values;
       'title' and 'description' are required.  'pubDate' may be a
       time.struct_time, and the current local time is used if it is not
       specified.  If 'guid' is not specified, and random UUID is used.
       Elements requiring sub-elements are not supported.

This method writes the new feed to a temporary file then replaces the original
file with it.

"""
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.f),
                                            text=True)
        try:
            tmp_f = os.fdopen(tmp_fd, 'w')
            feed = FeedWriter(tmp_f, self)

            for item in items:
                feed.add(_prep_item(item))
            for item in self.feed_items():
                feed.add(item)

            feed.end()
            tmp_f.close()
            os.rename(tmp_path, self.f)
        finally:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass


class FeedWriter:
    """Write an RSS feed to disk, one item at a time.

f: filename to write to.
attrs: dict of feed attributes.

"""

    def __init__ (self, f, attrs):
        self._ended = False
        self._feed = feed = XMLGenerator(f, 'utf-8')
        feed.startDocument()
        feed.startElement('rss', Attrs({'version': '2.0'}))
        feed.startElement('channel', Attrs({}))
        self._add_elems(attrs)

    def _add_elems (self, elems):
        feed = self._feed
        for tag, text in elems.items():
            feed.startElement(tag, Attrs({}))
            feed.characters(text)
            feed.endElement(tag)

    def add (self, item):
        """Add an item to the feed (dict of elements with string values)."""
        if self._ended:
            raise Exception('tried to add item to closed FeedWriter')
        self._feed.startElement('item', Attrs({}))
        self._add_elems(item)
        self._feed.endElement('item')

    def end (self):
        """Write the end of the feed."""
        if not self._ended:
            self._ended = True
            self._feed.endElement('channel')
            self._feed.endElement('rss')
            self._feed.endDocument()
