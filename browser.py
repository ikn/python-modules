"""A (very) simple web browser.

This provides a browser that is not intended to be controlled by the user: its
intended use is to display HTML documents.

WebKit is used for rendering, so CSS and JavaScript are fully supported.
Everything is done through the Browser class, and multiple windows and tabs
can be manipulated through a single instance.

Python version: 2.
Release: 1.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    CLASSES

BrowserTab
BrowserWindow
Browser

"""

import gtk
from webkit import WebView

# TODO:
# - optional close button on tabs (set in Browser (default False), tab checks that)
# - set tab name to page title, or window name if only one tab; else window name is set in Browser (defaults to 'Browser')

class BrowserTab:
    def load (self, url, content = None, mime_type = 'text/html', encoding = 'UTF-8'):
        if not self._loading:
            self.view.disconnect(self._nav_cb)
        self._loading = True
        if content is None:
            self.view.open(url)
        else:
            self.view.load_string(content, mime_type, encoding, url)

    def ignore_nav (self, from_load = True, *args):
        self._loading = False
        self._nav_cb = self.view.connect('navigation-policy-decision-requested', lambda *args: True)
        return False

    def __init__ (self, window):
        self.window = window
        self.label = gtk.Label('Blank')
        self.label.show()
        self.widget = gtk.ScrolledWindow()
        self.widget.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = WebView()
        self.widget.add(self.view)
        self.view.get_settings().set_property('auto-shrink-images', False)
        self.ignore_nav(False)
        self.view.connect('load-finished', self.ignore_nav)
        self.widget.show_all()

class BrowserWindow:
    def update_display (self):
        self.notebook.set_show_tabs(len(self.tabs) > 1)

    def new_tab (self, pos = None):
        if type(pos) is not int or pos < 0 or pos > len(self.tabs):
            pos = len(self.tabs)
        tab = BrowserTab(self)
        self.tabs.insert(pos, tab)
        self.notebook.insert_page(tab.widget, tab.label, pos)
        self.update_display()
        return tab

    def rm_tab (self, pos = None):
        if type(pos) is not int or pos < -1 or pos >= len(self.tabs):
            pos = -1
        self.notebook.remove_page(pos)
        tab = self.tabs.pop(pos)
        tab.widget.get_children()[0].destroy()
        tab.widget.destroy()
        self.update_display()

    def select_tab (self, tab):
        if type(tab) is BrowserTab:
            tab = self.tabs.index(tab)
        elif type(tab) is not int:
            raise TypeError('invalid tab argument')
        self.notebook.set_current_page(tab)

    def current_tab (self):
        return self.tabs[self.notebook.get_current_page()]

    def load (self, url, tab = None, *args):
        if tab is None:
            if not self.tabs:
                tab = self.new_tab()
                self.tabs.append(tab)
            tab = self.current_tab()
        elif type(tab) is int:
            tab = self.tabs[tab]
        tab.load(url, *args)

    def __init__ (self, browser):
        self.browser = browser
        self.window = gtk.Window()
        self.window.resize(800, 600)
        self.window.connect('delete_event', self.browser.window_closed)
        self.notebook = gtk.Notebook()
        self.window.add(self.notebook)
        self.tabs = []
        self.update_display()
        self.window.show_all()

class Browser:
    def window_closed (self, window, event):
        for w in self.windows:
            if window is w.window:
                self.windows.remove(w)
                for tab in w.tabs:
                    children = tab.widget.get_children()
                    if children:
                        children[0].destroy()
                    tab.widget.destroy()
                break
        return False

    def load (self, url, new = False, *args):
        if new == 'window' or not self.windows:
            w = BrowserWindow(self)
            self.windows.append(w)
            w.load(url, None, *args)
        else:
            w = self.windows[-1]
            if new == 'tab':
                w.new_tab()
                w.select_tab(-1)
                w.load(url, -1, *args)
            else:
                w.load(url, None, *args)

    def __init__ (self):
        self.windows = []

gtk.gdk.threads_init()
