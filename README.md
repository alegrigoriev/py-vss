# py-vss - Python framework for reading Microsoft Visual SourceSafe databases

This framework reads and parses Microsoft Visual SourceSafe (VSS) databases (repositories),
prints human-readable dump of its contents, and also produces a changelist to feed into a different source
control system.

The framework is modeled in part after Vss2Git project by Trevor Robinson at https://github.com/trevorr/vss2git.

It's written in Python, and requires Python interpreter version at least 3.9 to run. It's been tested with CPython.

## How is it licensed?

py-vss is open-source software, licensed under the [Apache License, Version 2.0](LICENSE).
Accordingly, **any use of the software is at your own risk**.

# Framework

The framework consist of low level classes and functions to read files and records of a VSS database (repository).

## File `VSS/vss_record.py`

File `VSS/vss_record.py` contains the following classes and functions:

class `vss_record_reader`
- provides methods to read fields of various size from a `bytes` buffer.
Provides a function to clone the reader to cover only a slice of the original buffer.

class `vss_record_header`
- describes a common header of VSS file records. Provides methods to read it and print to a text file.
An 8 byte VSS record header contains:
	- 32 bit record length (not including the 8 byte header);
	- 16 bit signature (record type) as 2 ASCII characters.
The signature makes more sense if you look at it as a C character literal.
For example, a comment record signature `'CM'` is stored as characters `"MC"`;
	- 16 bit CRC: produced by XOR of upper 16 bit and lower 16 bit of CRC-32 of the record data (which follows the header);

class `vss_record`
- base class for all VSS file record classes.

function `zero_terminated(src)`
- return a copy of the `src` object truncated to the first zero byte.

function `timestamp_to_datetime(timestamp:int)`
- converts a 32 bit timestamp, as time since 00:00 of 01/01/1970 in seconds, into `datetime.datetime` object.

class `vss_branch_record`
- represents a record describing a branch of this file.
Multiple branch records may be present, linked by `prev_branch_offset` field.

class `vss_checkout_record`
- represents a record describing the location and revision of a file checkout.
VSS keeps track of checkouts to be able to merge the file changes onto the most recent version of the file.

class `vss_comment_record`
- represents a revision comment string. The string is stored zero-terminated.
Unlike all other record types, its header doesn't contain a CRC, storing a zero instead.
VSS allows to edit the comment after the fact.

class `vss_project_record`
- points to projects (directories) this file belongs to.
A file can be cloned (shared) to multiple projects (directories).
Multiple project records can be present, linked by `prev_project_offset` field.

class `vss_delta_operation`
- implements an element of delta array. Implements methods to read and apply such an element.

class `vss_delta_record`
- represents delta (difference) of the previous revision of the file from the next revision.
Implements a function to apply the delta array to the data blob.

### class `vss_record_reader`

Class `vss_record_reader` defines the following methods:

`__init__(self, data:bytes, length:int=-1, slice_offset:int=None, encoding='utf-8')`
- constructs the object from a `data` blob of bytes, with `length` at `slice_offset`,
and `encoding` for byte data to Unicode conversion.

`clone(self, additional_offset:int=0, length:int=None)`
- returns a copy of the reader object, with data starting at `additional_offset` from the current read offset,
and covering `length`, or the rest of the original reader object, if `length` is omitted.

`crc16(self, length=-1)`
- calculate 16 bit CRC as XOR of upper 16 bit and lower 16 bit of CRC-32 of the reader data,
starting with the current offset, and over `length` of data (or the rest of the reader, if omitted).

`check_read(self, length:int)`
- checks if there's `length` bytes to read from the current offset.
If `length` overruns the remaining data, `EndOfBufferException` is raised.

`read_bytes(self, length:int)->bytes`
- calls `check_read(length)`, then reads the requested `length` as a byte array,
and returns it as `bytes` object. Current read offset is advanced by the length read.

