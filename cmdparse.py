"""Command-line command parser.

This means stuff like "program command [options] [arguments]".  Inspired by
Mercurial, it accepts any unambiguous abbreviation of known commands.
Everything is done through the CommandParser and Command classes.

Depends on miscutil.

Python version: 2.
Release: 6.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    CLASSES

CommandParser
Command

"""

import sys
import os
from textwrap import fill as tw_fill
from math import ceil

try:
    _
except NameError:
    _ = lambda s: s

from miscutil import startwith

def fill (s, w):
    """Like textwrap.fill, but preserve newlines (\n)."""
    return '\n'.join(tw_fill(p, w) for p in s.split('\n'))

class CommandParser:
    """Command parser.

CommandParser(cmds = [][, prog][, full_prog], desc = '', tidying = True,
    case_sensitive = True, sort = True, do_exact = False)

cmds: list of Command instances.
prog: name of the program, as executed; defaults to
      os.path.basename(sys.argv[0]).
full_prog: full program (descriptive) title, and a good place to put a version
           string.  Defaults to the 'prog' argument.
desc: description given with help.
tidying: add a capital letter and full stop to a short command description when
         its help page is printed, so that the command listing can omit these.
case_sensitive: determine case-sensitivity in comparing commands.
sort: whether to sort commands when listed.  True to sort alphabetically, False
      to leave in the order they're added (the 'help' command is always first),
      else a function to pass to list.sort as the cmp argument.  If you want to
      handle this yourself, just rearrange CommandParser._cmds_order before
      parsing.
do_exact: if a given command could match two known commands, but one is an
          exact match (say, 'delete' and 'delete_all'), passing True for this
          argument will perform that command; passing False will treat the
          input as ambiguous.  This is also applied to arguments passed to the
          help command.

This is used to parse command-line input using a command-based system, where
one of a number of commands may be given, each with its own help accessible
through the 'help' command.  The full command is not required if some first few
letters, or even one, is unambiguous.

    METHODS

add_cmd
cmd_descs
full_cmd
error
help
parse

    ATTRIBUTES

cmds: {command: Command instance} dict of known commands.  It's safe to modify
      this directly.
prog, full_prog, desc, tidying, case_sensitive: as given.

"""

    def __init__ (self, cmds = [], prog = None, full_prog = None, desc = '',
                  tidying = True, case_sensitive = True, sort = True,
                  do_exact = False):
        if prog is None:
            self.prog = os.path.basename(sys.argv[0])
        else:
            self.prog = prog
        if full_prog:
            self.full_prog = full_prog
        else:
            self.full_prog = self.prog
        self.desc = desc
        self.tidying = tidying
        self.case_sensitive = case_sensitive
        self._sort = sort
        self._cmds_order = []
        self.cmds = dict((c.cmd, c) for c in cmds)
        run_help = lambda cp, args: self.help(*args[:1])
        parse = lambda args: args
        self.add_cmd('help', _('print documentation for the given command'),
                     _('Without an argument, a list of commands is given.'),
                     _('[COMMAND]'), run_help, parse, None, '__call__')
        self._do_exact = do_exact

    def add_cmd (self, *args, **kw):
        """Add a command to the parser.

Takes a Command instance or arguments to pass to Command to create one.

"""
        if isinstance(args[0], Command):
            c = args[0]
        else:
            c = Command(*args, **kw)
        self._cmds_order.append(c.cmd)
        if self._sort:
            if hasattr(self._sort, '__call__'):
                self._cmds_order.sort(self._sort)
            else:
                self._cmds_order.sort()
        self.cmds[c.cmd] = c

    def cmd_descs (self, *cmds):
        """Return aligned descriptions for the given commands."""
        if not cmds:
            cmds = self._cmds_order
        descs = []
        width = 4 * int(ceil((max(len(c) for c in cmds) + 2) / 4.))
        # list comprehension faster than generator = silly
        for cmd in [c for c in self._cmds_order if c in cmds]:
            descs.append(cmd + ' ' * (width - len(cmd)) + self.cmds[cmd].desc)
        return descs

    def full_cmd (self, cmd, can_die = False):
        """Return the matching full command(s) for the given input.

full_cmd(cmd, can_die = False)

cmd: the (possibly abbreviated) input command.
can_die: if True, call CommandParser.error if cmd doesn't match one command;
         otherwise, raise ValueError if there are no matches and return a list
         of matches otherwise.

"""
        if self._do_exact and cmd in self.cmds:
            cmds = [cmd]
        else:
            cmds = startwith(self.cmds, cmd, self.case_sensitive)
        if cmds:
            if can_die:
                if len(cmds) > 1:
                    descs = '\n'.join(self.cmd_descs(*cmds))
                    self.error(_('\'{0}\' matches more than one command:\n\n{1}').format(cmd, descs))
                else:
                    return cmds[0]
            else:
                return cmds
        else:
            if can_die:
                self.error(_('\'{0}\' doesn\'t match any commands.').format(cmd), help = True)
            else:
                raise ValueError('unknown command')

    def error (self, msg = None, cmd = None, help = False):
        """Print an error and call sys.exit(1).

error([msg][, cmd], help = False)

msg: the error message to print.
cmd: the running command that wants to raise the error.
help: whether to display the full help listing before the error message.

"""
        if cmd is None:
            if help:
                self.help()
            else:
                print self.full_prog
            print ''
        else:
            # NOTE: displays command usage, eg. 'Usage: help [COMMAND]'
            print _('Usage: {0} {1}\n').format(self.prog, self.cmds[cmd].usage)
        s = _('{0}: error').format(self.prog)
        if msg:
            s += ': ' + msg
        print s
        sys.exit(1)

    def help (self, cmd = None):
        """Display the main help page or the one for the given command."""
        if cmd:
            # specific command
            cmd = self.cmds[self.full_cmd(cmd, True)]
            desc = cmd.desc[0].upper() + cmd.desc[1:] + '.' if self.tidying else cmd.desc
            print '{0} {1}\n\n{2}'.format(self.prog, cmd.usage, desc)
            if cmd.long_desc:
                print '\n', fill(cmd.long_desc, 79)
            if cmd.option_parser:
                options = cmd.option_help()
                if options:
                    print '\n', options[:-1]
        else:
            # main help
            print self.full_prog, '\n'
            if self.desc:
                print fill(self.desc, 79), '\n'
            print '{0}:\n\n{1}'.format(_('Commands'), '\n'.join(self.cmd_descs()))

    def parse (self, args = None, help = ('-h', '--help'),
               version = ('--version',)):
        """Parse command-line arguments and act accordingly.

parse([args], help = ('-h', '--help'), version = ('--version',))

args: arguments to parse; defaults to sys.argv[1:].
help: if the first argument is one of the strings in this list, print help and
      exit.
version: like help, but print the program name and version

If a valid unambiguous command is encountered, (command, parsed_options) is
returned and the command's callback is called, if any; in all other cases,
sys.exit is called.

parsed_options is the result of running any further options given through the
option parser supplied when constructing the command; if it hasn't got one,
this is None.  Of course, this parser may also call sys.exit itself.

"""
        if args is None:
            args = sys.argv[1:]
        if len(args) == 0 or args[0] in help:
            self.help()
            sys.exit()
        elif args[0] in version:
            print self.full_prog
            sys.exit()
        else:
            cmd = self.full_cmd(args[0], True)
            c = self.cmds[cmd]
            parsed_opts = c.parse(args[1:])
            if c.callback is not None:
                c.callback(self, parsed_opts)
            return cmd, parsed_opts

