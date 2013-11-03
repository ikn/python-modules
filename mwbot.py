"""A MediaWiki browser and editor.

These are functions to fetch and process data from, and make changes to,
MediaWiki installations.  Everything is done through the Wiki class.

Python version: 2.
Release 3.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

"""

# TODO:
# uploader: original uploader of file
# recent changes
# delete cookies (current/all in this instance/all in folder)
# logout: actually call action=logout

from os import sep as path_sep, makedirs, remove
from os.path import abspath, basename, expanduser, exists as path_exists
from shutil import rmtree
from time import strftime, gmtime
from re import compile, sub
from urllib import urlencode
from urllib2 import URLError
import json

from pycurl import FORM_FILE
from fetch import get, fetch_pages

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

api_raw
api
login
logout
is_logged_in
set_active

    READ

source
exists
list_pages
file_url
cats_on_page

    WRITE

edit
move [FIX]
move_cat [FIX]
delete [FIX]
upload [FIX]
transfer_files [FIX]

    ATTRIBUTES

logged_in: list of logged in users
active: the active user, or None
folder: the folder all cookies are stored in
api_url: API URL

"""

    def __init__ (self, url, user = None, pwd = None, trust_me = False):
        self.url = self._fix_url(url)
        # initialise some stuff
        self.api_url = self.url + '/api.php'
        self.logged_in = []
        self.active = None
        self.folder = expanduser('~') + path_sep + '.mwbot' + path_sep
        if not path_exists(self.folder):
            makedirs(self.folder)
        # check wiki exists if need to
        if not trust_me:
            if self.api('query') != []:
                raise ValueError('can\'t access wiki API at \'{0}\''.format(self.api_url))
        # log in if asked
        if user is not None:
            if self.login(user, pwd):
                self.active = self.logged_in[0]

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

    def api_raw (self, action, args = {}, req = 'post', user = None,
                 format = 'json'):
        """Make API request.

