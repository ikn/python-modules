"""Handle data files in a specific format.

Python version: 2.
Release: 2.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    FUNCTIONS

parse
load
generate
save

    DATA MODEL

Data is organised into sections, each composed of a number of entries.  An
entry contains a list of arguments, each with a predefined type.  Some
arguments may be optional: these must follow all compulsory arguments, of which
there must be at least one.

The type used for each argument must define a reversible string format.  That
is, for a given object to store in data, str(object) must give an argument and
type(argument) must give back the object.  Any line breaks in the string
representation of arguments are replaced with a space when generating a data
string.

Some arbitrary subset of arguments may be repeated an arbitrary number of times
for each entry.  These must be adjacent arguments, at the end of the defined
set of accepted arguments, and all arguments before repeated ones must be
compulsory.  THIS IS NOT IMPLEMENTED YET (TODO).

A data string of entries is parsed into a parsed format of objects, which in
turn can be used to generate a data string.  This is all done according to a
definition.

    DATA STRING FORMAT

A data string is the data as accepted by parse/load and returned by
generate/save.

A section is denoted by '[section_name]' on its own line. Every subsequent line
up to the next section heading or the end of the string is considered part of
this section.

Each line in a section is a list of whitespace-separated arguments.  These have
a type defined by the type given in the passed definition for that argument.
Arguments can be omitted if default values are defined.

Repeated argument sets are represented in data strings by prepending whitespace
to the new line containing each continuation.  For example, a polygon defined
by its RGB colour and some (x, y) points might have the entry

255 150 0 -10.9 0
          1 0.5
          3.2 1

The amount of indentation is not important, and can vary between repetitions in
the same entry.

    PARSED DATA FORMAT

Parsed data is the data as returned by parse/load and accepted by
generate/save.

This is a {section: entries} dict, where entries is a list of lists of
arguments.  Optional arguments may be omitted to use defaults.  Repeated
arguments are given a further nested list of lists in the entry.

    DEFINITION FORMAT

The definition format is a {section: data} dict, where section is the section
name and data is a list of argument types, which can be (type, default) tuples
for optional arguments.

Argument types are classes or other callables to pass the raw string data to
when parsing.  Optional arguments must come after all compulsory ones, and
each section must define at least one compulsory argument.

Repeated sets of arguments can be defined in the definition by placing '+'
before them in the types list.  In this case, all arguments before the repeated
ones must be compulsory.  For the polygon example used previously, the
definition could be

(int, int, int, '+', float, float)

"""

from os.path import exists
import re
from shlex import shlex

line_split = re.compile(r'[\r\n]+')
whitespace = re.compile(r'[ \t\f\v]')
default_quote = '"'
quotes = '\'"`'

def _parse_section (defn, lines):
    """Parse the lines in a data file section."""
    entries = []
    # separate types and defaults for easier use later
    types = [x if type(x) is type else x[0] for x in defn]
    defaults = [x[1] for x in defn if type(x) is not type]
    optional = len(defaults)
    num_types = len(types)
    # parse each line in this section
    for line in lines:
        if line[0] == '[' and line[-1] == ']':
            # new section starting
            break
        entry = []
        parser = shlex(line, posix = True)
        parser.quotes = quotes
        # should be able to escape ' within '' (as well as " in "")
        parser.escapedquotes = quotes
        words = [word for word in parser]
        # compile entry
        for cls, word in zip(types, words):
            entry.append(cls(word))
        # use defaults for missing optional data
        for i in xrange(len(words) + optional - num_types, optional):
            entry.append(defaults[i])
        entries.append(entry)
    return entries

def parse (data, definition, sections = None):
    """Parse data from a string.

load(data, definition[, sections]) -> parsed_data

data: data string.
definition: definition to use.
sections: the sections to parse and return.  Defaults to all.

parsed_data: the parsed data.  Each entry is filled up to the same length with
             defaults where necessary.

See module documentation for details on data string, parsed data and definition
formats.

"""
    # split into lines
    lines = []
    for line in re.split(line_split, data):
        line = line.strip()
        if line:
            lines.append(line)
    # parse using definition
    data = {}
    for sect in definition:
        if sections is None or sect in sections:
            # look for section header
            try:
                head_line = lines.index('[{0}]'.format(sect))
            except ValueError:
                # add empty list for missing section
                data[sect] = []
            else:
                data[sect] = _parse_section(definition[sect],
                                            lines[head_line + 1:])
    return data

def load (fn, definition, sections = None):
    """Load data from a file.

load(fn, definition[, sections]) -> data

fn: file path.
definition: definition to use.
sections: the sections to parse and return.  Defaults to all.

data: the parsed data.  Each entry is filled up to the same length with defaults
      where necessary.

See module documentation for details on data string, parsed data and definition
formats.

"""
    with open(fn) as f:
        s = f.read()
    return parse(s, definition, sections)

def generate (data, definition):
    """Generate a data string.

generate(data, definition) -> data_string.

data: parsed data to use.
definition: definition to use.

data_string: the generated data string.

See module documentation for details on data string, parsed data and definition
formats.

"""
    err = 'data doesn\'t match definition'
    sects = []
    for sect in [sect for sect in data if sect in definition]:
        entries = data[sect]
        types = [x if type(x) is type else x[1] for x in definition[sect]]
        entry_strings = []
        for entry in entries:
            if len(entry) > len(types):
                err = '{0}: too many arguments in entry'.format(err)
                raise ValueError(err)
            args = []
            for i in xrange(len(entry)):
                arg = str(entry[i])
                # check argument is of valid type and value
                cls = types[i]
                try:
                    cls(arg)
                except:
                    raise ValueError('{0}: couldn\'t retrieve str({1}) using '
                                     '{2}'.format(err, arg, cls))
                # replace line breaks with spaces
                arg = re.sub(line_split, ' ', arg)
                # quote if contains whitespace
                if re.search(whitespace, arg):
                    # use quotes not in the string
                    quotes_used = [quote in arg for quote in quotes]
                    if all(quotes_used):
                        # if all quotes used, escape and use the default
                        arg = re.sub(default_quote, '\\' + default_quote, arg)
                        quote = default_quote
                    else:
                        # get first unused quote
                        quote = quotes[quotes_used.index(False)]
                    arg = '{0}{1}{0}'.format(quote, arg)
                args.append(arg)
            if args:
                entry_strings.append(' '.join(args))
        if entry_strings:
            sects.append('[{0}]\n'.format(sect) + '\n'.join(entry_strings))
    return '\n\n'.join(sects)

def save (data, definition, fn, overwrite = False):
    """Save data to a file.

save(data, definition, fn, overwrite = False)

data: parsed data to use.
definition: definition to use.
fn: file path.
overwrite: if False, raise IOError if file already exists.

See module documentation for details on data string, parsed data and definition
formats.

"""
    if exists(fn) and not overwrite:
        raise IOError('file \'{0}\' exists'.format(fn))
    # open file first to save parsing if there's a problem doing so
    with open(fn, 'w') as f:
        data_string = generate(data, definition)
        f.write(data_string)