`read_bytes_at(self, offset:int, length:int)->bytes`
- validates `offset` and `length`,
then reads the requested `length` at `offset` as a byte array,
and returns it as `bytes` object. Current read offset is *not* advanced by the length read.

`read_int16(self, unaligned=False)`, `read_uint16(self, unaligned=False)`
- calls `check_read`, then reads 2 bytes as a little endian signed or unsigned integer,
Current read offset is advanced by 2.
If `unaligned` is `False`, and the current read position is not aligned by 2,
`UnalignedReadException` is raised.

`read_int32(self, unaligned=False)`, `read_uint32(self, unaligned=False)`
- calls `check_read`, then reads 4 bytes as a little endian signed or unsigned integer,
Current read offset is advanced by 4.
If `unaligned` is `False`, and the current read position is not aligned by 4,
`UnalignedReadException` is raised.

`skip(self, skip_bytes:int)`
- advances the read position by `skip_bytes`.
If this would cause the read position to move outside the valid buffer, `EndOfBufferException` is raised.

`remaining(self)`
- returns number of bytes remaining in the buffer after the current read position.

`read_byte_string(self, length:int=-1)->bytes`
- reads zero-terminated string as `bytes` object, up to `length`. If length is omitted,
the rest of the buffer is read. Current read offset is advanced by `length`.
The terminating zero byte is not a part of the returned object.

`read_byte_string_at(self, offset:int, length:int=-1)->bytes`
- reads zero-terminated string as `bytes` object,
up to `length` at `offset` as a byte array.
If length is omitted, the rest of the buffer is read. Current read offset is *not* advanced.
The terminating zero byte is not a part of the returned object.

`decode(self, s)`
- returns `s.decode(self.encoding)` to decode a `bytes` string from encoding-specific character set
(`encoding` argument saved at construction) to an Unicode `str` object.

`read_string(self, length:int=-1)`
- reads a zero-terminated byte string, then returns its Unicode representation as an `str` object.

`unpack(self, unpack_format:str|struct.Struct)`
- reads a tuple of multiple items from the buffer, as specified either by a format string,
or by a pre-compiled `struct.Strict` object. Current read offset is advanced by total length of items read.
See `struct.Strict` Python library documentation for the unpack format description.

`unpack_at(self, offset, unpack_format:str|struct.Struct)`
- reads a tuple of multiple items from the buffer, as specified either by a format string,
or by a pre-compiled `struct.Struct` object. Current read offset is *not* advanced.
See `struct.Struct` Python library documentation for the unpack format description.

`read_name(self)`
- reads a `vss_name` object, stored as 16 bit `flags`, 34 bytes zero-terminated name,
32 bit `name_offset` - optional offset of additional short/long names.

### class `vss_record`

It's a base class for all VSS file record classes. It contains the following methods:

`__init__(self, header:vss_record_header)`
- class constructor. It saves the reference to the header,
and also gets the reader object from the header and saves it as `self.reader`.
Constructors for all derived classes should have the `header` argument.

`read(self)`
- The function reads the record, using `self.reader`.
The base class does nothing; derived classes read fields of their actual records.

`print(self, fd, indent:str='', verbose:VerboseFlags)`
- The function prints the record data to `fd` file object as text formatted lines.
The base class only calls `self.header.print(fd, indent)` to print the record header.

`classmethod create_record(record_class_factory, record_header)`
- This class method can be called to create a record class instance based on the given `record_header`.
The default implementation only uses `record_class_factory` as the class to create an instance.

`classmethod valid_record_class(record_class_factory, record)`
- This class method can be called to validate the `record` is a valid record class instance created by `record_class_factory`.
The default implementation only checks that `record` is an instance of `record_class_factory`.

## File `VSS/vss_database.py`

File `VSS/vss_database.py` contains the following classes:

class `simple_ini_parser`
- implements a parser for `srcsafe.ini` file. Unlike common INI file format, `srcsafe.ini` file doesn't have sections.

