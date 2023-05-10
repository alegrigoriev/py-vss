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

		self.ini_path:Path = Path(path, "srcsafe.ini")

		ini_reader = simple_ini_parser(self.ini_path)

		data_path = ini_reader.get("Data_Path", "data")
		self.data_path = Path(path, data_path)

		return

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

	def print(self, fd):
		print('Database:', self.base_path, file=fd)

		return
