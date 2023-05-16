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
from .vss_record import vss_record, vss_record_header
from .vss_record_file import vss_record_file
from .vss_database import vss_database
from enum import IntEnum

class vss_name_header_record(vss_record):

	SIGNATURE = b"HN"

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.eof_offset:int = 0
		return

	def read(self):
		super().read()

		self.filler_words = (
			self.reader.read_uint32(),
			self.reader.read_uint32(),
			self.reader.read_uint32(),
			self.reader.read_uint32(),
			)
		self.eof_offset = self.reader.read_int32()
		return

	def print(self, fd, indent:str=''):
		super().print(fd, indent)

		if any(self.filler_words):
			print("%sFiller: %08X %08X %08X %08X" % (indent, *self.filler_words), file=fd)
		print("%sEOF offset: %06X" % (indent, self.eof_offset), file=fd)
		return

class vss_name_record(vss_record):

	SIGNATURE = b"SN"

	class NameKind(IntEnum):
		Dos        = 1
		Long       = 2
		MacOS      = 3
		Project    = 10

		def __str__(self):
			if self == self.Dos: return 'Dos'
			if self == self.Long: return 'Long'
			if self == self.MacOS: return 'MacOS'
			if self == self.Project: return 'Project'
			return str(int(self))

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.names:DefaultDict[int,str] = {}
		return

	def read(self):
		super().read()
		reader = self.reader

		name_kind_count = reader.read_int16()
		reader.skip(2)
		name_str_reader = reader.clone(additional_offset=name_kind_count*4)
		for i in range(name_kind_count):
			name_kind = reader.read_int16()
			name_offset = reader.read_int16()
			self.names[name_kind] = name_str_reader.read_byte_string_at(name_offset)
		return

	def get(self, name_kind, default_value=None):
		return self.names.get(int(name_kind), default_value)

	def print(self, fd, indent:str=''):
		super().print(fd, indent)

		print("%sNum names: %d" % (indent, len(self.names)), file=fd)
		for name_kind, name in self.names.items():
			print("%s  %s: %s" % (indent, self.NameKind(name_kind), self.decode(name)), file=fd)

		return

class vss_name_file(vss_record_file):
	def __init__(self, database:vss_database, filename:str):
		# names.dat file is stored directly under data/,
		super().__init__(database, filename, first_letter_subdirectory=False)

		self.header:vss_name_header_record = self.read_record(vss_name_header_record)

		# Fill the record dictionary
		self.read_all_records(vss_name_record, last_offset=self.header.eof_offset)
		return

	def get_name_record(self, name_offset)->vss_name_record:
		return self.get_record(name_offset)

	def print(self, fd, indent:str=''):
		print("%sName file %s" % (indent, self.filename), file=fd)

		super().print(fd, indent)
		return
