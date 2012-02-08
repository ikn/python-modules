"""A file manager for an arbitrary filesystem backend.

Python version: 3.
Release: 2.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    CLASSES

Manager
AddressBar

    FUNCTIONS

buttons

"""

# TODO:
# - hide bits of the addressbar breadcrumbs if it gets bigger than its parent
# - refresh should preserve selection
# - should remember selection on back/forward
# - if drag from an already selected file, drag and drop it/multiple instead of
#   changing selection
# - allow drag and drop between instances
# - searching doesn't work

from gi.repository import Gtk as gtk

COL_IS_DIR = 0
COL_ICON = 1
COL_NAME = 2
COL_COLOUR = 3
COL_EDITABLE = 4

NAME_COLOUR = '#000'
NAME_COLOUR_CUT = '#666'

class Manager (gtk.TreeView):
    """A filesystem viewer (and manager).  Subclass of Gtk.TreeView.

For keyboard accelerators to work, add Manager.accel_group to the window via
Gtk.Window.add_accel_group.

In all cases, the path is a hierarchical list of directory names, possibly
ending in a file name.  For example, '/some/path/current_dir/' is represented
by ['some', 'path', 'current_dir'].

    CONSTRUCTOR

Manager(backend, path = [], read_only = False, cache = False)

backend: an object with methods as follows.  Any method that changes the
         directory tree should not return until any call to list_dir will
         reflect the changes.

    list_dir: a function that takes the current path and returns a list of
              directories and files in it.  Each item is a (name, is_dir) tuple
              indicating the item's name and whether it is a directory.  The
              order of items is unimportant.

    open_files: this is optional.  It takes any number of file (not directory)
                paths as arguments to 'open' them.

         The following are only required if read_only is False.  They should
         each return True if the action is taken, else False.

    copy: takes a list of (old_path, new_path) tuples to copy files or
          directories.

    move: takes a list of (old_path, new_path) tuples to move files or
          directories.

    delete: takes file or directory paths as separate arguments to delete.

    new_dir: takes directory path to create.

         You should display and handle errors and confirmations yourself.

path: the initial path to display.
read_only: whether the directory tree is read-only; if True, things like copy,
           move and delete aren't provided, and the backend need not support
           these methods.
cache: whether to cache directory contents when requested.  There is no need to
       clear the cache after any changes that go through this class and the
       given backend (copy, delete, etc.); this is done automatically.

    METHODS

refresh
set_path
up
back
forwards
get_selected_files
clear_cache

    ATTRIBUTES

backend: as given.
path: as given; change it with the set_path method.
cache: as given.  Setting this to False will disable further caching, but not
       clear the existing cache; use the clear_cache method for this.
buttons: the buttons attribute of a Buttons instance.

"""

    def __init__ (self, backend, path = [], read_only = False, cache = False):
        self.backend = backend
        self.path = list(path)
        self.read_only = read_only
        self.cache = cache
        self._cache = {}
        self._clipboard = None
        self._history = [self.path]
        self._hist_pos = 0
        self.buttons = None
        self.address_bar = None

        # interface
        self._model = gtk.ListStore(bool, str, str, str, bool)
        gtk.TreeView.__init__(self, self._model)
        self.get_selection().set_mode(gtk.SelectionMode.MULTIPLE)
        self.set_search_column(1)
        self.set_enable_tree_lines(True)
        self.set_headers_visible(False)
        self.set_rubber_banding(True)
        self.set_rules_hint(True)
        # signals
        self.connect('row-activated', self._open)
        self.connect('button-press-event', self._click)
        # columns
        self.append_column(gtk.TreeViewColumn('Icon', gtk.CellRendererPixbuf(),
                                              stock_id = COL_ICON))
        r = gtk.CellRendererText()
        r.set_property('foreground-set', True)
        r.connect('edited', self._done_rename)
        r.connect('editing-canceled', self._cancel_rename)
        self.append_column(gtk.TreeViewColumn('Name', r, text = COL_NAME,
                                              foreground = COL_COLOUR,
                                              editable = COL_EDITABLE))
        # sorting
        self._model.set_default_sort_func(self._sort_tree)
        # FIXME: -1 should be DEFAULT_SORT_COLUMN_ID, but I can't find it
        self._model.set_sort_column_id(-1, gtk.SortType.ASCENDING)
        # accelerators
        group = self.accel_group = gtk.AccelGroup()
        accels = [
            ('F2', self._rename_selected),
            ('F5', self.refresh),
            ('Menu', self._menu),
            ('BackSpace', self.up),
            ('<alt>Up', self.up),
            ('<alt>Left', self.back),
            ('<alt>Right', self.forwards),
            ('<ctrl>l', self._focus_address_bar)
        ]
        if not self.read_only:
            accels += [
                ('<ctrl>x', self._copy, None, True),
                ('Escape', self._uncut, True),
                ('<ctrl>c', self._copy),
                ('<ctrl>v', self._paste),
                ('Delete', self._delete)
            ]
        def mk_fn (cb, *cb_args):
            def f (*args):
                if self.is_focus():
                    cb(*cb_args)
            return f
        for accel, cb, *args in accels:
            key, mods = gtk.accelerator_parse(accel)
            group.connect(key, mods, 0, mk_fn(cb, *args))

        self.refresh()

    def _focus_address_bar (self):
        """Give focus to the address bar, if any."""
        if self.address_bar is not None:
            self.address_bar.set_mode(True)
            self.address_bar.entry.grab_focus()

    def _show_menu (self, actions, menu_args):
        """Create a display a popup menu."""
        # HACK: need to store the menu for some reason, else it doesn't show up
        # - maybe GTK stores it in such a way that the garbage collector thinks
        # it can get rid of it or something
        menu = self._temp_menu = gtk.Menu()
        f = lambda widget, cb, *args: cb(*args)
        for x in actions:
            if x is None:
                item = gtk.SeparatorMenuItem()
            else:
                name, tooltip, cb, *cb_args = x
                item = gtk.ImageMenuItem(name)
                if name.startswith('gtk-'):
                    item.set_use_stock(True)
                elif '_' in name:
                    item.set_use_underline(True)
                if tooltip is not None:
                    item.set_tooltip_text(tooltip)
                cb_ = cb
                item.connect('activate', f, cb, *cb_args)
            menu.append(item)
        menu.show_all()
        menu.popup(*menu_args)

    def _show_noitem_menu (self, menu_args):
        """Show the context menu when no files are selected."""
        # compile a list of actions to show in the menu
        actions = []
        if not self.read_only:
            actions.append((gtk.STOCK_NEW, 'Create directory', self._new_dir))
            # only show paste if clipboard has something in it
            if self._clipboard is not None:
                actions.append((gtk.STOCK_PASTE, 'Paste cut or copied files',
                                self._paste))
            actions.append(None)
        actions.append((gtk.STOCK_SELECT_ALL, 'Select all files',
                        self.get_selection().select_all))
        # only show up if not in root directory
        if self.path:
            actions.append((gtk.STOCK_GO_UP, 'Go to parent directory',
                            self.up))
        # only show back if have history
        if self._hist_pos != 0:
            actions.append((gtk.STOCK_GO_BACK, 'Go to the previous directory',
                            self.back))
        # only show forwards if have forwards history
        if self._hist_pos != len(self._history) - 1:
            actions.append((gtk.STOCK_GO_FORWARD,
                            'Go to the next directory in history',
                            self.forwards))
        # show menu
        if actions:
            self._show_menu(actions, menu_args)
        pass

    def _show_item_menu (self, paths, menu_args):
        """Show the context menu when files are selected."""
        # compile a list of actions to show in the menu
        current_path = self.path
        model = self._model
        items = [model[path] for path in paths]
        item_paths = tuple(current_path + [item[COL_NAME]] for item in items)
        # only show open if supported by backend and no dirs are selected, or
        # only one dir and nothing else is selected
        all_files = not any(item[COL_IS_DIR] for item in items)
        one_dir = len(items) == 1 and items[0][COL_IS_DIR]
        if (hasattr(self.backend, 'open_files') and all_files) or one_dir:
            if all_files:
                f = (self.backend.open_files,) + item_paths
            else:
                f = (self._open, None, paths[0])
            actions = [(gtk.STOCK_OPEN, 'Open all selected files') + f, None]
        else:
            actions = []
        if not self.read_only:
            actions += [
                (gtk.STOCK_CUT, 'Prepare to move selected files', self._copy,
                 paths, True),
                (gtk.STOCK_COPY, 'Prepare to copy selected files',
                         self._copy, paths)
            ]
            # only show paste if clipboard has something in it
            if self._clipboard is not None:
                actions.append((gtk.STOCK_PASTE, 'Paste cut or copied files',
                                self._paste))
            actions += [
                (gtk.STOCK_DELETE, 'Delete selected files',
                 self._delete) + item_paths,
                ('_Rename', 'Rename selected files', self._rename, paths),
                (gtk.STOCK_NEW, 'Create directory', self._new_dir),
                None
            ]
        actions.append((gtk.STOCK_SELECT_ALL, 'Select all files',
                        self.get_selection().select_all))
        # only show up if not in root directory
        if current_path:
            actions.append((gtk.STOCK_GO_UP, 'Go to parent directory',
                            self.up))
        # only show back if have history
        if self._hist_pos != 0:
            actions.append((gtk.STOCK_GO_BACK, 'Go to the previous directory',
                            self.back))
        # only show forwards if have forwards history
        if self._hist_pos != len(self._history) - 1:
            actions.append((gtk.STOCK_GO_FORWARD,
                            'Go to the next directory in history',
                            self.forwards))
        # show menu
        if actions:
            self._show_menu(actions, menu_args)

    def _menu (self):
        """Show the context menu."""
        menu_args = (None, None, None, None, 0, gtk.get_current_event_time())
        selected = self._get_selected_paths()
        if selected:
            self._show_item_menu(selected, menu_args)
        else:
            self._show_noitem_menu(menu_args)

    def _click (self, tree, event):
        """Handle click events."""
        if event.button not in (1, 3):
            return
        sel = self.get_path_at_pos(int(event.x), int(event.y))
        if event.button == 1:
            if sel is None:
                # deselect
                self.get_selection().unselect_all()
        elif event.button == 3:
            # right-click: show context menu
            menu_args = (None, None, None, None, event.button, event.time)
            if sel is None:
                # deselect
                self.get_selection().unselect_all()
                # no-file context menu
                self._show_noitem_menu(menu_args)
                return
            # get clicked file and current selection
            clicked = sel[0]
            selected = self._get_selected_paths()
            if clicked in selected:
                # have menu apply to all selected files
                items = selected
                # don't change selection
                rtn = True
            else:
                # have menu apply to clicked file
                items = [clicked]
                # select clicked file
                rtn = False
            # show menu
            self._show_item_menu(items, menu_args)
            return rtn

    def _open (self, view, path, column = None):
        """Open a directory or file."""
        row = self._model[path]
        is_dir = row[COL_IS_DIR]
        name = row[COL_NAME]
        if is_dir:
            self.set_path(self.path + [name])
        else:
            try:
                self.backend.open_files(self.path + [name])
            except AttributeError:
                pass

    def _uncut (self, this_dir_only = False):
        """Cancel cut selection."""
        cb = self._clipboard
        if cb is not None and cb[1]:
            for row in self._model:
                row[COL_COLOUR] = NAME_COLOUR
            cb[1] = False

    def _copy (self, paths = None, cut = False):
        """Copy files for given TreeModel paths or selected files."""
        if paths is None:
            paths = self.get_selection().get_selected_rows()[1]
        files = [self.path + [self._model[path][COL_NAME]] for path in paths]
        if files:
            self._uncut()
            self._clipboard = [files, cut]
            if cut:
                # grey text for cut files
                for path in paths:
                    self._model[path][COL_COLOUR] = NAME_COLOUR_CUT

    def _paste (self):
        """Paste files in the clipboard."""
        cb = self._clipboard
        if cb is not None:
            files, cut = cb
            path = self.path
            f = self.backend.move if cut else self.backend.copy
            if f(*((f, path + [f[-1]]) for f in files)):
                self.refresh(True)
                if cut:
                    self._uncut()

    def _delete (self, *files):
        """Delete give files, else selected files, if any."""
        if not files:
            path = self.path
            files = [path + [name] for name in self.get_selected_files()]
        if files:
            if self.backend.delete(*files):
                # TODO: select next file if any, else previous if any
                self.refresh(True)

    def _rename_selected (self):
        """Rename the selected files."""
        self._rename(self._get_selected_paths())

    def _edit (self, path):
        """Edit the name at the given TreeModel path."""
        if not isinstance(path, gtk.TreePath):
            path = gtk.TreePath(path)
        self.set_cursor(path, self.get_column(1), True)

    def _rename (self, paths):
        """Rename the first of the given TreeModel paths."""
        if not paths:
            return
        path = paths[0]
        self._model[path][COL_EDITABLE] = True
        self._edit(path)

    def _cancel_rename (self, renderer):
        """Cancel renaming callback."""
        name = renderer.get_property('text')
        for row in self._model:
            if row[COL_NAME] == name:
                row[COL_EDITABLE] = False
                return

    def _done_rename (self, renderer, path, text):
        """Rename callback."""
        row = self._model[path]
        old = self.path + [row[COL_NAME]]
        new = self.path + [text]
        if old == new:
            # unedit
            row[COL_EDITABLE] = False
            return
        if self.backend.move((old, new)):
            self.refresh(True)
        else:
            # failed; reselect
            self._edit(path)

    def _new_dir (self, *args):
        """Create a new directory here."""
        # find a name not already used
        names = [row[2] for row in self._model]
        i = 1
        name = 'new'
        while name in names:
            i += 1
            name = 'new ({})'.format(i)
        # create it
        if not self.backend.new_dir(self.path + [name]):
            # failed
            return
        self.refresh(True)
        # find it in the tree
        j = None
        for i, row in enumerate(self._model):
            if name == row[2]:
                j = i
                break
        if j is not None:
            self._rename([i])

    def refresh (self, purge_cache = False):
        """Refresh the directory listing."""
        # TODO: preserve selection if possible
        model = self._model
        model.clear()
        # try to retrieve from cache
        try:
            if purge_cache:
                raise KeyError()
            items = self._cache[tuple(self.path)]
        except KeyError:
            # request listing
            items = self.backend.list_dir(self.path)
            # store in cache
            if self.cache:
                self._cache[tuple(self.path)] = items
        # disable sorting
        # FIXME: -2 should be UNSORTED_SORT_COLUMN_ID, but I can't find it
        model.set_sort_column_id(-2, gtk.SortType.ASCENDING)
        # add to model
        cb = self._clipboard
        if cb is not None:
            cb = cb[0] if cb[1] else False
        DIR = gtk.STOCK_DIRECTORY
        FILE = gtk.STOCK_FILE
        path = self.path
        for name, is_dir in items:
            icon = DIR if is_dir else FILE
            if cb and path + [name] in cb:
                colour = NAME_COLOUR_CUT
            else:
                colour = NAME_COLOUR
            model.append((is_dir, icon, name, colour, False))
        # enable sorting again
        # FIXME: -1 should be DEFAULT_SORT_COLUMN_ID, but I can't find it
        model.set_sort_column_id(-1, gtk.SortType.ASCENDING)

    def set_path (self, path, add_to_hist = True, tell_address_bar = True):
        """Set the current path.

set_path(path, add_to_hist = True, tell_address_bar = True)

path: a hierarchical list of directory names indicating the current path.
add_to_hist: whether to add this path to the navigation history.
tell_address_bar: whether to notify the AddressBar instance associated with
                  this widget, if any.

"""
        path = list(path)
        if path == self.path:
            return
        self.path = path
        # history
        if add_to_hist:
            self._hist_pos += 1
            self._history = self._history[:self._hist_pos] + [path]
        # file listing
        self.refresh()
        # address bar
        if tell_address_bar and self.address_bar is not None:
            self.address_bar.set_path(path)
        # button sensitivity
        if self.buttons is not None:
            sensitive = (self._hist_pos != 0,
                         self._hist_pos != len(self._history) - 1,
                         bool(self.path), not self.read_only)
            for i, s in enumerate(sensitive):
                try:
                    self.buttons[i].set_sensitive(s)
                except IndexError:
                    pass

    def up (self):
        """Go up one directory, if possible."""
        if self.path:
            self.set_path(self.path[:-1])

    def back (self):
        """Go back in the navigation history, if possible."""
        if self._hist_pos != 0:
            self._hist_pos -= 1
            self.set_path(self._history[self._hist_pos], False)

    def forwards (self):
        """Go forwards in the navigation history, if possible."""
        if self._hist_pos != len(self._history) - 1:
            self._hist_pos += 1
            self.set_path(self._history[self._hist_pos], False)

    def _get_selected_paths (self):
        """Get the model paths of the selected files and directories."""
        return self.get_selection().get_selected_rows()[1]

    def get_selected_files (self):
        """Get the paths of the currently selected files and directories."""
        model, paths = self.get_selection().get_selected_rows()
        return [model[path][COL_NAME] for path in paths]

    def clear_cache (self, *dirs):
        """Clear the current cache, or specific cached directories.

clear_cache(*dirs)

dirs: if none are given, clear all cache; otherwise, clear the cache for these
      paths.

"""
        if dirs:
            for d in dirs:
                try:
                    del self._cache[tuple(d)]
                except KeyError:
                    pass
        else:
            self._cache = {}

    def _sort_tree (self, model, iter1, iter2, data):
        """Sort callback."""
        row1 = model[iter1]
        is_dir1 = row1[COL_IS_DIR]
        row2 = model[iter2]
        is_dir2 = row2[COL_IS_DIR]
        # dirs first
        if is_dir1 != is_dir2:
            return 1 if is_dir2 else -1
        # if either name is None, it's not in the model yet
        name1 = row1[COL_NAME]
        name2 = row2[COL_NAME]
        if None in (name1, name2):
            return 0
        # alphabetical
        return (name1 > name2) - (name1 < name2)


