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
from typing import DefaultDict

from .vss_exception import VssFileNotFoundException

import re
from pathlib import Path

class simple_ini_parser:
	def __init__(self, inifile:str):
		self.values = {}

		with open(inifile, 'rt') as fd:
			for line in fd:
				line = line.strip()
				if not line or line.startswith(';'):
					continue
				parts = re.match(r'([^= ]+)\s*=\s*(.*)$', line)
				if parts:
					self.values[parts[1]] = parts[2]
				continue
		return

	def get(self, key:str, default:str):
		return self.values.get(key, default)

class vss_database:
	RootProjectName = "$"
	RootProjectFile = "AAAAAAAA"
	ProjectSeparatorChar = '/'
	ProjectSeparator = "/"

	# Default encoding is the local Windows ANSI code page
	def __init__(self, path:str, encoding='mbcs'):
		self.base_path:str = path
		self.encoding = encoding
		self.index_name_dict = {}
		self.physical_name_dict = {}
		self.logical_name_dict = {}

		self.ini_path:Path = Path(path, "srcsafe.ini")

		ini_reader = simple_ini_parser(self.ini_path)

		data_path = ini_reader.get("Data_Path", "data")
		self.data_path = Path(path, data_path)

		self.record_files_by_physical:DefaultDict[str,vss_record_file] = {}

		# In-method imports are used to prevent circular dependencies
		from .vss_name_file import vss_name_file
		self.name_file = vss_name_file(self, "names.dat")

		return

	def open_root_project(self, project_class, recursive=False):
		return project_class(self, self.RootProjectFile, self.RootProjectName, 0, recursive=recursive)

	def get_project_tree(self):
		# In-method imports are used to prevent circular dependencies
		from .vss_item import vss_project
		return self.open_root_project(vss_project, recursive=True)

	def get_data_path(self, physical_name, first_letter_subdirectory=True):
		if first_letter_subdirectory:
			# Data files are arranged into directories by the first letter of their name
			# Such arrangement is often called "sharding"
			return Path(self.data_path, physical_name[0:1], physical_name)
		else:
			return Path(self.data_path, physical_name)

	def open_data_file(self, physical_name, first_letter_subdirectory=True):
		try:
			return open(self.get_data_path(physical_name,
					first_letter_subdirectory=first_letter_subdirectory), 'rb')
		except FileNotFoundError as fnf:
			raise VssFileNotFoundException("VSS: %s %s" % (fnf.strerror, fnf.filename))

	# Item files can be shared for shared files.
	# Maintain a dictionary for them
	def open_records_file(self, file_class, physical_name, first_letter_subdirectory=False):
		file = self.record_files_by_physical.get(physical_name, None)
		if file is NotImplemented:
			raise VssFileNotFoundException("VSS: File not found %s" %
					(self.get_data_path(physical_name, first_letter_subdirectory=first_letter_subdirectory)))
		if file is not None:
			return file

		# Prevent recursion loop:
		self.record_files_by_physical[physical_name] = NotImplemented

		file = file_class(self, physical_name, first_letter_subdirectory)
		self.record_files_by_physical[physical_name] = file
		return file

	def get_long_name(self, name:vss_name) -> str:
		logical_name = name.short_name
		if name.name_file_offset != 0:
			name_record = self.name_file.get_name_record(name.name_file_offset)
			logical_name = name_record.get(
						name_record.NameKind.Project if name.is_project() else name_record.NameKind.Long,
						logical_name)
		long_name:str = self.logical_name_dict.get(logical_name, None)
		if long_name is None:
			long_name = logical_name.decode(self.encoding)
			self.logical_name_dict[logical_name] = long_name
		return long_name

	def get_index_name(self, short_name:bytes) -> bytes:
		# This name is used for case-insensitive indexing in the project items, even if short_name is empty.
		# VSS sorts the directory by lowercased short name byte values.
		# For proper sort, index_name needs to be 'bytes', because Unicode points may be in different sorting order
		index_name:bytes = self.index_name_dict.get(short_name)
		if index_name is None:
			index_name = short_name.decode(self.encoding).lower().encode(self.encoding)
			self.index_name_dict[short_name] = index_name
		return index_name

	def get_physical_name(self, physical_name:bytes) -> str:
		physical_name = physical_name.upper()
		decoded_name:str = self.physical_name_dict.get(physical_name)
		if decoded_name is None:
			decoded_name = physical_name.decode('ascii')
			self.physical_name_dict[physical_name] = decoded_name
		return decoded_name

	def print(self, fd):
		print('Database:', self.base_path, file=fd)

		self.get_project_tree().print(fd)
		return
