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
from typing import DefaultDict, Iterator

from .vss_revision import vss_full_name

from .vss_database import vss_database
from .vss_exception import VssFileNotFoundException
from .vss_record import vss_record, vss_record_header, vss_name
from .vss_record_file import vss_record_file
from .vss_item_file import *

from enum import IntFlag

class ProjectEntryFlag(IntFlag):

	Deleted    = 1
	Binary     = 2
	LatestOnly = 4
	Shared     = 8

	def __str__(self):
		flags = int(self)
		flags_list=[]
		if flags & ProjectEntryFlag.Deleted:
			flags_list.append('Deleted')
		if flags & ProjectEntryFlag.Binary:
			flags_list.append('Binary')
		if flags & ProjectEntryFlag.LatestOnly:
			flags_list.append('LatestOnly')
		if flags & ProjectEntryFlag.Shared:
			flags_list.append('Shared')

		flags &= ~(ProjectEntryFlag.Deleted
					|ProjectEntryFlag.Binary
					|ProjectEntryFlag.LatestOnly
					|ProjectEntryFlag.Shared)
		if flags or not flags_list:
			flags_list.append('0x%04X' % (flags))

		return '|'.join(flags_list)

class vss_item:

	def __init__(self, database:vss_database, item_file_class,
			physical_name:str, logical_name:str, flags:int):

		self.database = database
		self.parent:vss_project = None

		self.physical_name = physical_name
		self.logical_name = logical_name
		self.flags = flags
		self.deleted = 0 != (ProjectEntryFlag.Deleted & flags)
		try:
			self.item_file:item_file_class = database.open_records_file(item_file_class, physical_name)
		except VssFileNotFoundException:
			self.item_file:vss_item_file = None
		return

	def is_deleted(self):
		return self.deleted

	def make_full_path(self, sub_item_name:str=''):
		while self is not None:
			if self.is_project():
				sub_item_name = self.logical_name + '/' + sub_item_name
			else:
				sub_item_name = self.logical_name
			self = self.parent

		return sub_item_name

	def print(self, fd, indent:str=''):
		print("%sEntry flags=%s" % (indent, ProjectEntryFlag(self.flags)), file=fd)

		self.item_file.print(fd, indent)
		return

class vss_project_entry_record(vss_record):

	SIGNATURE = b"JP"

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.item_type:int = None
		self.flags:int = None
		self.name:vss_name = None
		self.pinned_version:int = None
		self.physical:str = None
		return

	def is_project_entry(self):
		return self.item_type == ItemFileType.Project

	def is_file_entry(self):
		return self.item_type == ItemFileType.File

	def read(self):
		super().read()
		reader = self.reader

		self.item_type = reader.read_int16()
		self.flags = reader.read_int16()
		self.name = reader.read_name()
		self.pinned_version = reader.read_int16()
		self.physical = reader.read_byte_string(10)
		return

	def print(self, fd, indent:str=''):
		super().print(fd, indent)

		print("%sItem Type: %d - Name: %s"
					% (indent, self.item_type, self.decode_name(self.name, self.physical)), file=fd)
		print("%sFlags: %4X (%s)" % (indent, self.flags, ProjectEntryFlag(self.flags)), file=fd)
		print("%sPinned version: %d" % (indent, self.pinned_version), file=fd)
		return

class vss_file(vss_item):

	def __init__(self, database:vss_database, physical_name:str, logical_name:str,
						flags:int, pinned_version:int=0):
		super().__init__(database, vss_file_item_file,
				physical_name, logical_name, flags)
		self.item_file:vss_file_item_file
		self.pinned_version = pinned_version
		return

	def is_project(self): return False

	def is_pinned(self):
		return self.pinned_version > 0

	def is_locked(self):
		return self.item_file.is_locked()

	def is_binary(self):
		return self.item_file.is_binary()

	def is_latest_only(self):
		return self.item_file.is_latest_only()

	def is_shared(self):
		return self.item_file.is_shared()

	def is_checked_out(self):
		return self.item_file.is_checked_out()

	def print(self, fd, indent=''):
		print("\n%sFile %s" % (indent, self.make_full_path()), file=fd)
		print("%s  File flags=%s" % (indent, FileHeaderFlags(self.item_file.header.flags)), file=fd)

		super().print(fd, indent+'  ')
		return