class Command:
    """Command used by CommandParser.

Command(cmd[, desc][, long_desc], args = ''[, callback][, option_parser,
    parser_option_help = 'format_option_help', parser_parse = 'parse_args'])

cmd: command name.
desc: short description that should fit on one line.
long_desc: full help; this is displayed below the short description, and so
           shouldn't duplicate it.
args: a string representing the positional arguments the command takes, printed
      to illustrate usage.
callback: a function called by CommandParser when this command is run; it is
          passed the CommandParser instance and the return value of this
          instance's parse method.
option_parser: if the command takes any options, this is some object with
               methods to parse options (like optparse.OptionParser).  The
               method names are given by the next two arguments, whose defaults
               work with optparse.OptionParser.
parser_option_help: a method of option_parser that returns a string containing
                    the option listing, for printing help, or None to print
                    nothing.
parser_parse: option_parser's method to parse options, taking a list of
              command-line arguments and returning what you need.

"""

    def __init__ (self, cmd, desc = '', long_desc = '', args = '',
                  callback = None, option_parser = None,
                  parser_option_help = 'format_option_help',
                  parser_parse = 'parse_args'):
        self.cmd = cmd
        self.desc = desc
        self.long_desc = long_desc
        self.option_parser = option_parser
        if hasattr(callback, '__call__'):
            self.callback = callback
        else:
            self.callback = None
        self.parser_option_help = parser_option_help
        self.parser_parse = parser_parse
        # construct usage string
        self.usage = self.cmd
        if args:
            self.usage += ' ' + args

    def option_help (self):
        """Wrapper using parser_option_help argument."""
        if self.option_parser and self.parser_option_help is not None:
            return getattr(self.option_parser, self.parser_option_help)()
        else:
            return ''

    def parse (self, args):
        """Wrapper using parser_parse argument."""
        if self.option_parser:
            return getattr(self.option_parser, self.parser_parse)(args)
        else:
            return None