class `vss_database`
- implements upper level functions of VSS database (repository).

### class `simple_ini_parser`

The class constructor takes the INI file pathname as its only argument.

The class method `get(key, default)` returns the value stored by the given `key`,
or the `default` value, if the key is not present in the file.

### class `vss_database`

The class defines the following methods:

`__init__(self, path:str, encoding='mbcs')`
- constructor, which takes the path to the repository root directory,
and an optional `encoding` argument, to specify locale or encoding for filenames in the repository.
VSS always uses the local ANSI code page, which is `mbcs` (Multi-Byte Character Set) encoding.

`get_data_path(self, physical_name, first_letter_subdirectory=True)`
- returns the full path for a database file, built from its `physical name`.
The database files are usually located under `data/` subdirectory,
which can be changed by the `Data_Path` value in the INI file.

Metadata and data files with 8-letter names and an optional single-letter extension
are located under a single-letter subdirectory under `data`.
For such files, `first_letter_subdirectory` argument should be left at `True`.
For all  other files located immediately under `data`, `first_letter_subdirectory` argument needs to be explicitly set as `False`.

`open_data_file(self, physical_name, first_letter_subdirectory=True)`
- returns a file object for the given file.
If the file is not present, the function raises an exception `VssFileNotFoundException`.

`open_records_file(self, file_class, physical_name, first_letter_subdirectory=False)`
- returns a new object of the class `file_class` (usually derived from `vss_record_file`),
or returns an existing one from cache for the given `physical_name`.

`get_long_name(self, name)`
- make a long (full) name from an object of `vss_name` type, which contains an optional offset in the name file for a name record.
`vss_name` object read from a file can only have names up to 34 bytes long.

`open_root_project(self, project_class, recursive=False)`
- opens the root project as the instance of class `project_class` (usually`vss_project`).
If `recursive`, then the whole project tree is built.

`get_project_tree(self)`
- return the project tree of `vss_project` type.

## File `VSS/vss_record_file.py`

The file implements class `vss_record_file`.

### class `vss_record_file`

The class has the following methods:

`__init__(self, database:vss_database, filename:str, first_letter_subdirectory=True)`
- the constructor opens the given file by its filename and the optional `first_letter_subdirectory`
(see `vss_database.get_data_path` for its meaning), and reads all its data into an internal buffer.

`read_record(self, record_factory, offset:int=None, ignore_unknown:bool=False)`
- reads the file record from the internal buffer at the given `offset` in the file,
or at the current read position after the previous `read_record` call.

	The function calls `create_record` method of `record_factory` which returns an object of some record class.
	If `record_factory` doesn't recognize this record type/signature, the function either returns `None`
	if `ignore_unknown` is `True`, or raises `UnrecognizedRecordException` otherwise.

`read_all_records(self, record_factory, offset=None, last_offset=None, ignore_unknown:bool=False)`
- reads all records, using `record_factory` to create the record objects, and stores them in a dictionary
by the record offset.
Optional argument `offset` specified the file offset to start the reading.
Optional argument `last_offset` specifies the file offset to stop the reading.  
The function returns an iterator for all read record objects in the file order.

`get_record(self, offset:int, record_class=None)`
- get a previously read record object from the dictionary by its offset.
An optional `record_class` argument can be provided, to validate the record belonging to the class.

## File `VSS/vss_record_factory.py`

The file implements class `vss_item_record_factory`, which is used to read records of a VSS item file
and create objects of record class based on the record signature.

### class `vss_item_record_factory`

The class implements two factory methods:

`classmethod create_record(cls, record_header)`
- This static method is called to create a record class instance based on the given `record_header`.
The class implementation creates one of `vss_comment_record`, `vss_checkout_record`, `vss_project_record`,
`vss_branch_record`, `vss_revision_record`, `vss_delta_record` objects, based on `record_header.signature`.  
Note that `cls` argument when this function is called is `vss_item_record_factory`,
since it's a class method.

