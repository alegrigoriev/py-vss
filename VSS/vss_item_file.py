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
from typing import Tuple, List, Iterator

from .vss_exception import EndOfBufferException, BadHeaderException, ArgumentOutOfRangeException
from .vss_record import *
from .vss_record_file import vss_record_file
from .vss_record_factory import vss_item_record_factory
from .vss_revision_record import vss_revision_record
from .vss_verbose import VerboseFlags

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

	def print(self, fd, indent='', verbose=VerboseFlags.Files):
		print("%sFile type: %s, version: %d" %
			(indent, 'Project' if self.file_type == ItemFileType.Project else 'File', self.file_version), file=fd)
		if any(self.filler_words):
			print("%sFiller: %08X %08X %08X %08X" % (indent, *self.filler_words), file=fd)
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

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.RecordHeaders):
		super().print(fd, indent, verbose)

		print("%sItem Type: %s - Revisions: %d - Name: %s" % (indent,
						'Project' if self.item_type == ItemFileType.Project else 'File',
						self.num_revisions, self.decode(self.name.short_name)), file=fd)
		if self.name.name_file_offset != 0:
			print("%sName offset: %06X" % (indent, self.name.name_file_offset), file=fd)
		print("%sFirst revision: #%3d" % (indent, self.first_revision), file=fd)
		if self.data_ext:
			print("%sData extension: %s" % (indent, self.data_ext.decode()), file=fd)
		print("%sFirst/last rev offset: %06X/%06X" % (indent, self.first_revision_offset, self.last_revision_offset), file=fd)
		print("%sEOF offset: %06X" % (indent, self.eof_offset), file=fd)
		if self.rights_offset != 0:
			print("%sRights offset: %06X" % (indent, self.rights_offset), file=fd)
		if self.item_header_filler_words is not None:
			print("%sFiller: %08X %08X %08X %08X" % (indent, *self.item_header_filler_words), file=fd)
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

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.RecordHeaders):
		super().print(fd, indent, verbose)

		print("%sFlags: %4X (%s)" % (indent, self.flags, FileHeaderFlags(self.flags)), file=fd)
		if self.branch_file:
			print("%sBranched from file: %s" % (indent, self.branch_file), file=fd)
		if self.branch_offset != 0:
			print("%sBranch offset: %06X" % (indent, self.branch_offset), file=fd)
		print("%sBranch count: %d" % (indent, self.branch_count), file=fd)
		print("%sProject offset: %06X" % (indent, self.project_offset), file=fd)
		print("%sProject count: %d" % (indent, self.project_count), file=fd)
		print("%sFirst/last checkout offset: %06X/%06X" % (indent, self.first_checkout_offset, self.last_checkout_offset), file=fd)
		print("%sData CRC: %8X" % (indent, self.data_crc), file=fd)
		print("%sLast revision time: %s" % (indent, timestamp_to_datetime(self.last_rev_timestamp)), file=fd)
		print("%sModification time: %s" % (indent, timestamp_to_datetime(self.modification_timestamp)), file=fd)
		print("%sCreation time: %s" % (indent, timestamp_to_datetime(self.creation_timestamp)), file=fd)
		if self.file_header_filler_words is not None:
			print("%sFiller: %08X %08X" % (indent, *self.file_header_filler_words), file=fd)
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

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.RecordHeaders):
		super().print(fd, indent, verbose)

		print("%sParent project: %s" % (indent, self.parent_project), file=fd)
		print("%sParent file: %s" % (indent, self.parent_file), file=fd)
		print("%sTotal items: %d" % (indent, self.total_items), file=fd)
		print("%sSubprojects: %d" % (indent, self.subprojects), file=fd)
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

		self.revisions:List[vss_revision] = []
		return

	def get_data_file_name(self)->str:
		data_file_suffix = self.header.data_ext.decode(encoding='ansi')
		return self.filename + data_file_suffix

	def all_revisions(self)->Iterator[vss_revision]:
		return iter(self.revisions)

	def get_last_revision_num(self):
		return self.header.num_revisions

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileHeaders):
		if verbose & (VerboseFlags.FileHeaders|VerboseFlags.Records):
			print("%sItem file %s, size: %06X" % (indent, self.filename, self.file_size), file=fd)
			super().print(fd, indent + '  ', verbose)

		if verbose & VerboseFlags.Records:
			# print all records
			super().print(fd, indent, verbose|VerboseFlags.FileHeaders)
		elif verbose & (VerboseFlags.FileRevisions|VerboseFlags.ProjectRevisions):
			super().print(fd, indent, verbose)
			for revision in self.revisions:
				print('', file=fd)	# insert an empty line
				revision.print(fd, indent, verbose|VerboseFlags.Records)
		return

