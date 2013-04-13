"""Fetching functions.

There are two functions here, built around PycURL, to make it quick and easy to
fetch one or many URLs.

Python version: 2.
Release: 4.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    FUNCTIONS

get
fetch_pages

    DATA

ff8: user-agent for Firefox 8.0.1 on Linux

"""

from os import sep as path_sep, makedirs
from os.path import exists as path_exists
from cStringIO import StringIO

import pycurl

ff8 = 'Mozilla/5.0 (X11; Linux i686; rv:8.0.1) Gecko/20100101 Firefox/8.0.1'
ff19 = 'Mozilla/5.0 (X11; Linux x86_64; rv:19.0) Gecko/20100101 Firefox/19.0'

def get (url, post = None, use = None, save = None, throttle = None,
         ua = ff19, store = None, httppost = False, info = False):
    """Fetch a single page using cURL.

get(url[, post][, use][, save][, throttle], ua = fetch.ff19[, store],
    httppost = False, info = False) -> page

post: already-urlencoded POST data.
use: a cookie file to load.
save: file to store cookies in.
throttle: maximum download speed in Bps.
ua: user-agent string.
store: file to store data in.
httppost: pass True to use PycURL HTTPPOST option; post is passed to this, so
          don't urlencode it.  See curl_formadd: dict values may be
          (option, data).
info: instead of just the data, return (data, response_code, effective_url),
      or just the latter two if saving to file.

"""
    f = StringIO() if store is None else open(store, 'wb')
    c = pycurl.Curl()
    # compulsory settings
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.WRITEFUNCTION, f.write)
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(pycurl.MAXREDIRS, 5)
    c.setopt(pycurl.CONNECTTIMEOUT, 30)
    c.setopt(pycurl.TIMEOUT, 60)
    c.setopt(pycurl.NOSIGNAL, 1)
    c.setopt(pycurl.USERAGENT, ua)
    # optional settings
    if post:
        if httppost:
            c.setopt(pycurl.HTTPPOST, post)
        else:
            c.setopt(pycurl.POSTFIELDS, post)
    if use:
        c.setopt(pycurl.COOKIEFILE, use)
    if save:
        c.setopt(pycurl.COOKIEJAR, save)
    if throttle:
        c.setopt(pycurl.MAX_RECV_SPEED_LARGE, throttle)
    # fetch
    result = []
    try:
        c.perform()
    except pycurl.error:
        if store is None:
            result.append('')
    else:
        if store is None:
            result.append(f.getvalue())
            f.close()
    if info:
        result.append(c.getinfo(pycurl.RESPONSE_CODE))
        result.append(c.getinfo(pycurl.EFFECTIVE_URL))
    c.close()
    if len(result) == 0:
        return
    elif len(result) == 1:
        return result[0]
    else:
        return tuple(result)