`classmethod valid_record_class(cls, record)`
- This static method is called to validate the `record` is a valid record class instance created by this factory class.
Note that `cls` argument when this function is called is `vss_item_record_factory`,
since it's a class method.

## File `VSS/vss_revision_record.py`

The file contains enum `VssRevisionAction` which describes codes for revision actions,
and the base class `vss_revision_record` which describes the generic structure for a revision record.

class `vss_revision_record_factory`
- implements a record factory, which creates one of revision record classes based on the `action` field in the record.

### class `vss_revision_record`

The class defines fields for the base revision record (log entry),
and the `read` function to read it from the record reader.

The following classes are derived from `vss_revision_record`:

class `vss_label_revision_record`
- encapsulates a record for label action.

class `vss_common_revision_record`
- encapsulates a record for several actions.
The record contains additional logical and physical name of an item it refers to.

class `vss_destroy_revision_record`
- encapsulates a record for project or file destroy action.

class `vss_rename_revision_record`
- encapsulates a record for project or file rename action.

class `vss_move_revision_record`
- encapsulates a record for project or file destroy action.

class `vss_share_revision_record`
- encapsulates a record for a file share, pin and unpin action.

class `vss_branch_revision_record`
- encapsulates a record for file branch action.

class `vss_checkin_revision_record`
- encapsulates a record for file check-in action.

class `vss_archive_restore_revision_record`
- encapsulates a record for project or file archive or restore action.

## File `VSS/vss_name_file.py`

The file implements class `vss_name_file` along with record classes used in the name file.

### class `vss_name_file`

This class manages the VSS name file, which contains records to store various flavors of
file names, when the default reserved length 34 bytes for a name is insufficient.

It implements the following methods:

`__init__(self, database:vss_database, filename:str)`
- constructor. Opens the file by its filename (default `names.dat`) under `data/` database directory,
and preloads the record dictionary with `vss_name_record` records.

`get_name_record(self, name_offset)`
- gets a name record of type `vss_name_record` from the dictionary by its offset in the file.

## File `VSS/vss_item_file.py`

The file implements classes to manage VSS item files. The item files contain information, including log entries, about projects (directories) and
files in these directories.

This file contains the following classes:

class `vss_item_file`
- a common class to manage item files;

class `vss_project_item_file`
- a class to manage project (directory) item file.

class `vss_file_item_file`
- a class to manage file item file.

### class `vss_item_file`

This is the base class for file and project item file classes. It has the following methods:

`__init__(self, database, filename:str, header_record_class)`
- constructor. Reads the file header of `header_record_class`, and then reads all records,
using `vss_item_record_factory` record factory.

`get_data_file_name(self)`
- makes the data file name from its own filename and datafile extension taken from the header.
The datafile extension is a single letter which alternates at every update to the data file.

`all_revisions(self)`
- returns an iterator for all revisions, in chronological order

`get_last_revision_num(self)`
- returns the last revision for this item file

### class `vss_project_item_file`

This class manages project item files, which store directory revisions. It has the following methods:

`__init__(self, database, filename:str)`
- constructor. Invokes vss_item_file constructor.

`is_project(self)`
- returns `True`.

`build_revisions(self)`
- internal method to make a revision array by calling `vss_project_revision_factory` function for each revision record (log entry).

`get_revision(self, version:int)`
- returns a vss_revision object for the given version number.
If the version number is out of bounds, it raises `ArgumentOutOfRangeException` exception.

Methods listed below are used for item position reconstruction.
The program rebuilds an array of items in a directory by applying changes caused by project revisions,
from first (oldest) to last (the most recent). Each revision then knows an index of an item which it applies to.

An item in the array is just a `vss_full_name` object, which consists of the item's logical name,
physical name, indexing name, and long (actual) name.