class vss_project_item_file(vss_item_file):
	# 'first_letter_subdirectory' argument is not used: it's always True.
	# It's passed as part of generic record file open
	def __init__(self, database, filename:str, first_letter_subdirectory):
		super().__init__(database, filename, vss_project_header_record)
		self.header:vss_project_header_record

		self.items_array = []
		self.build_revisions(database)
		return

	def is_project(self):
		return True

	# Read revisions in reverse order from last to first
	def build_revisions(self, database):
		# pre-allocate the revision array
		self.revisions = [None] * self.header.num_revisions
		offset = self.header.last_revision_offset
		# In-method imports are used to prevent circular dependencies
		from .vss_revision import vss_project_revision_factory
		while offset > 0:
			record:vss_revision_record
			record = self.get_record(offset)
			revision = vss_project_revision_factory(record, database, self)

			self.revisions[revision.revision_num-1] = revision
			# Continue from the new position
			offset = record.prev_rev_offset
			continue

		# Need to pre-process revisions in forward order to assign indices to items
		for revision in self.revisions:
			revision.apply_to_project_items(self)
		return

	def find_item(self, full_name):
		item_idx = self.find_item_index(full_name)
		if item_idx >= len(self.items_array):
			return -1
		item = self.items_array[item_idx]
		if item.index_name == full_name.index_name \
				and item.physical_name == full_name.physical_name:
			return item_idx
		return -1

	### Finds either the item index, or the insertion point for the new item
	def find_item_index(self, full_name):
		top = len(self.items_array)
		bottom = 0
		middle = 0
		# Search by bisection. Find an index of last item less than we're looking for
		while bottom != top:
			middle = (bottom + top + 1) // 2
			if full_name.index_name > self.items_array[middle-1].index_name:
				bottom = middle
				continue
			elif top == middle:
				# Not found, break out to avoid infinite loop
				break
			else:
				top = middle
			continue

		# There can be Multiple items with same index name can.
		# They're not sorted by physical name.
		# They're inserted at index 0.
		top = len(self.items_array)
		middle = bottom
		while middle < top:
			item = self.items_array[middle]
			if item.index_name != full_name.index_name:
				break
			if item.physical_name == full_name.physical_name:
				# Found
				return middle
			middle += 1
			continue
		return bottom

	def remove_item(self, full_name):
		item_idx = self.find_item(full_name)
		if item_idx >= 0 and item_idx < len(self.items_array):
			return (item_idx, self.items_array.pop(item_idx))
		else:
			return (item_idx, None)

	def remove_item_by_idx(self, item_idx):
		if item_idx >= 0 and item_idx < len(self.items_array):
			return (item_idx, self.items_array.pop(item_idx))
		else:
			return (item_idx, None)

	def add_item(self, full_name):
		item_idx = self.find_item_index(full_name)
		self.items_array.insert(item_idx, full_name)
		return item_idx

	def get_item(self, item_idx):
		if item_idx >= len(self.items_array):
			return None
		return self.items_array[item_idx]

	def insert_item(self, item_idx, full_name):
		self.items_array.insert(item_idx, full_name)
		return item_idx

	def get_revision(self, version:int)->vss_revision:
		if version < 1 or version > self.header.num_revisions:
			raise ArgumentOutOfRangeException("version", version, "Invalid version number")
		if not self.revisions:
			return None
		# Projects (directories) don't branch.
		return self.revisions[version-1]

	def get_creation_timestamp(self):
		return self.get_revision(1).timestamp

