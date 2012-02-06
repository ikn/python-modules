"""GameCube file utilities.

Python version: 3.
Release: 1.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    CLASSES

GCFS

    FUNCTIONS

read
write
copy
tree_from_dir

"""

import os
from os import sep
from shutil import rmtree
import tempfile
import codecs

CODEC = 'shift-jis'
_decode = lambda b: codecs.decode(b, CODEC)
_encode = lambda s: codecs.encode(s, CODEC)

from os import mkdir
from os.path import dirname, basename
from base64 import urlsafe_b64encode as b64

def read (f, start, size = None, num = False, until = None, block_size = 0x10):
    """Read data from a file object.

read(f, start[, size], num = False[, until, block_size = 0x10]) -> data

f: the file object to read from (open in binary mode).
start: position to start reading from.
size: amount of data to read.  until must be passed if this is not.  Even if
      you pass until, it's a good idea to give some upper limit here in case
      there's an error and the character is never found (to avoid reading in
      the whole file).
num: if True, treat the whole of the data read as a base 256 integer and
     convert it to base 10.
until: if this character (length-1 bytes object) is found, truncate the result
       and stop reading; or a function that gets passed a string of read bytes
       (with length block_size) and returns True to continue reading, else an
       integer to stop reading and keep that many bytes from the string.
block_size: amount to read between checks for this character.

Data is always measured in bytes.

"""
    f.seek(start)
    if until is None:
        if size is None:
            raise ValueError('expected size argument')
        data = f.read(size)
    else:
        # truncate until to one char
        if isinstance(until, bytes):
            until = until[:1]
        data = b''
        left = size or -1
        while left:
            # left < 0 means just keep going until the character is found
            new = block_size if left < 0 else min(block_size, left)
            new_data = f.read(new)
            if isinstance(until, bytes):
                char = new_data.find(until)
                if char == -1:
                    data += new_data
                    if len(new_data) < new:
                        # didn't get all the bytes we asked for: EOF
                        left = 0
                    else:
                        left -= new
                else:
                    # found character: stop reading
                    data += new_data[:char]
                    left = 0
            else:
                # until should be a function
                do = until(new_data)
                if isinstance(do, int):
                    # keep this many characters and stop
                    new_data = new_data[:min(max(do, 0), new)]
                    left = 0
                elif do is not True:
                    raise ValueError('until should only return True or an int')
    if num:
        size = len(data)
        data = sum(j * 256 ** (size - i - 1) for i, j in enumerate(data))
    return data

def write (data, f, pos, size = None):
    """Copy data to a file object.

write(data, f, pos[, size])

data: the data to copy.  This can be a bytes object, or an int to convert to
      base 256, ie. a bytes object.
f: the file object to write to (open in binary/write mode).
pos: position to start writing to.
size: if converting from an int, pad it to this size in bytes by prepending by
      0s.  The data will not be truncated if longer than this.

"""
    if isinstance(data, int):
        # convert to bytes
        i = data
        data = []
        while i:
            data.insert(0, i % 256)
            i //= 256
        data = b'\0' * max(size - len(data), 0) + bytes(data)
    f.seek(pos)
    f.write(data)

def copy (source, f, pos, block_size = 0x100000):
    """Copy a file to a file object.

read(source, f, pos, block_size = 0x100000) -> data

source: the file path to copy from.
f: the file object to write to (open in binary/write mode).
pos: position to start writing to.
block_size: the maximum amount of data, in bytes, to read and write at a time
            (0x100000 is 1MiB).

"""
    f.seek(pos)
    with open(source, 'rb') as f_src:
        while True:
            data = f_src.read(block_size)
            if data:
                f.write(data)
            else:
                # nothing left to read
                break

def tree_from_dir (root, walk_iter = None):
    """Build a tree from a directory on the real filesystem.

This returns a dict in the same format as the tree attribute of GCFS objects.
That is, you can place it directly in such a tree to import lots of files.

"""
    tree = {}
    if walk_iter is None:
        walk_iter = os.walk(root)
    path, dirs, files = next(walk_iter)
    # files
    tree[None] = [(f, path + sep + f) for f in files]
    # dirs
    for d in dirs:
        tree[(d, None)] = tree_from_dir(d, walk_iter)
    return tree


