"""A MediaWiki browser and editor.

These are functions to fetch and process data from, and make changes to,
MediaWiki installations.  Everything is done through the Wiki class.

Python version: 2.
Release 2.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

"""

# TODO:
# METHODS:
# uploader: original uploader of file
# cats_on_page: categories a page is in ('#catlinks a'[1:])
# do_multi (pass multiple actions of edit, move, delete, each as one arg with a list of separate *args, **kwargs, then use fetch_pages; also pass a function to act on pages if editing (string in, string out))
# recent changes
# delete cookies (current/all in this instance/all in folder)
# if urlencode fails, use multipart, and also for too-long POST and files

from os import sep as path_sep, makedirs, remove
from os.path import abspath, basename, expanduser, exists as path_exists
from shutil import rmtree
from time import strftime, gmtime
from re import compile, sub
from urllib import urlencode
from urllib2 import URLError
from xml.etree.ElementTree import XML

from pycurl import FORM_FILE
from fetch import get, fetch_pages
from htmlparse import HTMLTree

class Wiki (object):
    """Create a wiki instance.

Wiki(url[, user, pwd][, trust_me])

url: the base URL of the wiki, after which 'index.php' would normally come.
user/pwd: credentials to log in straight away.
trust_me: set to True to skip checking if wiki can be reached and is valid.

All functions use the active user, specified through Wiki.set_active.  Logging
in successfully when no active user is set sets the logged in user to the
active user.  Once a username has logged in, it is found in Wiki.logged_in,
and can be set as the active user.

        METHODS

    UTILITIES

page [DEL]
fetch [DEL]
fetch_tree [DEL]
api_get [-> fetch]
get_tree
login
logout
is_logged_in
set_active

    READ

source
exists
list_pages
links_to [FIX]
file_url [FIX]
save_files [FIX]
pages_in_cat [FIX]

    WRITE

edit [FIX]
move
move_cat [FIX]
delete [FIX]
upload
transfer_files

    ATTRIBUTES

logged_in: list of logged in users
active: the active user, or None
folder: the folder all cookies are stored in
api: API URL

"""

    def __init__ (self, url, user = None, pwd = None, trust_me = False):
        self.url = self._fix_url(url)
        # initialise some stuff
        self.api = self.url + '/api.php'
        self.logged_in = []
        self.active = None
        self.folder = expanduser('~') + path_sep + '.mwbot' + path_sep
        if not path_exists(self.folder):
            makedirs(self.folder)
        # check wiki exists if need to
        if not trust_me:
            if not self.api_get('query').endswith('<api />'):
                raise ValueError('can\'t access wiki API at \'{0}\''.format(self.api))
        # log in if asked
        if user is not None:
            if self.login(user, pwd):
                self.active = self.logged_in[0]
            else:
                print 'Warning: login details incorrect'

    def _fix_url (self, url):
        # remove protocol prefixes and trailing slash
        try:
            url = url.lower()
        except TypeError:
            raise TypeError('url must be a string')
        if not url:
            raise ValueError('invalid url')
        while url[-1] == '/':
            url = url[:-1]
        dot = url.find('.')
        while '/' in url[:dot]:
            url = url[url.find('/') + 1:]
            dot = url.find('.')
        return url

    def _cookie (self, user = None):
        # construct cookie filepath
        if user is None:
            user = self.active
        if user is None:
            raise Exception('no user specified and no active user exists')
        return '%scookie_%s_%s' % (self.folder, self.url.encode('hex'), user)

    def page (self, page, GET = {}):
        """Construct the full URL for a page.

Wiki.page(page, GET = {}) -> full_url

Uses Monobook.

page: article name.
GET: dict of HTTP_GET parameters.

"""
        return 'http://%s/index.php?useskin=monobook&redirect=no&title=%s&%s' % (self.url, page.replace(' ', '_').replace('&', '%26'), urlencode(GET))

    def fetch (self, page, GET = {}, POST = None, store = None):
        """Fetch a page as a logged in user.

Wiki.fetch(page, GET = {}, POST[, store]) -> page_content

page: article name.
GET: dict of HTTP_GET parameters.
POST: dict of HTTP_POST parameters.
store: store the returned page in this file.

"""
        if POST is not None:
            POST = urlencode(POST)
        use = None if self.active is None else self._cookie()
        return get(self.page(page, GET), POST, use, store = store)
        # TODO: if not logged in on page: self.logged_in.pop(self.active); self.active = None; print 'Warning: the active user (\'%s\') is no longer logged in' % self.active; then try to log in, if success, redo, if fails, raise Exception

    def fetch_tree (self, *args):
        """Return the HTMLTree of a page as a logged in user.

See Wiki.fetch for details.

"""
        return HTMLTree(self.fetch(*args))

    def api_get (self, action, args = {}, req = 'get', user = None,
                 format = 'xml'):
        """Make API request.

Wiki.api_get(action, args = {}, req = 'get'[, user], format = 'xml') -> page

action: 'action' parameter.
args: arguments to send to the API.
req: 'get', 'post' or 'httppost'.
user: user to perform the request as (defaults to the active user); if there is
      no active user, no cookie is used (anonymous request).
format: 'format' parameter.

"""
        try:
            c = self._cookie(user)
        except Exception:
            c = None
        if req == 'get':
            GET = args
            POST = {}
        else: # req == *'post':
            GET = {}
            POST = args
        GET['action'] = action
        GET['format'] = format
        url = 'http://{0}?{1}'.format(self.api, urlencode(GET))
        httppost = req == 'httppost'
        if httppost:
            POST = [(str(k), v if isinstance(v, (list, tuple)) else str(v))
                    for k, v in POST.iteritems()]
        else:
            POST = urlencode(POST)
        data = get(url, POST, c, c, httppost = httppost, info = True)
        page, code, real_url = data
        if real_url != url:
            # got redirected: POST might not work properly, so fix self.url
            base = 'http://' + self.url
            if real_url.endswith(url[len(base):]):
                self.url = self._fix_url(real_url[:len(base) - len(url)])
                self.api = self.url + '/api.php'
        return page

    def get_tree (self, *args, **kwargs):
        """Return the ElementTree of an API query.

See Wiki.api_get for argument details.

"""
        return XML(self.api_get(*args, **kwargs))

    def login (self, user, pwd, token = None, api = False):
        """Log in.

Wiki.login(user, pwd) -> login_successful.

Adds users successfully logged in to Wiki.logged_in and stores a cookie at
~/.mwbot/cookie_user.

"""
        if user in self.logged_in:
            return True
        args = {'lgname': user, 'lgpassword': pwd}
        if token is not None:
            args['lgtoken'] = token
        page = self.get_tree('login', args, 'post', user)
        login = page[0]
        result = login.attrib['result']
        if result == 'NeedToken':
            if token is None:
                print 'got token: ' + login.attrib['token']
                return self.login(user, pwd, login.attrib['token'])
            else:
                return False
        elif result == 'Success':
            self.logged_in.append(user)
            if self.active is None:
                self.active = user
            return True
        else:
            return False

    def logout (self, user = None):
        """Log a user out.

Wiki.logout(user = Wiki.active)

"""
        if user is None:
            user = self.active
        if user is None:
            raise Exception('no user specified and no active user exists')
        if user == self.active:
            self.set_active(None)
        try:
            self.logged_in.remove(user)
        except ValueError:
            pass

    def is_logged_in (self, user = None):
        """Check if a user is still logged in.

Wiki.is_logged_in(user = Wiki.active) -> is_logged_in

"""
        if user is None:
            user = self.active
        if user is None:
            raise Exception('no user specified and no active user exists')
        return 'anon' not in self.get_tree('query', {'meta': 'userinfo'})[0][0]

    def set_active (self, user):
        """Set the active user.

Wiki.set_active(user)

Pass user = None to be anonymous.

"""
        if user in self.logged_in or user is None:
            self.active = user
        else:
            raise ValueError('user \'{0}\' is not logged in'.format(user))

    def source (self, page):
        """Fetch the source of a page.

Wiki.source(page) -> page_source

Raises ValueError if the page doesn't exist.

"""
        if not page:
            raise ValueError('page name must not be zero-length')
        tree = self.get_tree('query', {'prop': 'revisions', 'rvprop': 'content', 'titles': page})
        tree_page = tree[0].find('pages')[0]
        if 'missing' in tree_page.attrib:
            raise ValueError('page \'{0}\' doesn\'t seem to exist'.format(page))
        else:
            return tree_page[0][0].text

    def exists (self, page):
        """Check whether a page exists."""
        if not page:
            return False
        tree = self.get_tree('query', {'prop': 'info', 'titles': page})
        attrs = tree[0].find('pages')[0].attrib
        return 'missing' not in attrs and 'invalid' not in attrs

    def list_pages (self, ns = None, start = '', lim = None):
        """List pages given by Special:Allpages.

Wiki.list_pages([ns]) -> page_list

ns: namespace, either a number (faster) or string.  If not given, all
    namespaces are checked.

"""
        # TODO: ns = None gets all namespaces
        # TODO: allow string ns (look up)
        pages = []
        while True:
            got = len(pages)
            # get pages up to given limit or a bot maximum, if allowed
            get = lim - got if lim is not None else 500
            if get == 0:
                break
            args = {'list': 'allpages', 'apnamespace': ns, 'aplimit': get}
            if pages:
                # already got some: continue from last
                # strip ns first
                page = pages[-1]
                args['apfrom'] = page[page.find(':') + 1:]
            elif start:
                # use given start if any
                args['apfrom'] = start
            tree = self.get_tree('query', args)
            q = tree.find('query')
            if q is None:
                return []
            new = [page.attrib['title'] for page in q.find('allpages')]
            if pages:
                # continued from last: ignore that one
                pages += new[1:]
            else:
                pages += new
            if tree.find('query-continue') is None:
                # no more to get
                break
        return pages

    def links_to (self, page, trans = True, links = True, redirs = True):
        """Find what pages link to a page.

Wiki.links_to(page, trans = True, links = true, redir = True) -> page_list

page: article name.
trans: include transclusions.
links: include links.
redir: include redirects.

"""
        if not page:
            return []
        GET = {'limit': '500'}
        for x in ('trans', 'links', 'redirs'):
            GET['hide%s' % x] = '0' if locals()[x] else '1'
        print 'fetching Special:WhatLinksHere...'
        tree = self.fetch_tree('Special:WhatLinksHere/%s' % page, GET)
        links = tree.selection('#mw-whatlinkshere-list > li > a')
        # check if there are more pages
        n = 2
        while True:
            next = tree.selection('p + a')
            if next:
                do = False
                if 'next' in next[0].source():
                    do = 1
                elif len(next) > 1:
                    if 'next' in next[1].source():
                        do = 2
                if do:
                    # more pages; follow link
                    next = next[do - 1].attrs['href']
                    next = next[next.find('&amp;from=') + 10:]
                    if '&' in next:
                        next = next[:next.find('&')]
                    print 'page %s...' %n
                    GET['from'] = next
                    tree = self.fetch_tree('Special:WhatLinksHere/%s' % page, GET)
                    links += tree.selection('#mw-whatlinkshere-list > li > a')
                    n += 1
                else:
                    break
            else:
                break
        return [link.source() for link in links]

    def file_url (self, page):
        """Get uploaded file URL."""
        # Image: for compatibility with older MW versions
        tree = self.fetch_tree('Image:' + page)
        try:
            link = tree.selection('.filehistory .filehistory-selected a')[0]
        except IndexError:
            raise ValueError('File:\'%s\' doesn\'t seem to exist' % page)
        else:
            return link.attrs['href']

    def save_files (self, *pages, **kwargs):
        """Download files.

Wiki.save_files(*pages, dir = Wiki.folder)

dir: the folder to store the files in.  This is a keyword-only argument.

"""
        d = kwargs.get('dir')
        if d is None:
            d = self.folder
        else:
            d = expanduser(d)
        d = abspath(d)
        if not path_exists(d):
            makedirs(d)
        # get URLs
        urls = []
        failed = []
        good_pages = []
        for page in pages:
            try:
                url = self.file_url(page)
            except ValueError:
                failed.append(page)
            else:
                good_pages.append(page)
                urls.append(url)
        more_failed = fetch_pages(urls, folder = d, files = good_pages, names = good_pages)[0]
        # combine failed lists
        failed += [good_pages[urls.index(url)] for url in more_failed]
        return tuple(set(failed))

    def _fix_cat (self, cat):
        # remove prefix if exists and gives proper caps
        if ':' in cat.lower():
            cat = cat[cat.lower().find(':') + 1:]
        return cat[0].upper() + cat[1:]

    def pages_in_cat (self, cat, cascade = False):
        """Return a list of the pages in the given category.

Wiki.pages_in_cat(cat, cascade = False) -> page_list

cat: the category to look in.
cascade: look in subcategories too.

"""
        cat = self._fix_cat(cat)
        # get all category pages
        print 'fetching Category:%s...' % cat
        pages = [self.fetch_tree('Category:' + cat)]
        page_links = pages[-1].selection('.pagingLinks')
        if page_links:
            from_page = page_links[0].spans[1]._a.attrs['href']
            from_page = from_page[from_page.find('&amp;from=') + 10:]
            n = 2
            while True:
                print '\tpage %s...' % n
                pages.append(self.fetch_tree('Category:' + cat, {'from': from_page}))
                page_links = pages[-1].selection('.pagingLinks')
                a = page_links[0].selection('a')[0].source()
                if 'next' in a:
                    from_page = page_links[0].spans[1]._a.attrs['href']
                    from_page = from_page[from_page.find('&amp;from=') + 10:]
                else:
                    break
                n += 1
        # compile subcategory/page lists
        # subcategories
        sub = [a.source() for a in pages[0].selection('#mw-subcategories a')]
        result = set(('Category:' + cat for cat in sub))
        # files in a gallery
        media = (page.selection('#mw-category-media .gallerytext a') for page in pages)
        for page in media:
            result = result.union((a.attrs['title'] for a in page))
        # normal pages
        pages = (page.selection('#mw-pages a') for page in pages)
        for page in pages:
            result = result.union((a.source() for a in page))
        if cascade:
            # go through subcategories
            for cat in sub:
                result = result.union(self.pages_in_cat(cat, cascade))
        return list(result)

    def edit (self, page, content, summary = '', minor = False):
        """Edit a page.

Wiki.edit(page, content[, summary], minor = False)

"""
        #tree = self.get_tree('query', {'titles': '|'.join(names), 'prop': 'info', 'intoken': 'edit'})
        #change = dict((page.attrib['to'], page.attrib['from']) for page in tree[0][0])
        #for page in tree:
        #    title = page.attrib['title']
        #    title = change.get(title, title)
        #    token = page.attrib['edittoken']

        print 'getting form parameters...'
        tree = self.fetch_tree(page, {'action': 'edit'})
        # content might be a function to perform on the source
        try:
            content = content(self.source(tree))
        except TypeError:
            pass
        # construct POST
        try:
            token = tree.selection('#editform [name="wpEditToken"]')[0].attrs['value']
        except IndexError:
            raise Exception('insufficient permissions to edit page')
        edittime = strftime('%Y%m%d%H%M%S', gmtime())
        minor = ('0', '1')[minor]
        # edit
        print 'editing \'%s\'...' % page
        tree = self.fetch_tree(page, {'action': 'submit'}, {'wpTextbox1': content, 'wpSummary': summary, 'wpSave': '1', 'wpSection': '', 'wpStarttime': edittime, 'wpEdittime': edittime, 'wpEditToken': token, 'wpMinorEdit': minor})
        if tree.selection('#editform'):
            raise Exception('something failed')
        else:
            print 'success!'

    def move (self, page, to, reason = '', leave_redirect = True, move_talk = True):
        """Move a page.

Wiki.move(page, to[, reason], leave_redirect = True, move_talk = True)

page: the page to move.
to: the new name of the page.
reason: a reason for the move.
leave_redirect: leave behind a redirect.
move_talk: also move talk page.

"""
        if page == to:
            print 'no change in name; page not moved'
            return
        # get token
        tree = self.get_tree('query', {'prop': 'info', 'intoken': 'move', 'titles': page})
        token = tree.find('query').find('pages').find('page').attrib['movetoken']
        # perform move
        args = {'from': page, 'to': to, 'token': token, 'reason': reason, 'ignorewarnings': 1}
        if move_talk:
            args['movetalk'] = ''
        if not leave_redirect:
            args['noredirect'] = ''
        tree = self.get_tree('move', args, 'post')
        if not leave_redirect and 'redirectcreated' in tree.find('move').attrib:
            print 'redirect created: might need to delete'
        # TODO: check for errors <error code="..." info="...">

    def move_cat (self, cat, to, reason = '', overwrite_if_exists = False):
        """Move a category and recategorise all pages in it.

Wiki.move_cat(cat, to[, reason], overwrite_if_exists = False)

cat: the category to move.
to: the target category.
reason: a reason for the move.
overwrite_if_exists: if the target category exists, whether to edit it with
                     the source of cat and delete cat.  Otherwise, only the
                     category of the pages in cat is changed.

"""
        cat, to = self._fix_cat(cat), self._fix_cat(to)

        def callback (match):
            s = self._temp[match.start():match.end()]
            if '|' in s:
                return '[[Category:%s|%s]]' % (to, s[s.find('|') + 1:-2])
            else:
                return '[[Category:%s]]' % to

        pattern = compile(r'(?i)\[\[category *: *%s(\|.*)?\]\]' % cat)
        summary = 'changing category from \'%s\' to \'%s\'' % (cat, to) + ' (%s)' % reason if reason else ''
        pages = self.pages_in_cat(cat)
        for page in pages:
            self._temp = self.source(page)
            self.edit(page, sub(pattern, callback, self._temp), summary, True)
        del self._temp
        # move category
        if not overwrite_if_exists:
            if self.exists('Category:' + to):
                self.delete('Category:' + cat, 'moving to \'%s\' without overwriting' + ' (%s)' % reason if reason else '')
                return
        if self.exists('Category:' + cat):
            # TODO: if fails, try to edit new cat with old cat's contents then delete old one
            self.move('Category:' + cat, 'Category:' + to, reason, False)

    def delete (self, page, reason = ''):
        """Delete a page.

Wiki.delete(page[, reason])

page: the page to delete.
reason: a reason for the deletion.

"""
        print 'getting form parameters...'
        tree = self.fetch_tree(page, {'action': 'delete'})
        if tree.selection('h1')[0].source() == 'Internal error':
            raise Exception('got Internal Error: the page may not exist')
        try:
            token = tree.selection('#deleteconfirm [name="wpEditToken"]')[0].attrs['value']
        except IndexError:
            raise Exception('insufficient permissions to delete page')
        print 'deleting \'%s\'...' % page
        tree = self.fetch_tree(page, {'action': 'delete', 'useskin': 'monobook'}, {'wpReason': reason, 'wpEditToken': token})
        if tree.selection('.permissions-errors'):
            raise Exception('insufficient permissions to delete page')
        elif tree.selection('h1')[0].source() != 'Action complete':
            raise Exception('something failed')
        else:
            print 'success!'

    def upload (self, fn, name = None, desc = '', destructive = True):
        """Upload a file.

Wiki.upload(fn[, name], desc = '')

fn: file path.
name: name to save the file as at the wiki (without the 'File:'); defaults to
      the file's local name.
desc: description (full page content).
destructive: ignore any warnings.

"""
        fn = expanduser(fn)
        if name is None:
            name = basename(fn)
        # get token
        tree = self.get_tree('query', {'prop': 'info', 'intoken': 'edit', 'titles': 'File:' + name})
        token = tree.find('query').find('pages').find('page').attrib['edittoken']
        # perform upload
        args = {'filename': name, 'file': (FORM_FILE, fn), 'text': desc, 'token': token}
        if destructive:
            args['ignorewarnings'] = 1
        tree = self.api_get('upload', args, 'httppost')
        # TODO: check for errors/warnings

    def transfer_files (self, target, *pages, **kwargs):
        """Move files and their descriptions from one wiki to another.

Wiki.transfer_files(target, *pages, destructive = True) -> failed_pages

target: a Wiki instance or tuple of Wiki constructor arguments to create a new
        instance.
pages: files' page names on this wiki (without namespace).
destructive: ignore any warnings (otherwise add that image to the failed list).
             This is a keyword-only argument.

failed_pages: list of (page, error_msg) tuples.

"""
        if not pages:
            return []
        destructive = kwargs.get('destructive', True)
        if not isinstance(target, Wiki):
            print '\tcreating Wiki instance...'
            target = Wiki(*target)
        # add/replace namespaces
        pages_arg = '|'.join('Image:' + page[page.find(':') + 1:] for page in pages)
        print '\tgetting file details...'
        tree = self.get_tree('query', {'prop': 'revisions|imageinfo', 'rvprop': 'content', 'iiprop': 'url', 'titles': pages_arg}, 'post')
        pages = tree.find('query').find('pages')
        failed = []
        data = []
        print '\tgetting edit tokens...'
        tree = target.get_tree('query', {'prop': 'info', 'intoken': 'edit', 'titles': pages_arg})
        tokens = dict((page.attrib['title'], page.attrib['edittoken']) for page in tree[0].find('pages'))
        print '\ttransferring files...'
        for page in pages:
            if 'missing' in page.attrib:
                failed.append((page.attrib['title'], 'doesn\'t exist'))
            else:
                # upload
                name = page.attrib['title']
                token = tokens[name]
                # get rid of namespace
                name = name[name.find(':') + 1:]
                url = page.find('imageinfo')
                if url is None:
                    failed.append((name, 'doesn\'t exist'))
                    continue
                else:
                    url = url[0].attrib['url']
                content = page.find('revisions')[0].text
                if content is None:
                    content = ''
                args = {'filename': name, 'text': content.encode('utf-8'), 'url': url, 'token': token}
                if destructive:
                    args['ignorewarnings'] = 1
                try:
                    print name
                except UnicodeEncodeError:
                    failed.append((name, 'filename contains a strange character'))
                    continue
                tree = target.get_tree('upload', args, 'post')
                # TODO: check for errors
                if not destructive:
                    # TODO: check for warnings
                    pass
        return failed
