#   Copyright 2023 Alexandre Grigoriev
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

from __future__ import annotations
import sys
import struct

if sys.version_info < (3, 9):
	sys.exit("vss2git: This package requires Python 3.9+")

from .vss_exception import EndOfBufferException, UnalignedReadException, RecordCrcException, RecordNotFoundException

class crc32:
	# Make the CRC table
	POLY=0xEDB88320
	table=[]
	for i in range(256):
		value = i
		for j in range(8):
			if value & 1:
				value = POLY ^ (value >> 1)
			else:
				value >>= 1

		table.append(value)
		continue

	@staticmethod
	def calculate(data:bytes, initial=0,final=0, offset=0, length=-1):
		crc = initial
		if length < 0:
			length = len(data) - offset
		for i in range(offset, offset + length):
			crc = (crc >> 8) ^ crc32.table[0xFF & (crc ^ data[i])];
		return crc ^ final

def zero_terminated(src):
	zero_byte_pos = src.find(0)
	if zero_byte_pos >= 0:
		src = src[0:zero_byte_pos]
	return src

class vss_record_reader:
	# If the length argument is supplied, it means the length after 'slice_offset' in the buffer
	# If slice_offset is not specified, it's same as offset
	def __init__(self, data:bytes, length:int=-1, slice_offset:int=0, encoding='utf-8'):
		data_len = len(data)
		if length == -1:
			length = data_len - slice_offset

		if slice_offset > data_len:
			raise EndOfBufferException(
				"Attempted slice at offset 0x%X with only 0x%X bytes in buffer"
				% (slice_offset, data_len))

		data_len -= slice_offset
		if length > data_len:
			raise EndOfBufferException(
				"Attempted slice of 0x%X bytes with only 0x%X bytes remaining in buffer"
				% (length, data_len))

		self.data = data
		# Start of the record data in 'data'
		self.slice_offset = slice_offset
		# Current offset to read data, relative to 'slice_offset'
		self.offset = 0
		# length of data to read, starting from 'slice_offset'
		self.length = length
		self.encoding = encoding
		return

	def clone(self, additional_offset:int=0, length:int=None):
		offset = self.offset + additional_offset
		if offset > self.length:
			raise EndOfBufferException(
				"Attempted slice at offset 0x%X with only 0x%X bytes in buffer"
				% (offset, self.length))

		if length is None:
			length = self.length - offset
		elif length + offset > self.length:
			raise EndOfBufferException(
				"Attempted slice of 0x%X bytes with only 0x%X bytes remaining in buffer"
				% (length, self.length - offset))
		return vss_record_reader(self.data,
								slice_offset=offset+self.slice_offset,
								length=length,
								encoding=self.encoding)

	def crc16(self, length=-1):
		if length < 0:
			length = self.length - self.offset
		else:
			self.check_read(length)
		crc = crc32.calculate(self.data, offset=self.offset+self.slice_offset, length=length)
		return 0xFFFF & (crc ^ (crc >> 16))

	def check_read(self, length:int):
		if self.offset + length > self.length:
			raise EndOfBufferException(
				"Attempted read of %d bytes with only %d bytes remaining in buffer"
				% (length, self.length - self.offset))
		return

	def check_read_at(self, offset:int, length:int):
		if offset + length > self.length:
			raise EndOfBufferException(
				"Attempted read of %d bytes with only %d bytes remaining in buffer"
				% (length, self.length - offset))
		return

	def read_bytes(self, length:int)->bytes:
		self.check_read(length)
		offset = self.offset + self.slice_offset
		bytes_read = self.data[offset:offset+length]
		self.offset += length
		return bytes_read

	# Read without updating the current offset
	def read_bytes_at(self, offset:int, length:int)->bytes:
		self.check_read_at(offset, length)
		offset += self.slice_offset
		bytes_read = self.data[offset:offset+length]
		# Not advancing self.offset
		return bytes_read

	def read_int16(self, unaligned=False)->int:
		if not unaligned and (self.offset & 1):
			raise UnalignedReadException("Attempted read of 16-bit integer at unaligned offset %d" % (self.offset,))
		return int.from_bytes(self.read_bytes(2), byteorder='little', signed=True)

	def read_uint16(self, unaligned=False)->int:
		return 0xFFFF & self.read_int16(unaligned)

	# Read without updating the current offset (peek)
	def read_int16_at(self, offset:int, unaligned=False)->int:
		if not unaligned and ((self.offset + offset) & 1):
			raise UnalignedReadException("Attempted read of 16-bit integer at unaligned offset %d" % (self.offset + offset,))
		return int.from_bytes(self.read_bytes_at(offset, 2), byteorder='little', signed=True)

	def read_uint16_at(self, offset:int, unaligned=False)->int:
		return 0xFFFF & self.read_int16_at(offset, unaligned)

	def read_int32(self, unaligned=False)->int:
		if not unaligned and (self.offset & 3):
			raise UnalignedReadException("Attempted read of 32-bit integer at unaligned offset %d" % (self.offset,))
		return int.from_bytes(self.read_bytes(4), byteorder='little', signed=True)

	def read_uint32(self, unaligned=False)->int:
		return 0xFFFFFFFF & self.read_int32(unaligned)

	# Read without updating the current offset
	def read_int32_at(self, offset:int, unaligned=False)->int:
		if not unaligned and ((self.offset + offset) & 1):
			raise UnalignedReadException("Attempted read of 32-bit integer at unaligned offset %d" % (self.offset + offset,))
		return int.from_bytes(self.read_bytes_at(offset, 4), byteorder='little', signed=True)

	def read_uint32_at(self, offset:int, unaligned=False)->int:
		return 0xFFFFFFFF & self.read_int32_at(offset, unaligned)

	def skip(self, skip_bytes:int):
		self.check_read(skip_bytes)
		self.offset += skip_bytes
		return

	def remaining(self):
		return self.length - self.offset

	def read_byte_string(self, length:int=-1)->bytes:
		if length < 0:
			length = self.remaining()

		result = self.read_byte_string_at(self.offset, length)
		self.skip(length)
		return result

	def read_byte_string_at(self, offset:int, length:int=-1)->bytes:
		if length < 0:
			self.check_read_at(offset, 0)
			length = self.length - offset

		string_bytes = self.read_bytes_at(offset, length)
		return zero_terminated(string_bytes)

	def decode(self, s):
		return s.decode(self.encoding)

	def read_string(self, length:int=-1):
		return self.decode(self.read_byte_string(length))

	def unpack_at(self, offset, unpack_format:str|struct.Struct):
		if type(unpack_format) is str:
			size = struct.calcsize(unpack_format)
			self.check_read_at(offset, size)
			return struct.unpack_from(unpack_format, self.data, offset + self.slice_offset), size
		else:
			size = unpack_format.size
			self.check_read_at(offset, size)
			return unpack_format.unpack_from(self.data, offset + self.slice_offset), size

	def unpack(self, unpack_format:str|struct.Struct):
		unpacked, size = self.unpack_at(self.offset, unpack_format)
		self.offset += size
		return unpacked

