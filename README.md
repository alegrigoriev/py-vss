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
