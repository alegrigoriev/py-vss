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
import struct
from .vss_record import *
from enum import IntEnum

class VssRevisionAction(IntEnum):
	Label              = 0
	CreateProject      = 1
	AddProject         = 2
	AddFile            = 3
	DestroyProject     = 4
	DestroyFile        = 5
	DeleteProject      = 6
	DeleteFile         = 7
	RecoverProject     = 8
	RecoverFile        = 9
	RenameProject      = 10
	RenameFile         = 11
	MoveFrom           = 12
	MoveTo             = 13

	ShareFile          = 14		# also used to pin and unpin files
	BranchFile         = 15
	CreateFile         = 16
	CheckinFile        = 17
	CheckInProject     = 18
	CreateBranch       = 19

	ArchiveVersionFile = 20
	RestoreVersionFile = 21
	ArchiveFile        = 22
	ArchiveProject     = 23
	RestoreFile        = 24
	RestoreProject     = 25

	def __str__(self):
		# Don't want the class name
		return super().__str__().removeprefix('VssRevisionAction.')

class vss_revision_record(vss_record):

	SIGNATURE = b"EL"
	unpack_format = struct.Struct(b'<IHHI32s32sIIHH')

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.prev_rev_offset:int = None
		self.action:int = None
		self.revision_num:int = None
		self.timestamp:int = None
		self.user:str = None
		self.label:str = None
		self.comment_offset:int = None
		self.label_comment_offset:int = None
		self.comment_length:int = None
		self.label_comment_length:int = None
		return

	def read(self):
		super().read()

		# Format: '<IHHI32s32sIIHH'
		(
			self.prev_rev_offset,		# I
			self.action,				# H
			self.revision_num,			# H
			self.timestamp,				# I
			user,						# 32s
			label,						# 32s
			self.comment_offset,		# I
			self.label_comment_offset,	# I
			self.comment_length,		# H
			self.label_comment_length,	# H
		) = self.reader.unpack(self.unpack_format)

		self.user = zero_terminated(user)
		self.label = zero_terminated(label)
		return

	def print(self, fd):
		super().print(fd)

		print("Revision: %d" % (self.revision_num), file=fd)
		print("  By: '%s', at: %s (%d)" % (self.decode(self.user), timestamp_to_datetime(self.timestamp), self.timestamp), file=fd)
		print("  %s (%d)" % (VssRevisionAction(self.action), self.action), file=fd)
		print("  Prev rev offset: %06X" % (self.prev_rev_offset), file=fd)

		if self.comment_offset != 0:
			print("  Comment offset: %06X, length: %04X" %
				(self.comment_offset, self.comment_length), file=fd)
		if self.label_comment_offset != 0:
			print("  Label comment offset: %06X, length: %04X" %
				(self.label_comment_offset, self.label_comment_length), file=fd)
		return