class AddressBar (gtk.Box):
    """An address bar to work with a Manager.  Subclass of Gtk.Box.

If you call show_all, call update immediately afterwards.

    CONSTRUCTOR

AddressBar(manager, sep = '/', prepend_sep = True, append_sep = False,
           padding = 6)

manager: a Manager instance.
sep: the path separator used in output.  This can be any string.
prepend_sep: whether to prepend paths in output with the path separator.
append_sep: whether to append to paths in output the path separator.
padding: the padding between widgets in this gtk.Box.

    METHODS

update
set_path
set_mode

    ATTRIBUTES

manager: as given.
sep, prepend_sep, append_sep: as given; if you change them, call the update
                              method.
address: the 'text' part of the bar: the entry and its 'OK' button.
entry: the Gtk.Entry used in the bar.
breadcrumbs: the breadcrumbs buttons used in the bar.
mode_button: the button used to switch display modes.

"""
    def __init__ (self, manager, sep = '/', prepend_sep = True,
                  append_sep = False, padding = 6):
        gtk.Box.__init__(self, False, padding)
        self.manager = manager
        self.sep = sep
        self.prepend_sep = prepend_sep
        self.append_sep = append_sep
        manager.address_bar = self
        self._working = False
        # widgets
        self.mode_button = mode_b = gtk.ToggleButton(None, gtk.STOCK_EDIT)
        f = lambda b: self.set_mode(b.get_active(), False)
        mode_b.connect('toggled', f)
        self.pack_start(mode_b, False, False, 0)
        # entry
        self.address = gtk.Box(False, padding)
        self.pack_start(self.address, True, True, 0)
        self.entry = e = gtk.Entry()
        self.address.pack_start(e, True, True, 0)
        e.connect('activate', self._set_path_entry)
        ok_b = gtk.Button(None, gtk.STOCK_OK)
        ok_b.connect('clicked', self._set_path_entry)
        self.address.pack_start(ok_b, False, False, 0)
        # breadcrumbs
        self.breadcrumbs = b = gtk.Box()
        self.pack_start(b, True, True, 0)
        root_b = gtk.ToggleButton(None, gtk.STOCK_HARDDISK)
        self.breadcrumbs.pack_start(root_b, False, False, 0)
        root_b.connect('toggled', self._breadcrumb_toggle)
        # remove button labels
        for b in (mode_b, root_b, ok_b):
            box = b.get_child().get_child()
            box.remove(box.get_children()[1])

        self.show_all()
        self.hide()
        self.update()

    def update (self):
        """Update the current displayed path."""
        self.set_mode(self.mode_button.get_active(), False)
        self.set_path(self.manager.path)

    def set_path (self, path):
        """Set the path displayed to the one given (in list form).

This does not affect the manager.

"""
        self._set_entry_path(path)
        self._set_breadcrumbs_path(path)

    def _set_entry_path (self, path):
        """Set the path in the entry to the one given (in list form)."""
        sep = self.sep
        path = sep.join(path)
        if self.prepend_sep:
            path = sep + path
        if self.append_sep:
            path += sep
        self.entry.set_text(path)

    def _set_breadcrumbs_path (self, path):
        """Set the breadcrumbs path to the one given (in list form)."""
        b = self.breadcrumbs
        self._working = True
        # remove children we don't want any more
        root, *cs = b.get_children()
        rm = False
        to_rm = []
        for c, d in zip(cs, path + [None] * (len(cs) - len(path))):
            if not rm:
                if d is not None and c.get_label() != d:
                    rm = True
                else:
                    c.set_active(False)
            if rm:
                b.remove(c)
                to_rm.append(c)
                c.destroy()
        for c in to_rm:
            cs.remove(c)
        # add extra children
        for d in path[len(cs):]:
            c = gtk.ToggleButton(d)
            self.breadcrumbs.pack_start(c, False, False, 0)
            cs.append(c)
            c.connect('toggled', self._breadcrumb_toggle)
            c.show()
        # set root activity
        b.get_children()[0].set_active(not path)
        # set at most one child active
        if path:
            cs[len(path) - 1].set_active(True)
        self._working = False

    def _set_manager_path (self, path):
        """Set the manager path to the one given (in list form)."""
        self.manager.set_path(path, tell_address_bar = False)
        self.manager.grab_focus()

    def _set_path_entry (self, widget):
        """Set the path in the manager to the one in the entry."""
        path = [d for d in self.entry.get_text().split(self.sep) if d]
        self.set_path(path)
        self._set_manager_path(path)

    def _breadcrumb_toggle (self, b):
        """Callback for toggling one of the breadcrumb buttons."""
        if self._working:
            return
        # can't untoggle
        if not b.get_active():
            self._working = True
            b.set_active(True)
            self._working = False
        # get path
        cs = self.breadcrumbs.get_children()
        path = []
        if not b.get_use_stock(): # else root
            for c in cs[1:]:
                path.append(c.get_label())
                if c is b:
                    break
        # set path
        self.set_path(path)
        self._set_manager_path(path)

    def set_mode (self, mode, fix_button = True):
        """Set the display mode: True for an entry, False for breadcrumbs."""
        if fix_button:
            self.mode_button.set_active(mode)
        if mode:
            self.breadcrumbs.hide()
            self.address.show()
        else:
            self.address.hide()
            self.breadcrumbs.show()


