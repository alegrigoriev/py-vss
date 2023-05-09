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

from __future__ import annotations
from typing import Tuple, List

from .vss_exception import EndOfBufferException, BadHeaderException
from .vss_record import *
from .vss_record_file import vss_record_file
from .vss_record_factory import vss_item_record_factory

from enum import IntEnum, IntFlag

class ItemFileType(IntEnum):

	Project = 1
	File    = 2

class vss_item_file_header:
	ITEM_FILE_VERSION = 6

	def __init__(self, reader:vss_record_reader):

		self.file_type = None	# value of ItemFileType enum
		self.file_version = None	# must be ITEM_FILE_VERSION
		self.filler_words:Tuple[int, int, int, int] = None

		self.read(reader)
		return

	def read(self, reader:vss_record_reader):
		try:
			file_sig = reader.read_bytes(0x20)
			if file_sig[:21] != b"SourceSafe@Microsoft\x00":
				raise BadHeaderException("Incorrect file signature")

			self.file_type = reader.read_int16()
			self.file_version = reader.read_int16()
			if self.file_version != self.ITEM_FILE_VERSION:
				raise BadHeaderException("Incorrect file version")

			self.filler_words = (
				reader.read_uint32(),
				reader.read_uint32(),
				reader.read_uint32(),
				reader.read_uint32(),
			)
		except EndOfBufferException as e:
			raise BadHeaderException("Truncated header", *e.args)
		# Total 52 bytes read (0x34)
		return

	def print(self, fd):
		print("  File type: %s, version: %d" %
			('Project' if self.file_type == ItemFileType.Project else 'File', self.file_version), file=fd)
		if any(self.filler_words):
			print("  Filler: %08X %08X %08X %08X" % self.filler_words, file=fd)
		return

class vss_item_header_record(vss_record):

	SIGNATURE = b"DH"

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.item_type = None	# value of ItemFileType enum
		self.num_revisions:int = None	# The number includes revisions of the branch parent(s)
		self.name:vss_name = None
		self.first_revision:int = None
		self.data_ext:str = None
		self.first_revision_offset:int = None
		self.last_revision_offset:int = None
		self.eof_offset:int = None
		self.rights_offset:int = None
		self.item_header_filler_words:Tuple[int, int, int, int] = None
		return

	def read(self):
		super().read()
		reader = self.reader

		self.item_type = reader.read_int16()
		self.num_revisions = reader.read_uint16()
		self.name = reader.read_name()
		self.first_revision = reader.read_uint16()
		self.data_ext = reader.read_bytes(2)
		self.first_revision_offset = reader.read_int32()
		self.last_revision_offset = reader.read_int32()
		self.eof_offset = reader.read_int32()
		self.rights_offset = reader.read_int32()
		self.item_header_filler_words = (
			reader.read_uint32(),
			reader.read_uint32(),
			reader.read_uint32(),
			reader.read_uint32(),
		)
		if not any(self.item_header_filler_words):
			self.item_header_filler_words = None
		return

	def print(self, fd):
		super().print(fd)

		print("  Item Type: %s - Revisions: %d - Name: %s" % (
						'Project' if self.item_type == ItemFileType.Project else 'File',
						self.num_revisions, self.decode(self.name.short_name)), file=fd)
		if self.name.name_file_offset != 0:
			print("  Name offset: %06X" % (self.name.name_file_offset), file=fd)
		print("  First revision: #%3d" % (self.first_revision), file=fd)
		if self.data_ext:
			print("  Data extension: %s" % (self.data_ext.decode()), file=fd)
		print("  First/last rev offset: %06X/%06X" % (self.first_revision_offset, self.last_revision_offset), file=fd)
		print("  EOF offset: %06X" % (self.eof_offset), file=fd)
		if self.rights_offset != 0:
			print("  Rights offset: %06X" % (self.rights_offset), file=fd)
		if self.item_header_filler_words is not None:
			print("  Filler: %08X %08X %08X %08X" % self.item_header_filler_words, file=fd)
		return

class FileHeaderFlags(IntFlag):

	Locked       = 1
	Binary       = 2
	LatestOnly   = 4		# Store the latest version only (WHO WOULD DO THAT?)
	Shared       = 0x20
	CheckedOut   = 0x40

	def __str__(self):
		flags = int(self)
		flags_list=[]
		if flags & FileHeaderFlags.Locked:
			flags_list.append('Locked')
		if flags & FileHeaderFlags.Binary:
			flags_list.append('Binary')
		if flags & FileHeaderFlags.LatestOnly:
			flags_list.append('LatestOnly')
		if flags & FileHeaderFlags.Shared:
			flags_list.append('Shared')
		if flags & FileHeaderFlags.CheckedOut:
			flags_list.append('CheckedOut')

		flags &= ~(FileHeaderFlags.Locked
					|FileHeaderFlags.Binary
					|FileHeaderFlags.LatestOnly
					|FileHeaderFlags.Shared
					|FileHeaderFlags.CheckedOut)
		if flags or not flags_list:
			flags_list.append('0x%04X' % (flags))

		return '|'.join(flags_list)