class GCFS:
    """Read from and make changes to a GameCube image's filesystem.

To make changes to the tree, edit data in the tree attribute directly.  To undo
all changes, call the build_tree method.  The entries and names attributes
reflect what is actually in the image, and will only change when the write
method is called.

To import a directory tree from the real filesystem, use the tree_from_dir
function in this module and place the result in the tree attribute, or
replace the whole tree if you want to import an entire GameCube filesystem.

    CONSTRUCTOR

GCFS(fn)

fn: file path to the image file.

    METHODS

build_tree
get_info
get_extra_files
extract_extra_files [NOT IMPLEMENTED]
extract
write
compress [NOT IMPLEMENTED]

    ATTRIBUTES

fs_start: position in the image at which the filesystem starts.
fst_size: image's filesystem table (includes string table) size in bytes.
num_entries: number of entries in the filesystem.
str_start: position in the image at which the string table starts.
entries: a list of file table entries; each is an
         (is_dir, str_start, start, size) tuple, where:
    is_dir: whether this is a directory.
    str_start: offset of this entry's name in the string table.
    start: offset of this file in the filesystem, or position of this
           directory's parent directory in the table (first entry is 1, root
           directory is 0).
    size: file size in bytes, or for a directory, position of the next
          file/directory in the table that is not a child (or child of a child,
          etc.) of this one.  The root entry is not included.  Files (and
          directories) follow the directory they are in.
names: a list of filenames corresponding to the entries.
tree: a dict representing the root directory.  Each directory is a dict whose
      keys are directory identifiers for child directories, and with None the
      key for a list of file identifiers.  That is:

    {id1: {id2: {...}, ...}, ..., None: [id3, ...]}

      In each case, an identifier is (name, index), where:
    name: the directory/file's (current) name.
    index: the index in the entries list if the file/directory is already in
           the image's filesystem, else (for items yet to be added) None for a
           directory, or the real filesystem path for a file.
"""

    def __init__ (self, fn):
        self.fn = str(fn)
        # read data from the disk
        with open(self.fn, 'rb') as f:
            self.fs_start = fs_start = read(f, 0x424, 0x4, True)
            self.fst_size = read(f, 0x428, 0x4, True)
            self.num_entries = read(f, self.fs_start + 0x8, 0x4, True)
            self.str_start = str_start = self.fs_start + self.num_entries * 0xc
            # get file data
            self.entries = entries = []
            for i in range(1, self.num_entries):
                # get entry offset
                entry_offset = fs_start + i * 0xc
                # is_dir, str_offset, start, size
                args = ((0x0, 0x1), (0x1, 0x3), (0x4, 0x4), (0x8, 0x4))
                data = [read(f, entry_offset + offset, size, True)
                        for offset, size in args]
                data[0] = bool(data[0])
                entries.append(tuple(data))
            # get filenames
            self.names = names = []
            for entry in entries:
                # only read 512 chars for safety
                name = read(f, str_start + entry[1], 0x200, False, b'\0', 0x20)
                names.append(_decode(name))
            # build tree
            self.tree = self.build_tree()

    def _tree_size (self, tree):
        """Get the number of children in a tree."""
        size = 0
        for k, v in tree.items():
            if k is None:
                # files
                size += len(v)
            else:
                # dir
                size += 1 + self._tree_size(v)
        return size

    def build_tree (self, store = True, start = 0, end = None):
        """Build the directory tree from the current entries list.

build_tree(store = True, start = 0[, end]) -> tree

store: whether to store the built tree in the tree attribute.
start: the entry to start at.
end: the index of the entry to stop at (this one is not included).  Defaults to
     len(entries).

tree: the built tree.

"""
        entries = self.entries
        names = self.names
        start = max(start, 0)
        if end is None:
            end = len(entries)
        end = min(end, len(entries))
        # create tree with empty file list
        children = []
        tree = {None: children}
        # populate it
        i = start
        while i < end:
            is_dir, str_offset, start, size = entries[i]
            name = names[i]
            if is_dir:
                # build as a separate tree
                tree[(name, i)] = self.build_tree(False, i + 1, size - 1)
                i = size - 1
            else:
                # add file list
                children.append((name, i))
                i += 1
        if store:
            self.tree = tree
        return tree

    def changed (self):
        """Return whether changes have been made since the last write."""
        return self.tree != self.build_tree(False)

    def get_info (self):
        """Get basic information about a GameCube image.

Returns a dict containing 'code', 'version' (int), 'name' and
'apploader version'.  Strings are bytes objects.

"""
        fields = (
            ('code', 0x0, 0x4),
            ('version', 0x7, 0x1, True),
            # unlikely to have a game name longer than 256 characters
            ('name', 0x20, 0x100, False, b'\0', 0x30),
            ('apploader version', 0x2440, 0xa)
        )
        data = {}
        with open(self.fn, 'rb') as f:
            for name, *args in fields:
                data[name] = read(f, *args)
        return data

    def get_extra_files (self):
        """Get a list of files in the image that aren't in the filesystem.

Each file is a (name, start, size) tuple.

"""
        with open(self.fn, 'rb') as f:
            appldr_size = read(f, 0x2454, 0x4, True)
        return [('boot.bin', 0x0, 0x440), ('bi2.bin', 0x440, 0x2000),
                ('appldr.bin', 0x2440, 0x2440 + appldr_size)]

    def _extract (self, f, start, size, dest, block_size = 0x100000,
                  overwrite = False):
        """Copy data from the disk image to a file.

_extract(f, start, size, dest, block_size = 0x100000, overwrite = False)
    -> success

f: the disk image opened in binary mode.
start: position to start reading from.
size: amount of data to read.
dest: file to extract to.
block_size: the maximum amount of data, in bytes, to read and write at a time
            (0x100000 is 1MiB).
overwrite: whether to overwrite the file if it exists (if False and the file
           exists, success will be False).

success: whether the file could be created.

"""
        if not overwrite and os.path.exists(dest):
            return False
        try:
            with open(dest, 'wb') as f_dest:
                f.seek(start)
                # copy data
                while size > 0:
                    amount = min(size, block_size)
                    data = f.read(amount)
                    size -= amount
                    f_dest.write(data)
        except IOError:
            return False
        else:
            return True

    def extract_extra_files (self, *files, block_size = 0x100000,
                             overwrite = False):
        """Extract files from the image that aren't in the filesystem.

extract_extra_files(*files, block_size = 0x100000, overwrite = False)
    -> success

files: the files to extract, echa a (name, target) tuple, where:
    name: the file's name as returned by get_extra_files.
    target: the path on the real filesystem to extract this file to.  This may
            also be a file object to write to (open in binary mode).
block_size: the maximum amount of data, in bytes, to read and write at a time
            (0x100000 is 1MiB).  This is a keyword-only argument.
overwrite: whether to overwrite files if they exist (if False and a file
           exists, its returned success will be False).

success: a list of bools corresponding to the given files, each indicating
         whether the file could be created.  Failure can occur if the file
         already exists or if the target path is invalid.

Any missing intermediate directories will be created.

"""
        # TODO
        return NotImplemented

    def extract (self, *files, block_size = 0x100000, overwrite = False):
        """Extract files from the filesystem.

extract(*files, block_size = 0x100000, overwrite = False) -> failed

files: the files and directories to extract, each an (index, target) tuple,
       where:
    index: the index of the file/directory in this GCFS instance's entries
           attribute.  Use -1 (or any other number less than 0) for the root
           directory.
    target: the path on the real filesystem to extract this file/directory to.
block_size: the maximum amount of data, in bytes, to read and write at a time
            (0x100000 is 1MiB).  This is a keyword-only argument.
overwrite: whether to overwrite files if they exist and ignore existing
           directories (if False and a file/directory exists, it will be in the
           failed list).

failed: a list of files and directories that could not be created.  This is in
        the same format as the given files, but may include ones not given (if
        a given directory could be created, but not one of its children).
        Failure can occur if the file/directory already exists or if the target
        path is invalid.

Like the entries attribute itself, this method does not take into account
modifications made to the tree attribute that have not been written to the
image (using the write method).

Directories are extracted recursively.

"""
        entries = self.entries
        names = self.names
        failed = []
        # files might be a non-list iterable, and we might need to append to it
        files = list(files)
        with open(self.fn, 'rb') as f:
            while files:
                i, dest, *args = files[0]
                # remove trailing separator
                s = (os.sep, sep)[isinstance(dest, bytes)]
                while dest.endswith(s):
                    dest = dest[:-1]
                # get entry data
                if i < 0:
                    # root
                    is_dir = True
                else:
                    is_dir, str_start, start, size = entries[i]
                if is_dir:
                    # create dir
                    try:
                        mkdir(dest)
                    except OSError as e:
                        if not overwrite or e.errno != 17:
                            # unknown error
                            files.pop(0)
                            failed.append((i, dest))
                            continue
                        # else already exists and we want to ignore this
                    # need a vanilla tree
                    if args:
                        tree = args[0]
                    else:
                        # we don't already have one: create it
                        if i < 0:
                            # root
                            tree = self.build_tree(False)
                        else:
                            tree = self.build_tree(False, i, i + 1)
                            tree = tree[(names[i], i)]
                    # add children to extract list
                    # files
                    for name, j in reversed(list(tree[None])):
                        files.insert(1, (j, dest + sep + name))
                    del tree[None]
                    # dirs
                    dirs = reversed(list(tree.items()))
                    for (name, j), child_tree in dirs:
                        files.insert(1, (j, dest + sep + name, child_tree))
                else:
                    # extract file
                    if not self._extract(f, start, size, dest, block_size,
                                         overwrite):
                        failed.append((i, dest))
                files.pop(0)
        return failed

    def write (self, block_size = 0x100000, temp_dir = None):
        """Write the current tree to the image.

write(block_size = 0x100000[, temp_dir])

block_size: the maximum amount of data, in bytes, to read and write at a time
            (0x100000 is 1MiB).  This is used when copying data to the image.
temp_dir: a directory to store temporary files in for some operations.

This function looks at the current state of the tree and amends the filesystem
in the GameCube image to be the same, copying files from the real filesystem as
necessary.  The algorithm tries not to increase the size of the disk image, but
it may be necessary.

It's probably a good idea to back up first...

"""
        old_entries = self.entries
        old_names = self.names
        tree = self.tree
        # compile new filesystem/string tables
        tree[None] = [f + (True,) for f in tree[None]]
        entries = []
        old_files = []
        new_files = []
        names = []
        str_start = 0
        dirs = []
        parent_indices = {id(tree): 0}
        done = False
        sort_key = lambda c: c[0].upper()
        while True:
            while len(tree) == 1 and not tree[None]:
                # go up one dir
                if dirs:
                    tree = dirs.pop()
                else:
                    done = True
                    break
            if done:
                break
            # find next file or dir alphabetically
            children = tree[None]
            # += causes the original list to be modified
            children = children + list(k for k in tree if k is not None)
            child = min(children, key = sort_key)
            if len(child) == 3:
                # file
                name, old_i = child[:2]
                names.append(name)
                i = len(entries)
                if isinstance(old_i, int):
                    # existing file
                    start, size = old_entries[old_i][2:]
                    old_files.append((start, i, old_i, size))
                else:
                    # new file: get size
                    fn = old_i
                    start = fn
                    if not os.path.isfile(fn):
                        err = '\'{}\' is not a valid file'
                        raise ValueError(err.format(fn))
                    size = os.path.getsize(fn)
                    # put in new file list
                    new_files.append((size, i))
                entries.append((False, str_start, start, size))
                # update tree
                tree[None].remove(child)
            else:
                assert len(child) == 2
                # dir
                new_tree = tree[child]
                dirs.append(tree)
                parent = parent_indices[id(tree)]
                del tree[child]
                tree = new_tree
                tree[None] = [f + (True,) for f in tree[None]]
                name = child[0]
                names.append(name)
                next_index = len(entries) + 2 + self._tree_size(tree)
                entries.append((True, str_start, parent, next_index))
                parent_indices[id(tree)] = len(entries)
            # terminate with a null byte
            str_start += len(_encode(name)) + 1
        # sort existing files by position
        old_files.sort()
        # get start of actual file data (str_start is now the string table
        # size)
        data_start = self.fs_start + (1 + len(entries)) * 0xc + str_start
        # get existing files overwritten by the filesystem/string tables and
        # extract them to a temp dir
        temp_dir = tempfile.mkdtemp(prefix = 'gcutil', dir = temp_dir)
        while old_files and old_files[0][0] < data_start:
            # move from old_files to new_files
            start, i, old_i, size = old_files.pop(0)
            new_files.append((size, i))
            # extract
            f = tempfile.NamedTemporaryFile(prefix = '', dir = temp_dir,
                                            delete = False)
            fn = f.name
            f.close()
            failed = self.extract((old_i, fn), block_size = block_size,
                                  overwrite = True)
            if failed:
                # cleanup
                rmtree(temp_dir)
                self.build_tree()
                msg = 'couldn\'t extract to a temporary file ({})'
                raise IOError(msg.format(failed[0][1]))
            # change entry
            entries[i] = (False, entries[i][1], fn, size)
        # copy new files to the image
        if new_files:
            # get free space in the filesystem
            free = []
            l = [(data_start, None, None, 0)] + old_files
            for j in range(len(l) - 1):
                start = l[j][0] + l[j][3]
                end = l[j + 1][0]
                gap = end - start
                if gap > 0:
                    free.append((gap, start))
            # fit new files to gaps: sort both by size
            if old_files:
                last_file = old_files[-1]
                end = last_file[0] + last_file[3]
            else:
                end = data_start
            new_files.sort(reverse = True)
            free.sort(reverse = True)
            # take the largest file
            for file_i, (size, i) in enumerate(new_files):
                # and put it in the smallest possible gap
                gap_i = -1
                for gap_i, (gap, gap_start) in enumerate(free):
                    if gap < size:
                        gap_i -= 1
                        break
                if gap_i < 0:
                    # either no gaps or won't fit in any: place at the end
                    start = end
                    end += size
                else:
                    start = free[gap_i][1]
                    # alter the gap entry
                    gap, gap_start = free[gap_i]
                    if gap == size:
                        free.pop(gap_i)
                    else:
                        free[gap_i] = (gap - size, gap_start + size)
                        free.sort(reverse = True)
                new_files[file_i] = (start, i)
            # copy
            with open(self.fn, 'r+b') as f:
                for start, i in new_files:
                    str_start, fn, size = entries[i][1:]
                    copy(fn, f, start, block_size)
                    entries[i] = (False, str_start, start, size)
            last_new = max(new_files)
        # clean up temp dir
        rmtree(temp_dir)
        # get new fst_size, num_entries, str_start
        self.fst_size = data_start - self.fs_start
        self.num_entries = len(entries) + 1
        self.str_start = self.fs_start + self.num_entries * 0xc
        # write new fst_size and filesystem/string tables to the image
        self.entries = entries
        self.names = names
        with open(self.fn, 'r+b') as f:
            write(self.fst_size, f, 0x428, 0x4)
            root = (True, 0, 0, self.num_entries)
            args = ((0x0, 0x1), (0x1, 0x3), (0x4, 0x4), (0x8, 0x4))
            offset = self.fs_start
            for k, entry in enumerate([root] + self.entries):
                for data, (pos, size) in zip(entry, args):
                    write(int(data), f, offset + pos, size) # is_dir is bool
                offset += 0xc
            pos = self.str_start
            for name in names:
                name = _encode(name)
                write(name + b'\0', f, pos)
                pos += len(name) + 1
        # build new tree
        self.build_tree()

    def compress (self, block_size = 0x100000):
        """Compress the image.

compress(block_size = 0x100000)

block_size: the maximum amount of data, in bytes, to read and write at a time
            (0x100000 is 1MiB).

This function removes all free space in the image's filesystem to make it
smaller.  GameCube images often have a load of free space between the
filesystem string table and the file data, sometimes hundreds of MiB.  This
will also remove free space between files that may have been opened up by
deletions or other editing.

This will effectively read the entire image to another file in the same
directory, then delete the original and rename the new image.  For this reason,
it can take some time, and can require as much as 1.4GiB free space on the disk
on which the image is stored.

Unless you're making a _lot_ of changes to the image, it is generally not
necessary or useful to do this more than once, unless you're obsessive
compulsive or something.

Back up first.  Please.

"""
        # TODO
        return NotImplemented