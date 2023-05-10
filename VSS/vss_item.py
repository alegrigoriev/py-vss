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

	def print(self, fd):
		print("  Entry flags=%s" % (ProjectEntryFlag(self.flags)), file=fd)

		self.item_file.print(fd)
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

	def print(self, fd):
		super().print(fd)

		print("  Item Type: %d - Name: %s"
					% (self.item_type, self.decode_name(self.name, self.physical)), file=fd)
		print("  Flags: %4X (%s)" % (self.flags, ProjectEntryFlag(self.flags)), file=fd)
		print("  Pinned version: %d" % (self.pinned_version), file=fd)
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

	def print(self, fd):
		print("\nFile %s" % (self.make_full_path()), file=fd)
		print("  File flags=%s" % (FileHeaderFlags(self.item_file.header.flags)), file=fd)

		super().print(fd)
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
		for entry in project_entry_file.read_all_records(vss_project_entry_record):
			assert(entry.is_file_entry() or (entry.is_project_entry() and entry.pinned_version == 0))
			item:vss_item = self.open_new_item(entry.physical.decode(), self.database.get_long_name(entry.name),
					entry.is_project_entry(), entry.flags, entry.pinned_version)

			self.insert_item(item)
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

	def remove_from_directory(self, item):
		return self.items_by_logical_name.pop(item.logical_name)

	def insert_item(self, item):
		item.parent = self
		self.items_array.append(item)
		if not item.is_deleted():
			assert(item.logical_name not in self.items_by_logical_name)
			self.items_by_logical_name[item.logical_name] = item
		return

	def is_project(self): return True

	def all_items(self) ->Iterator[vss_item]:
		return iter(self.items_array)

	def get_item_by_logical_name(self, logical_name:str)->vss_item:
		return self.items_by_logical_name.get(logical_name, None)

	def print(self, fd):
		print("\nProject %s" % (self.make_full_path()), file=fd)

		super().print(fd)

		# Print child items
		for item in self.all_items():
			item.print(fd)
		return
