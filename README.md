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

class `vss_delta_record`
- represents delta (difference) of the previous revision of the file from the next revision.

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

`print(self, fd)`
- The function prints the record data to `fd` file object as text formatted lines.
The base class only calls `self.header.print(fd)` to print the record header.

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

### class `vss_project_item_file`

This class manages project item files, which store directory revisions. It has the following methods:

`__init__(self, database, filename:str)`
- constructor. Invokes vss_item_file constructor.

`is_project(self)`
- returns `True`.

### class `vss_file_item_file`

This class manages file item files, which store file revisions. It has the following methods:

`__init__(self, database, filename:str)`
- constructor. Invokes vss_item_file constructor.

`is_project(self)`
- returns `False`.

`is_locked(self)`, `is_binary(self)`, `is_latest_only(self)`, `is_shared(self)`, `is_checked_out(self)`
- return `True` or `False`, depending on flag set in the header.
