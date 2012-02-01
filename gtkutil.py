"""Miscellaneous PyGTK-based stuff.

Python version: 2.
Release: 5.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    FUNCTIONS

scale_pixbuf
defaultise
tabify
confirm
get_login

    DATA

italic: Pango italic property
bold: Pango bold property

"""

try:
    import gtk, pango
except ImportError:
    raise ImportError('PyGTK cannot be found')
from textwrap import fill

italic = pango.AttrList()
italic.insert(pango.AttrStyle(pango.STYLE_ITALIC, 0, -1))

bold = pango.AttrList()
bold.insert(pango.AttrWeight(pango.WEIGHT_BOLD, 0, -1))

def scale_pixbuf (old, w = None, h = None, scale_x = None, scale_y = None):
    """Scale a gtk.gdk.Pixbuf.

scale_pixbuf(old[, w[, h]][, scale_x[, scale_y]]) -> new

old: the pixbuf to scale.
w: the width of the new pixbuf.
h: the width of the new pixbuf.
scale_x: the factor to scale by horizontally.
scale_y: the factor to scale by vertically.

One of w or scale_x is required.  If w is given and h is not, or scale_x is
given and scale_y is not, the image's aspect ratio is preserved.

"""
    if w is None:
        if scale_x is None:
            raise TypeError('one of w and scale_x must be given')
        x = scale_x
        if scale_y is None:
            y = x
        else:
            y = scale_y
        w = int(old.get_width() * x)
        h = int(old.get_height() * y)
    else:
        x = float(w) / old.get_width()
        if h is None:
            y = x
            h = int(old.get_height() * y)
        else:
            y = float(h) / old.get_height()
    try:
        new = gtk.gdk.Pixbuf(old.get_colorspace(), old.get_has_alpha(),
                            old.get_bits_per_sample(), w, h)
    except RuntimeError:
        raise ValueError('the resulting image size is invalid')
    old.scale(new, 0, 0, w, h, 0, 0, x, y, gtk.gdk.INTERP_BILINEAR)
    return new

def _make_default (button):
    # store current default widget of the window the button's in, if any
    window = button.get_toplevel()
    if isinstance(window, gtk.Window):
        button._window_old_default = window.default_widget
    # make button default
    button.grab_default()

def _unmake_default (button):
    # restore whatever was the window's default widget before, if anything
    window = button.get_toplevel()
    if isinstance(window, gtk.Window):
        try:
            default = button._window_old_default
        except AttributeError:
            default = None
        else:
            del button._window_old_default
        window.set_default(default)

def defaultise (button, *entries):
    """Set a button as the default for some entries.

defaultise(button, *entries)

button: the gtk.Button that activating one of the entries will activate.
entries: the gtk.Entry widgets that activate the button.

"""
    button.set_flags(gtk.CAN_DEFAULT)
    for entry in entries:
        entry.set_activates_default(True)
        entry.connect('focus_in_event', lambda entry, event: _make_default(button))
        entry.connect('focus_out_event', lambda entry, event: _unmake_default(button))

def tabify (tab_list, padding = 6, pair_padding = 18, tab_width = 12, tabbed_first = False, pad_right = False, container = None):
    """Return a container of GTK widgets with tabbing.

tabify (tab_list, padding = 6, pair_padding = 18, tab_width = 12,
    tabbed_first = False, pad_right = False[, container]) -> gtk.VBox

tab_list: list of sections, each one or a list of widgets to tabify; alternate
          sections are tabbed/untabbed.
padding: vertical padding between each section and between widgets in the same
         section.
pair_padding: vertical padding between each pair of sections (tabbed-untabbed
              or untabbed-tabbed depending on tabbed_first).
tab_width: indentation of tabbed sections.
tabbed_first: whether the first section is tabbed (alternates thereafter).
pad_right: whether to add padding to the right of tabbed sections (as well as
           the left).
container: a container to pack sections into (pack_start) instead of creating
           and returning a gtk.VBox.  The pair_padding argument has no effect
           if this is given.

The show method is not called on any passed widgets, but is called on all
created containers, including the returned outer gtk.VBox.

Pass anything boolean False for a section to make it blank.  Sections can also
be a string (instead of an list), in which case a bold, left-aligned gtk.Label
is created (useful for headings).

"""
    # outer container
    if container is None:
        v0 = gtk.VBox(False, pair_padding)
    else:
        v0 = container

    # pack sections in
    for x in xrange(len(tab_list)):
        if not x % 2:
            # start of alternation
            # remove last v1 if exists and empty
            try:
                if not v1.get_children():
                    v0.remove(v1)
                    v1.destroy()
            except NameError:
                pass
            # initialise this container of (one or) two sections
            v1 = gtk.VBox(False, padding)
            v0.pack_start(v1, False)
            v1.show()
        if not tab_list[x]:
            # empty section
            continue

        if x % 2 == tabbed_first:
            # not-tabbed section
            v2 = v1
        else:
            # tabbed section
            # if tab width is odd, add a pixel
            h1 = gtk.HBox(False, tab_width % 2)
            v1.pack_start(h1, False)
            h1.pack_start(gtk.HBox(), False, padding = tab_width / 2)
            v2 = gtk.VBox(False, padding)
            h1.pack_start(v2)
            if pad_right:
                h1.pack_end(gtk.HBox(), False, padding = tab_width / 2)
            h1.show_all()
        if isinstance(tab_list[x], gtk.Widget):
            # single widget
            v2.pack_start(tab_list[x], False)
        else:
            try:
                for widget in tab_list[x]:
                    v2.pack_start(widget, False)
            except TypeError:
                if isinstance(tab_list[x], basestring):
                    # got string; make a left-aligned bold label
                    widget = gtk.Label(tab_list[x])
                    widget.set_alignment(0, 0.5)
                    widget.set_property('attributes', bold)
                    v2.pack_start(widget, False)
                    widget.show()
                else:
                    raise TypeError('expected list of widgets, got {0}'.format(tab_list[x]))

    v0.show()
    return v0

