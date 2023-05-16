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
from .vss_exception import UnrecognizedRecordException, RecordClassMismatchException
from .vss_record import *

from typing import DefaultDict

class vss_record_file:
	def __init__(self, database:vss_database, filename:str, first_letter_subdirectory=True):
		self.filename = filename
		self.header = None

		with database.open_data_file(filename,
				first_letter_subdirectory=first_letter_subdirectory) as file:
			self.reader = vss_record_reader(file.read(), encoding=database.encoding)
			self.file_size = self.reader.length

		# All records by offset
		self.records:DefaultDict[int, vss_record] = {}
		return

	### Read one record, using 'record_factory' to create record object.
	# The record must match its class SIGNATURE
	# 'record_class' can also be a record factory.
	def read_record(self, record_factory, offset:int=None, ignore_unknown:bool=False):
		if offset is not None:
			self.reader.offset = offset
		else:
			offset = self.reader.offset

		try:
			record_header = vss_record_header(self.reader)
			record_header.check_crc()

			record = record_factory.create_record(record_header)

			if record is not None:
				record_header.check_signature(record.SIGNATURE)
				record.read()
			elif not ignore_unknown:
				raise UnrecognizedRecordException(
					"Unrecognized record signature %s in file %s" % (record_header.signature.decode(), self.filename))

			return record

		except EndOfBufferException as e:
			raise RecordTruncatedException(*e.args)
		return

	### Read all records, using 'record_factory' to create record objects.
	# All records must match its class SIGNATURE
	def read_all_records(self, record_factory, offset=None, last_offset=None, ignore_unknown:bool=False):
		if offset is None:
			offset = self.reader.offset
		if last_offset is None:
			last_offset = self.file_size
		while offset + vss_record_header.LENGTH <= last_offset:
			record = self.get_record(offset, record_factory)
			if record is not None:
				offset += record.header.length + record.header.LENGTH
				continue
			record = self.read_record(record_factory, offset=offset, ignore_unknown=ignore_unknown)
			if record is not None:
				self.records[offset] = record
			offset = self.reader.offset
			continue
		return self.records.values()

	def get_record(self, offset:int, record_class=None) -> vss_record:
		record = self.records.get(offset, None)
		if record is not None and record_class is not None and \
				not record_class.valid_record_class(record):
			raise RecordClassMismatchException(
				"Mismatched record class at offset %06X in item file %s, expected %s, actual %s"
					% (offset, self.filename, record_class.__name__, type(record).__name__))
		return record

	def print(self, fd, indent:str=''):
		if self.header is not None:
			print(indent + "Header:", file=fd)
			self.header.print(fd, indent+'  ')

		for record in self.records.values():
			record.print(fd, indent)
		return