A logical name is the name by which an item is referred in revisions (as in `vss_name` object).
In some cases it may be empty.

An indexing name is item's logical name, converted to the locale-specific lowercase,
in locale-specific multi-byte encoding. Simple byte comparison is used for sort.

A physical name refers to the database file name (8 uppercase letters).

A long name is the actual file name in the checkout tree.

The items' array is sorted by their indexing name.
Multiple items can have same indexing name, but they will have distinct physical name.
Items with same indexing name are not sorted by their physical name.

`find_item_index(self, full_name)`
- Find item index in the sorted array by indexing name and physical name, which are part of `full_name`.
If an item is not present, the function returns the index of the first element with same or greater logical name,
which is an insertion point for the new item.

`find_item(self, full_name)`
- Find item index in the sorted array by indexing name and physical name, which are part of `full_name`.
If a matching item is not present, return -1.

`remove_item(self, full_name)`
- remove the item from the sorted array by indexing name and physical name, which are part of `full_name`.
Returns a tuple of `(item_idx, item)`, or `(item_idx, None)` if the name not found.

`remove_item_by_idx(self, item_idx)`
- remove the item from the sorted array by index in the array.
Returns a tuple of `(item_idx, item)`, or `(item_idx, None)` if the index is invalid.

`add_item(self, full_name)`
- add an item to the sorted array by indexing name and physical name, which are part of `full_name`.

`get_item(self, item_idx)`
- returns an item by its index in the array.

`def insert_item(self, item_idx, full_name)`
- insert an item (`full_name`) at the given position.

### class `vss_file_item_file`

This class manages file item files, which store file revisions. It has the following methods:

`__init__(self, database, filename:str)`
- constructor. Invokes vss_item_file constructor.

`is_project(self)`
- returns `False`.

`is_locked(self)`, `is_binary(self)`, `is_latest_only(self)`, `is_shared(self)`, `is_checked_out(self)`
- return `True` or `False`, depending on flag set in the header.

`build_revisions(self, data:bytes)`
- internal method to make a revision array by calling `vss_file_revision_factory` function for each revision record (log entry).
`data` if the final data blob.
The function returns the resulting data blob for the very first revision (possibly at the branch point).

`get_revision(self, version:int)`
- returns a vss_revision object for the given version number. If the version number is out of bounds,
it raises `ArgumentOutOfRangeException` exception. If the version number precedes the branching point,
it opens the branch parent file and forwards the call to that file.

## File `VSS/vss_item.py`

The file contains classes to represent logical items: projects (directories) and files in those
projects.

The following classes are defined:

class `vss_item`
- common base class for project item and file item;

class `vss_project`
- manages a logical directory (project).

class `vss_file`
- manages a logical file.

### class `vss_item`

The class is used only to derive `vss_project` and `vss_file` classes. It implements the following methods:

`__init__(self, database:vss_database, item_file_class, physical_name:str, logical_name:str, flags:int)`
- constructor.

`is_deleted(self)`
- return `True` if the item marked as deleted. In VSS, items are not purged from a directory, unless deleted permanently.

`make_full_path(self, sub_item_name:str='')`
- return the full path for a sub-item of this item.

### class `vss_project`

The class is derived from `vss_item` and implements the following methods:

`__init__(self, database:vss_database, physical_name:str, logical_name:str, flags:int, recursive=True)`
- constructor. If `recursive`, also creates the sub-items (projects and files).

`is_project(self)`
- returns `True`.

`all_items(self)`
- returns an iterator of all child items (projects and files).

### class `vss_file`

The class is derived from `vss_item` and implements the following methods:

`__init__(self, database:vss_database, physical_name:str, logical_name:str, flags:int, pinned_version:int=0)`
- constructor.

`is_project(self)`
- returns `False`.

`is_pinned(self)`, `is_locked(self)`, `is_binary(self)`, `is_latest_only(self)`, `is_shared(self)`, `is_checked_out(self)`
- Returns flags state of its item file.