class vss_file_header_record(vss_item_header_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.flags:int = None
		self.branch_file:str = None
		self.branch_offset:int = None
		self.project_offset:int = None
		self.branch_count:int = None
		self.project_count:int = None
		self.first_checkout_offset:int = None
		self.last_checkout_offset:int = None
		self.data_crc = None
		self.last_rev_timestamp:int = None
		self.modification_timestamp:int = None
		self.creation_timestamp:int = None
		return

	def read(self):
		super().read()
		reader = self.reader

		self.flags = reader.read_int16()
		self.branch_file = reader.read_string(10)
		self.branch_offset = reader.read_int32()
		self.project_offset = reader.read_int32()
		self.branch_count = reader.read_uint16()
		self.project_count = reader.read_uint16()
		self.first_checkout_offset = reader.read_int32()
		self.last_checkout_offset = reader.read_int32()
		self.data_crc = reader.read_uint32()
		self.file_header_filler_words = (
			reader.read_uint32(),
			reader.read_uint32(),
		)
		if not any(self.file_header_filler_words):
			self.file_header_filler_words = None
		self.last_rev_timestamp = reader.read_uint32()
		self.modification_timestamp = reader.read_uint32()
		self.creation_timestamp = reader.read_uint32()
		return

	def print(self, fd):
		super().print(fd)

		print("  Flags: %4X (%s)" % (self.flags, FileHeaderFlags(self.flags)), file=fd)
		if self.branch_file:
			print("  Branched from file: %s" % (self.branch_file), file=fd)
		if self.branch_offset != 0:
			print("  Branch offset: %06X" % (self.branch_offset), file=fd)
		print("  Branch count: %d" % (self.branch_count), file=fd)
		print("  Project offset: %06X" % (self.project_offset), file=fd)
		print("  Project count: %d" % (self.project_count), file=fd)
		print("  First/last checkout offset: %06X/%06X" % (self.first_checkout_offset, self.last_checkout_offset), file=fd)
		print("  Data CRC: %8X" % (self.data_crc), file=fd)
		print("  Last revision time: %s" % (timestamp_to_datetime(self.last_rev_timestamp)), file=fd)
		print("  Modification time: %s" % (timestamp_to_datetime(self.modification_timestamp)), file=fd)
		print("  Creation time: %s" % (timestamp_to_datetime(self.creation_timestamp)), file=fd)
		if self.file_header_filler_words is not None:
			print("  Filler: %08X %08X" % self.file_header_filler_words, file=fd)
		return

class vss_project_header_record(vss_item_header_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.parent_project:str = None
		self.parent_file:str = None
		self.total_items:int = None
		self.subprojects:int = None
		return

	def read(self):
		super().read()
		reader = self.reader

		self.parent_project = reader.read_string(260)
		self.parent_file = reader.read_string(12)
		self.total_items = reader.read_int16()
		self.subprojects = reader.read_int16()
		return

	def print(self, fd):
		super().print(fd)

		print("  Parent project: %s" % (self.parent_project), file=fd)
		print("  Parent file: %s" % (self.parent_file), file=fd)
		print("  Total items: %d" % (self.total_items), file=fd)
		print("  Subprojects: %d" % (self.subprojects), file=fd)
		return

class vss_item_file(vss_record_file):

	def __init__(self, database, filename:str, header_record_class):
		super().__init__(database, filename)

		self.header:vss_item_header_record = None

		self.file_header = vss_item_file_header(self.reader)

		self.header = self.read_record(header_record_class)
		if self.header.item_type != self.file_header.file_type:
			raise BadHeaderException("Header record type mismatch")

		# Fill the record dictionary
		self.read_all_records(vss_item_record_factory, last_offset=self.header.eof_offset)

		return

	def get_data_file_name(self)->str:
		data_file_suffix = self.header.data_ext.decode(encoding='ansi')
		return self.filename + data_file_suffix

	def print(self, fd):

		print("Item file %s, size: %06X" % (self.filename, self.file_size), file=fd)
		super().print(fd)

		return

class vss_project_item_file(vss_item_file):
	# 'first_letter_subdirectory' argument is not used: it's always True.
	# It's passed as part of generic record file open
	def __init__(self, database, filename:str, first_letter_subdirectory):
		super().__init__(database, filename, vss_project_header_record)
		self.header:vss_project_header_record

		return

	def is_project(self):
		return True

class vss_file_item_file(vss_item_file):
	# 'first_letter_subdirectory' argument is not used: it's always True.
	# It's passed as part of generic record file open
	def __init__(self, database, filename:str, first_letter_subdirectory):
		super().__init__(database, filename, vss_file_header_record)
		self.header:vss_file_header_record

		return

	def is_project(self):
		return False

	def is_locked(self):
		return (self.header.flags & FileHeaderFlags.Locked) != 0

	def is_binary(self):
		return (self.header.flags & FileHeaderFlags.Binary) != 0

	def is_latest_only(self):
		return (self.header.flags & FileHeaderFlags.LatestOnly) != 0

	def is_shared(self):
		return (self.header.flags & FileHeaderFlags.Shared) != 0

	def is_checked_out(self):
		return (self.header.flags & FileHeaderFlags.CheckedOut) != 0

	def print(self, fd):
		super().print(fd)

		offset = self.header.project_offset
		if offset != 0:
			print("\nIncluded in %d project(s):" % (self.header.project_count), file=fd)
			while offset != 0:
				# Note that the project count may be less than number of records
				# Because some projects may be inactive at this time
				project_record = self.get_record(offset, vss_project_record)
				print('', file=fd)
				project_record.print(fd)
				offset = project_record.prev_project_offset

		offset = self.header.branch_offset
		if offset != 0:
			print("\nBranched to %d project(s):" % (self.header.branch_count), file=fd)
			while offset != 0:
				branch_record = self.get_record(offset, vss_branch_record)
				print('', file=fd)
				branch_record.print(fd)
				offset = branch_record.prev_branch_offset

		offset = self.header.last_checkout_offset
		if offset != 0:
			print("\nChecked out to:", file=fd)
			while offset != 0:
				checkout_record = self.get_record(offset, vss_checkout_record)
				print('', file=fd)
				checkout_record.print(fd)
				if offset == self.header.first_checkout_offset:
					break
				offset = checkout_record.prev_checkout_offset

		return