class vss_project(vss_item):

	def __init__(self, database:vss_database,
			physical_name:str, logical_name:str, flags:int, recursive=True):
		super().__init__(database, vss_project_item_file, physical_name, logical_name, flags)
		self.item_file:vss_project_item_file

		# items_by_logical_name only contains active (not deleted) child items
		self.items_by_logical_name:DefaultDict[str,vss_item] = {}
		self.items_array = []
		if self.item_file is None:
			return
		if not recursive:
			return

		# Build tree
		project_entry_file = database.open_records_file(vss_record_file,
						self.item_file.get_data_file_name(), first_letter_subdirectory=True)

		entry:vss_project_entry_record
		# Pre-allocate the items array
		self.items_array = [None] * len(self.item_file.items_array)
		project_entry_idx = 0
		for entry in project_entry_file.read_all_records(vss_project_entry_record):
			assert(entry.is_file_entry() or (entry.is_project_entry() and entry.pinned_version == 0))
			item_full_name = vss_full_name(database, entry.name, entry.physical)
			# In some databases (restored from old version?),
			# order of items after [share A from X, delete A, branch A from Y]
			# may not match the recovered order.
			# We need to use the recovered order, since it matches the "share" record indices.
			item_index = self.item_file.find_item(item_full_name)
			assert(self.items_array[item_index] is None)
			if item_index != project_entry_idx:
				entry.add_annotation("WARNING: Item out of order. Expected at position %d, actual position %d"
								% (item_index, project_entry_idx))
			self.items_array.pop(item_index)
			self.insert_new_item(item_full_name.physical_name, item_full_name.name,
					entry.is_project_entry(), entry.flags, entry.pinned_version, item_idx=item_index)

			project_entry_idx += 1
			continue
		return

	def open_new_item(self, physical_name:str, logical_name:str, is_project:bool,
				flags=0, pinned_version:int=0):
		if is_project:
			item = vss_project(self.database, physical_name, logical_name,
							flags)
		else:
			item = vss_file(self.database, physical_name, logical_name,
							flags, pinned_version)

		return item

	def insert_new_item(self, physical_name:str, logical_name:str, is_project:bool,
				flags=0, pinned_version:int=0, item_idx:int=-1):
		item:vss_item = self.open_new_item(physical_name, logical_name, is_project, flags, pinned_version)

		if item_idx == -1:
			item_idx = len(self.items_array)
		self.insert_item_by_idx(item, item_idx)
		return item

	def remove_item_by_index(self, item_idx, remove_from_directory=False):
		if item_idx >= len(self.items_array):
			return None
		item = self.items_array.pop(item_idx)
		if not item.is_deleted():
			if remove_from_directory or item.item_file is None:
				assert(item is self.items_by_logical_name.get(item.logical_name, None))
				self.items_by_logical_name.pop(item.logical_name)
			# If the item file is present, the logical name will be removed by Create action
		return item

	def remove_from_directory(self, item):
		return self.items_by_logical_name.pop(item.logical_name)

	def get_item_by_index(self, item_idx):
		if item_idx >= len(self.items_array):
			return None
		return self.items_array[item_idx]

	def insert_item_by_idx(self, item, item_idx):
		if item_idx < len(self.items_array) \
				and self.items_array[item_idx] is item:
			return item_idx

		item.parent = self
		self.items_array.insert(item_idx, item)
		if not item.is_deleted():
			assert(item.logical_name not in self.items_by_logical_name)
			self.items_by_logical_name[item.logical_name] = item
		return item_idx

	def find_by_path_name(self, full_name:str):
		# Find the root project
		item = self
		while item.parent is not None:
			item = item.parent

		full_name = full_name.removesuffix('/')
		name_parts = full_name.split('/')
		logical_name = name_parts.pop(0)
		assert(logical_name == item.logical_name)
		while name_parts:
			logical_name = name_parts.pop(0)

			item = item.get_item_by_logical_name(logical_name)
			if item is None:
				return None
			if not item.is_project():
				break
			continue

		if name_parts:
			return None

		return item

	def is_project(self): return True

	def all_items(self) ->Iterator[vss_item]:
		return iter(self.items_array)

	def get_item_by_logical_name(self, logical_name:str)->vss_item:
		return self.items_by_logical_name.get(logical_name, None)

	def print(self, fd, indent:str=''):
		print("\n%sProject %s" % (indent, self.make_full_path()), file=fd)

		indent += '  '
		super().print(fd, indent)

		# Print child items
		for item in self.all_items():
			item.print(fd, indent)
		return