def buttons (manager):
    """Returns some buttons to work with a Manager.

buttons(manager) -> button_list

manager: a Manager instance.

button_list: a list of Gtk.Button instances: back, forward, up, new, in that
             order.  If manager is read-only, new is omitted.

"""
    m = manager
    m.buttons = buttons = []
    # widgets
    button_data = [
        (gtk.STOCK_GO_BACK, 'Go to the previous directory', m.back),
        (gtk.STOCK_GO_FORWARD, 'Go to the next directory in history',
         m.forwards),
        (gtk.STOCK_GO_UP, 'Go to parent directory', m.up)
    ]
    # only show new if not read-only
    if not m.read_only:
        button_data.append((gtk.STOCK_NEW, 'Create directory', m._new_dir))
    # create and add buttons
    f = lambda widget, cb, *args: cb(*args)
    for name, tooltip, cb, *cb_args in button_data:
        if name.startswith('gtk-'):
            b = gtk.Button(None, name)
        else:
            b = gtk.Button(name, None, '_' in name)
        buttons.append(b)
        b.set_tooltip_text(tooltip)
        b.connect('clicked', f, cb, *cb_args)
    # visibility
    # only allow back if have history
    buttons[0].set_sensitive(m._hist_pos != 0)
    # only allow forwards if have forwards history
    buttons[1].set_sensitive(m._hist_pos != len(m._history) - 1)
    # only allow up if not in root directory
    buttons[2].set_sensitive(bool(m.path))
    # return copy to avoid changes to manager.buttons
    return list(buttons)