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
from .vss_exception import EndOfBufferException, RecordTruncatedException
from .vss_record import *

class vss_record_file:
	def __init__(self, database:vss_database, filename:str, first_letter_subdirectory=True):
		self.filename = filename
		self.header = None

		with database.open_data_file(filename,
				first_letter_subdirectory=first_letter_subdirectory) as file:
			self.reader = vss_record_reader(file.read(), encoding=database.encoding)
			self.file_size = self.reader.length

		return

	### Read one record of 'record_class'. The record must match record_class.SIGNATURE
	def read_record(self, record_class, offset:int=None):
		if offset is not None:
			self.reader.offset = offset
		else:
			offset = self.reader.offset

		try:
			record_header = vss_record_header(self.reader)
			record_header.check_crc()

			record = record_class(record_header)

			record_header.check_signature(record_class.SIGNATURE)
			record.read()

			return record

		except EndOfBufferException as e:
			raise RecordTruncatedException(*e.args)
		return

	def print(self, fd):
		if self.header is not None:
			print("Header:", file=fd)
			self.header.print(fd)

		for record in self.records.values():
			record.print(fd)
		return