Wiki.api_raw(action, args = {}, req = 'get'[, user], format = 'json') -> page

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
        url = 'http://{0}?{1}'.format(self.api_url, urlencode(GET))
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
                self.api_url = self.url + '/api.php'
        return page

    def api (self, *args, **kwargs):
        """Return the parsed JSON of an API query.

See Wiki.api_raw for argument details.

"""
        args = args[:5]
        if 'format' in kwargs:
            del kwargs['format']
        return json.loads(self.api_raw(*args, **kwargs))

    def login (self, user, pwd, token = None, api = False):
        """Log in.

Wiki.login(user, pwd) -> login_successful.

Adds users successfully logged in to Wiki.logged_in and stores a cookie at
~/.mwbot/cookie_user.

"""
        if user in self.logged_in:
            return True

        # check if already logged in through cookies
        res = self.api('query', {'meta': 'userinfo'}, user=user)
        if 'anon' not in res['query']['userinfo']:
            success = True
        else:
            args = {'lgname': user, 'lgpassword': pwd}
            if token is not None:
                args['lgtoken'] = token
            page = self.api('login', args, 'post', user)['login']
            if page['result'] == 'NeedToken':
                return token is None and self.login(user, pwd, page['token'])
            else:
                success = page['result'] == 'Success'

        if success:
            self.logged_in.append(user)
            if self.active is None:
                self.active = user
        return success

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
        page = self.api(
            'query', {'prop': 'revisions', 'rvprop': 'content', 'titles': page}
        )['query']['pages'].values()[0]
        if 'missing' in page:
            raise ValueError(
                'page \'{0}\' doesn\'t seem to exist'.format(page['title'])
            )
        elif 'invalid' in page:
            raise ValueError(
                'invalid page name: \'{0}\''.format(page['title'])
            )
        else:
            return page['revisions'][0]['*']

    def exists (self, page):
        """Check whether a page exists."""
        if not page:
            return False
        page = self.api(
            'query', {'prop': 'info', 'titles': page}
        )['query']['pages'].values()[0]
        return 'missing' not in page and 'invalid' not in page

    def list_pages (self, ns=None, start='', lim=None):
        """List pages given by Special:Allpages.

Wiki.list_pages([ns]) -> page_list

ns: namespace, either a number (faster) or string (TODO).  If not given, all
    namespaces are checked (TODO).

"""
        pages = []
        while True:
            # get pages up to given limit or a bot maximum, if allowed
            get = lim - len(pages) if lim is not None else 500
            if get == 0:
                break
            args = {'list': 'allpages', 'apnamespace': ns, 'aplimit': get}
            if pages:
                # already got some: continue from last
                args['apcontinue'] = \
                    res['query-continue']['allpages']['apcontinue']
            elif start:
                # use given start if any
                args['apfrom'] = start
            res = self.api('query', args)
            pages += [page['title'] for page in res['query']['allpages']]
            if 'query-continue' not in res:
                # no more to get
                break
        return pages

    def list_cat (self, cat, start='', lim=None):
        """List pages in a category.

Wiki.list_cat(cat) -> page_list

"""
        if not cat.lower().startswith('category:'):
            cat = 'Category:' + cat
        pages = []
        while True:
            # get pages up to given limit or a bot maximum, if allowed
            get = lim - len(pages) if lim is not None else 500
            if get == 0:
                break
            args = {'cmtitle': cat, 'list': 'categorymembers', 'cmlimit': get}
            if pages:
                # already got some: continue from last
                args['cmcontinue'] = \
                    res['query-continue']['categorymembers']['cmcontinue']
            elif start:
                # use given start if any
                args['cmfrom'] = start
            res = self.api('query', args)
            pages += [page['title']
                      for page in res['query']['categorymembers']]
            if 'query-continue' not in res:
                # no more to get
                break
        return pages

    def file_url (self, page, width=-1, height=-1):
        """Get uploaded file URL.

Wiki.file_url(page[, width])

width: width in pixels of the resulting image.

"""
        if any(page.lower().startswith(prefix)
               for prefix in ('file:', 'image:')):
            page = page[page.find(':') + 1:]
        # Image: for compatibility with older MW versions
        info = self.api(
            'query',
            {
                'prop': 'imageinfo', 'iiprop': 'url', 'iiurlwidth': width,
                'iiurlheight': height, 'titles': 'Image:' + page
            }
        )['query']['pages'].values()[0]['imageinfo'][0]
        url = None
        if 'thumburl' in info:
            url = info['thumburl']
        # thumburl can be an empty string
        if not url:
            url = info['url']
        return url

    def cats_on_page (self, page):
        """Get the categories that the given page is in.

Wiki.cats_in_page(page)

"""
        cats = []
        while True:
            if get == 0:
                break
            args = {'prop': 'categories', 'titles': page, 'cllimit': 500}
            if cats:
                # already got some: continue from last
                args['clcontinue'] = \
                    res['query-continue']['categories']['clcontinue']
            res = self.api('query', args)
            page_data = res['query']['pages'].values()[0]
            if 'missing' in page_data or 'invalid' in page_data:
                raise ValueError('no such page: \'{0}\''.format(page))
            cats += [cat['title'] for cat in page_data['categories']]
            if 'query-continue' not in res:
                # no more to get
                break
        return cats

    def edit (self, page, content, summary='', minor=False, mode='replace'):
        """Edit a page.

Wiki.edit(page, content[, summary], minor=False, mode='replace')

mode: 'replace', 'append' or 'prepend'

"""
        res = self.api(
            'query', {'prop': 'info', 'intoken': 'edit', 'titles': page}
        )
        token = res['query']['pages'].values()[0]['edittoken']
        if token == '+\\':
            raise Exception('invalid token returned (missing permissions?)')

        args = {'title': page, 'token': token, 'summary': summary, 'bot': 'y'}
        if minor:
            args['minor'] = 'y'
        args[{
            'replace': 'text', 'append': 'appendtext', 'prepend': 'prependtext'
        }[mode]] = content
        res = self.api('edit', args)
        if res['edit']['result'] != 'Success':
            raise Exception('edit failed')

    def move (self, page, to, reason='', leave_redirect=True, move_talk=True):
        """Move a page.

Wiki.move(page, to[, reason], leave_redirect = True, move_talk = True)

page: the page to move.
to: the new name of the page.
reason: a reason for the move.
leave_redirect: leave behind a redirect.
move_talk: also move talk page.

"""
        return NotImplemented
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
        return NotImplemented
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
        return NotImplemented
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
        return NotImplemented
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
        tree = self.api('upload', args, 'httppost')
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
        return NotImplemented
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