## File `VSS/vss_revision.py`

The file contains classes to represent revision objects of different type,
and also factory functions to make an action-specific revision object
from a revision record.

The following classes and functions are defined:

class `vss_full_name`
- the class encapsulates name information for a VSS item: physical name for the item file.

class `vss_revision`
- common base class for action-specific revision classes.

function `vss_file_revision_factory(record:vss_revision_record, database,
item_file:vss_file_item_file)`
- factory function to make a _file_ item revision object out of a revision record.

function `vss_project_revision_factory(record:vss_revision_record, database,
item_file:vss_project_item_file)`
- factory function to make a _project_ item revision object out of a revision record.

### class `vss_revision`

It's a base class which encapsulates logical data of a revision.

The class defines the following methods:

`__init__(self, record:vss_revision_record, database, item_file:vss_item_file)`
- class constructor. It can fetch additional records for comment and label comment.

`apply_to_project_items(self, item_file:vss_project_item_file)`
- the function is invoked for item position reconstruction.
It normally invokes methods of `item_file`, which is an object of class `vss_project_item_file`,
and saves the returned item index.

`set_revision_data(self, data:bytes)`
- sets the data blob for this _file_ revision, and returns the data blob to be used for the preceding revision.
The base class function only returns same `data` blob.
`vss_checkin_revision` applies the delta record to the blob to produce the blob for previous revision.

`print(self, fd, indent:str='', verbose:VerboseFlags)`
- The function prints the revision data to `fd` file object as text formatted lines.
The base class prints a generic revision header.

## File `VSS/vss_action.py`

The file contains class `vss_action` and various action-specific classes derived from it.

The file exports `create_file_action` and `create_project_action` functions,
which returns an action object of a class specific to the given revision action.

### class `vss_action`

This is the base class for all action classes. It defines the following class data items:

`ACTION_STR`
- a base string for building a human-readable action description.

`project_action`
- `True` for project action classes, `False` for file action classes.

The base class sets both to `NotImplemented`.

It also defines the following methods:

`__init__(self, revision:vss_revision, base_path:str, name:str='')`
- constructor. `base_path` provides the path name of a directory which contains this action.

`add_error_string(self, error_str)`
- adds the given error string to a list in this object, to be emitted to the actions log.

`__str__(self)`
- returns a string describing this action. The default implementation combines `ACTION_STR` and file name into a string.

### class `vss_named_action`

This class is derived from `vss_action` and provides a base class for various actions.

This class redefines the constructor as: `__init__(self, revision:vss_revision, base_path:str)`.

### Function `create_file_action`

This function, defined as `create_file_action(revision, base_path)` is an action factory,
which returns an action object of a specific class for the given `revision`.

### Function `create_project_action`

This function, defined as `create_project_action(revision, base_path)` is an action factory,
which returns an action object of a specific class for the given `revision`.

# Command line interface

Although the main use of this package is as a framework, the command line capability
is provided, for running VSS database analysis.

Command line is invoked by executing `vss_main.py` as:

```
python vss_main.py <database path> <options>
```

`vss_main.py` expects the VSS database (repository) directory path as an only argument,
and supports following command line options:

`--log <log filename>`
- log file pathname. By default, the log is sent to the standard output.

`--encoding=<encoding>`
- specifies an encoding (code page) for the database 8 bit text and file names. The default is **mbcs**,
which is an alias for the current Windows *Multi Byte Character Set* in Python runtime,
AKA *text encoding for non-Unicode programs*.
See https://learn.microsoft.com/en-us/windows/win32/intl/code-page-identifiers for more code page IDs.

`--root-project-file <root filename>`
- root file name. By default, the database root file is AAAAAAAA.
You can dump the database starting from other directory file, which you can find from the log.

## File `vss_main.py`

File `vss_main.py` provides a main function to run VSS database analysis from a command line.