def fetch_pages (urls, cons = 10, retries = 2, folder = None,
                       files = None, names = None, err_names = None,
                       func = None, failed_msg = 'invalid content',
                       cookie = None, throttle = False):
    """Fetch multiple pages quickly.

fetch_pages(urls, cons = 10, retries = 2
[, folder, files = [str(id(url)) for url in urls]],
names = urls, err_names = names[, func], failed_msg = 'invalid content'
[, cookie][, throttle]) -> (failed, result)

urls: list of URLs to fetch.
cons: number of simultaneous connections to use.
retries: number of times to retry pages that failed before giving up.
folder: the folder to save the pages in (gets created if doesn't exist); if
        this argument is not given, the pages' content is returned in a list.
files: list of filenames to save downloads as.
names: list of names to print out for each URL.
err_names: list of names to print out for each URL that fails.
func: a function to perform on each page before storing it; useful to save disk
      space (or memory), or do the processing while we're still fetching stuff
to save time later; should return False to re-fetch the page.
failed_msg: message to give when func returns False.
cookie: a cookie file to load and use for every page fetch.
throttle: maximum download speed in Bps.

failed: list of URLs that failed, even after all retries were exhausted.
result: the pages - either a list of filenames or a list of strings of page
        content; both preserve the given order in the urls argument.

Also sets user-agent to Firefox 4 on Linux to avoid rejection as a bot.

"""
    # names
    if names is None:
        names = urls
    if err_names is None:
        err_names = names
    temp, names = names, {}
    for i in xrange(len(urls)):
        names[urls[i]] = temp[i]
    temp, err_names = err_names, {}
    for i in xrange(len(urls)):
        err_names[urls[i]] = temp[i]
    # set up storage
    retries = max(0, retries)
    queue = [(url, retries) for url in set(urls)]
    if folder is None:
        data = dict(((x[0], None) for x in queue))
    else:
        if folder[-1] != path_sep:
            folder += path_sep
        if not path_exists(folder):
            makedirs(folder)
        data = {}
        for x in queue:
            if files is None:
                data[x[0]] = str(id(x[0]))
            else:
                data[x[0]] = files[urls.index(x[0])]
    cons = max(min(cons, len(queue)), 1)

    # initialise cURL stuff
    m = pycurl.CurlMulti()
    m.handles = []
    for i in xrange(cons):
        c = pycurl.Curl()
        c.out = None
        c.setopt(pycurl.FOLLOWLOCATION, 1)
        c.setopt(pycurl.MAXREDIRS, 5)
        c.setopt(pycurl.CONNECTTIMEOUT, 30)
        c.setopt(pycurl.TIMEOUT, 60)
        c.setopt(pycurl.NOSIGNAL, 1)
        c.setopt(pycurl.USERAGENT, ff8)
        if cookie is not None:
            c.setopt(pycurl.COOKIEFILE, cookie)
        if throttle is not None:
            c.setopt(pycurl.MAX_RECV_SPEED_LARGE, throttle/cons)
        m.handles.append(c)
    free = m.handles[:]
    failed = []
    left = len(queue)

    # fetch
    while left:
        # assign URLs to free connections
        while queue and free:
            url, retries = queue.pop()
            c = free.pop()
            if folder is None:
                c.out = StringIO()
            else:
                c.out = open(folder + data[url], 'wb')
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.WRITEFUNCTION, c.out.write)
            m.add_handle(c)
            c.url, c.retries = url, retries
        while True:
            ret, num_handles = m.perform()
            if ret != pycurl.E_CALL_MULTI_PERFORM:
                break
        # sort out finished downloads
        while True:
            num_q, done, err = m.info_read()
            for c in done:
                has_err = False
                if folder is None:
                    p = c.out.getvalue()
                    s = p if func is None else func(p)
                    if s is False:
                        has_err = True
                    else:
                        data[c.url] = s
                c.out.close()
                if folder is not None and func is not None:
                    with open(folder + data[c.url]) as f:
                        page = f.read()
                    page = func(page)
                    if page is False:
                        has_err = True
                    else:
                        with open(folder + data[c.url], 'w') as f:
                            f.write(page)
                if has_err:
                    err.append((c, 0, failed_msg))
                else:
                    print names[c.url]
                    left -= 1
                    c.out = None
                    m.remove_handle(c)
                    free.append(c)
            for c, n, msg in err:
                err_str = '{0}: FAILED: {1} ({2} retr{3} left)'
                suffix = 'y' if c.retries == 1 else 'ies'
                print err_str.format(err_names[c.url], msg, c.retries, suffix)
                if c.retries:
                    # try again if still have some retries left
                    queue.append((c.url, c.retries - 1))
                else:
                    failed.append(c.url)
                    left -= 1
                c.out.close()
                c.out = None
                m.remove_handle(c)
                free.append(c)
            if num_q == 0:
                break
        # idle for a bit
        m.select(1.)

    # clean up
    for c in m.handles:
        if c.out is not None:
            c.out.close()
            c.out = None
        c.close()
    m.close()

    # compile results
    result = []
    for url in urls:
        result.append(data[url])
    return failed, result