class vss_record_header:

	LENGTH = 8
	unpack_struct = struct.Struct(b'<I2sH')

	def __init__(self, reader:vss_record_reader):
		self.offset:int = None
		self.length:int = None
		self.signature:bytes = None
		self.file_crc: int = None
		self.actual_crc:int = None

		self.read(reader)
		return

	def is_crc_valid(self):
		return self.file_crc == self.actual_crc

	def read(self, reader:vss_record_reader):
		self.offset = reader.offset
		self.length, self.signature, self.file_crc = reader.unpack(self.unpack_struct)

		# Create a slice reader:
		self.reader = reader.clone(length=self.length)

		self.actual_crc = self.reader.crc16(self.length)

		# Advance the original reader beyond this whole record
		reader.skip(self.length)
		return

	def check_crc(self):
		if not self.is_crc_valid():
			raise RecordCrcException("CRC error in %s record: expected=%04X, actual=%04X"
							% (self.signature.decode(), self.file_crc, self.actual_crc))
		return

	def check_signature(self, expected:bytes):
		if self.signature != expected:
			raise RecordNotFoundException("Unexpected record signature: expected=%s, actual=%s"
					% (expected.decode(), self.signature.decode()))

	def print(self, fd):
		# The signature is printed as if it'a a two-character literal: characters reversed
		print("RECORD: '%c%c' - Length: 0x%X (%d) - Offset: %06X - CRC: %04X (%s: %04X)" % (
			chr(self.signature[1]), chr(self.signature[0]),
			self.length + self.LENGTH, self.length + self.LENGTH,
			self.offset, self.file_crc,
			"valid" if self.is_crc_valid() else "INVALID", self.actual_crc), file=fd)
		return

class vss_record:

	def __init__(self, header:vss_record_header):
		self.header:vss_record_header = header
		self.reader:vss_record_reader = header.reader
		self.encoding:str = self.reader.encoding
		self.annotations:List[str] = None
		return

	def read(self):
		return

	def decode(self, s):
		return s.decode(self.encoding)

	def add_annotation(self, annotation):
		if self.annotations:
			self.annotations.append(annotation)
		else:
			self.annotations = [annotation]
		return

	def print(self, fd):
		self.header.print(fd)

		if self.annotations:
			print('\n'.join(self.annotations), file=fd)
		return