def confirm (title = 'Confirm action', question = 'Are you sure?', parent = None, check_label = 'don\'t ask again'):
    """Display a confirmation dialogue with checkbox.

confirm(title = 'Confirm action', question = 'Are you sure?'[, parent],
    check_label = 'don\'t ask again') -> (response, checked)

title: the title of the dialogue window.
question: the main text of the dialogue.
parent: the parent window to set the dialogue transient for.
check_label: the label for the checkbox.

The returned response is True if Yes was clicked, False if No was clicked, and
None if the dialogue was closed; checked gives the final state of the checkbox.

"""
    # create
    d = gtk.MessageDialog(parent, 0, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, question)
    d.set_title(title)
    c = gtk.CheckButton(check_label)
    # place below message
    d.vbox.get_children()[0].get_children()[1].pack_start(c)
    c.show()
    # focus on 'No'
    d.action_area.get_children()[1].grab_focus()
    # run
    response = d.run()
    d.destroy()
    # return
    check = c.get_active()
    if response == gtk.RESPONSE_YES:
        return True, check
    elif response == gtk.RESPONSE_NO:
        return False, check
    else:
        return None, check

def get_login (title = 'Log in', parent = None, label = None, just_pwd = False, checkbox = None, validator = None, validator_args = (), hide_while_validating = False, error_msg = None, u_str = 'Username', p_str = 'Password'):
    """Get login credentials.

get_login(title = 'Log in'[, parent][, label], just_pwd = False[, checkbox]
    [, validator = None[, validator_args = ()], hide_while_validating = False
    [, error_msg]], u_str = 'Username', p_str = 'Password')

title: the title of the dialogue window.
parent: the parent window to set the dialogue transient for.
label: text for a gtk.Label to display before the input field(s).
just_pwd: whether to display only a password field (as opposed to username and
          password).
checkbox: the label for a checkbox displayed under the input field(s).
validator: a function that takes the normal return value of this function and
           validates the input.  If it returns False, we reject the input and
           try again.  Any other returned value is returned from this function
           (detailed below).
validator_args: list of arguments to pass to the validator function (after the
                normal return value of this function(.
hide_while_validating: whether to hide the dialogue window while the validator
                       function is running (else set insensitive).
error_msg: an error message to display if validation fails.
u_str: the username field label.
p_str: the password field label.

The last two arguments are intended to make localisation possible.

If the dialogue was canceled, returns None; if the 'OK' button was pressed
(and the input passed validation, if any), returns a list of the form
[[username], password[, checkbox][, validation]], where:

username: the input username (only if just_pwd is False).
password: the input password.
checkbox: whether the checkbox was ticked (only if the checkbox argument is
          given).
validation: the return value from the validator function (only if the validator
            argument is given).

"""
    # set up
    d = gtk.Dialog(title, parent, 0, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
    d.set_resizable(False)
    outer = gtk.VBox(False, 12)
    d.vbox.pack_start(outer)
    outer.set_border_width(12)
    # labels
    if label is not None:
        l = gtk.Label(fill(label, 40))
        l.set_alignment(0, 0.5)
        outer.pack_start(l)
    if error_msg:
        err = gtk.Label(fill(error_msg, 40))
        err.set_property('attributes', italic)
        err.set_alignment(0, 0.5)
        outer.pack_start(err)
    # entries
    h = gtk.HBox(False, 6)
    outer.pack_start(h)
    v = gtk.VBox(True, 6)
    h.pack_start(v)
    for x in (p_str + ':',) if just_pwd else (u_str + ':', p_str + ':'):
        l = gtk.Label(x)
        l.set_alignment(0, .5)
        v.pack_start(l)
    v = gtk.VBox(True, 6)
    h.pack_start(v)
    if not just_pwd:
        user = gtk.Entry()
    pwd = gtk.Entry()
    pwd.set_visibility(False)
    for e in (pwd,) if just_pwd else (user, pwd):
        v.pack_start(e)
        e.set_flags(gtk.CAN_FOCUS)
        e.set_activates_default(True)
        e.connect('activate', lambda *args: d.response(gtk.RESPONSE_OK))
    # checkbox
    if checkbox is not None:
        h = gtk.HBox(False, 6)
        outer.pack_start(h)
        check = gtk.CheckButton(checkbox)
        h.pack_start(check, padding = 6)
    # run
    d.show_all()
    if error_msg is not None:
        err.hide()
    while True:
        d.set_sensitive(True)
        d.show()
        (pwd if just_pwd else user).grab_focus()
        response = d.run()
        if response != gtk.RESPONSE_OK:
            break
        result = []
        if not just_pwd:
            u = user.get_text()
            result.append(u)
        p = pwd.get_text()
        result.append(p)
        if checkbox is not None:
            c = check.get_active()
            result.append(c)
        if hide_while_validating or validator is None:
            d.hide()
        else:
            d.set_sensitive(False)
        if validator is None:
            break
        else:
            v = validator(*(result + list(validator_args)))
            if v is not False:
                break
        if error_msg is not None:
            err.show()
    # return
    d.destroy()
    if response == gtk.RESPONSE_OK:
        result = []
        if not just_pwd:
            result.append(u)
        result.append(p)
        if checkbox is not None:
            result.append(c)
        if validator is not None:
            result.append(v)
        return result
    else:
        return None