class vss_file_item_file(vss_item_file):
	# 'first_letter_subdirectory' argument is not used: it's always True.
	# It's passed as part of generic record file open
	def __init__(self, database, filename:str, first_letter_subdirectory):
		super().__init__(database, filename, vss_file_header_record)
		self.header:vss_file_header_record
		with database.open_data_file(self.get_data_file_name()) as file:
			self.last_data = file.read()

		if self.header.branch_file:
			self.branch_parent = database.open_records_file(vss_file_item_file,
														self.header.branch_file)
		else:
			self.branch_parent:vss_file_item_file = None
		self.build_revisions(database, self.last_data)
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

	# Read revisions in reverse order from last to first
	def build_revisions(self, database, data:bytes):
		first_revision:int = self.header.first_revision
		# pre-allocate the revision array
		self.revisions = [None] * (self.header.num_revisions - (first_revision-1))
		offset = self.header.last_revision_offset
		prev_data = data
		# In-method imports are used to prevent circular dependencies
		from .vss_revision import vss_file_revision_factory
		from .vss_revision_record import VssRevisionAction
		while offset > 0:
			record:vss_revision_record
			record = self.get_record(offset)
			revision = vss_file_revision_factory(record, database, self)
			self.revisions[revision.revision_num-first_revision] = revision

			# If the file was added as empty, and the non-empty message is present,
			# Use the second revision's data for the first revision
			if revision.revision_num == 1 \
				and len(data) == 0:
				data = prev_data
			elif record.action == VssRevisionAction.CheckinFile:
				prev_data = data

			data = revision.set_revision_data(data)

			# Continue from the new position
			offset = record.prev_rev_offset
			continue

		return

	def get_revision(self, version:int)->vss_revision:
		if not self.revisions:
			return None
		if version < 1 or version > self.header.num_revisions:
			raise ArgumentOutOfRangeException("version", version, "Invalid version number")
		if version >= self.header.first_revision:
			return self.revisions[version - self.header.first_revision]
		if self.branch_parent is None or self.branch_parent is NotImplemented:
			# NotImplemented can be returned in case of dependency cycle
			return None
		return self.branch_parent.get_revision(version)

	def get_creation_timestamp(self):
		return self.get_revision(self.header.first_revision).timestamp

	def get_revision_data(self, version:int)->bytes:
		revision = self.get_revision(version)
		if revision is None:
			return None
		if revision.revision_data is None:
			return b''
		return revision.revision_data

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileHeaders):
		super().print(fd, indent, verbose)

		crc = crc32.calculate(self.last_data)
		if crc != self.header.data_crc:
			print("header.data_crc=%08X, calculated: %08X" % (self.header.data_crc, crc), file=fd)

		if verbose & VerboseFlags.Records:
			return

		# With VerboseFlags.Records flag, these records are printed in file order
		offset = self.header.project_offset
		if offset != 0:
			print("\n%sIncluded in %d project(s):" % (indent, self.header.project_count), file=fd)
			while offset != 0:
				# Note that the project count may be less than number of records
				# Because some projects may be inactive at this time
				project_record = self.get_record(offset, vss_project_record)
				print('', file=fd)
				project_record.print(fd, indent + '  ', verbose)
				offset = project_record.prev_project_offset

		offset = self.header.branch_offset
		if offset != 0:
			print("\n%sBranched to %d project(s):" % (indent, self.header.branch_count), file=fd)
			while offset != 0:
				branch_record = self.get_record(offset, vss_branch_record)
				print('', file=fd)
				branch_record.print(fd, indent + '  ', verbose)
				offset = branch_record.prev_branch_offset

		offset = self.header.last_checkout_offset
		if offset != 0:
			print("\n%sChecked out to:" % (indent), file=fd)
			while offset != 0:
				checkout_record = self.get_record(offset, vss_checkout_record)
				print('', file=fd)
				checkout_record.print(fd, indent + '  ', verbose)
				if offset == self.header.first_checkout_offset:
					break
				offset = checkout_record.prev_checkout_offset

		return
