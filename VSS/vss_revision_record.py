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
from .vss_exception import UnrecognizedRevActionException
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

class vss_label_revision_record(vss_revision_record):

	def print(self, fd):
		super().print(fd)

		print("  Label: %s" % (self.decode(self.label)), file=fd)
		return

class vss_common_revision_record(vss_revision_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.name:vss_name = None
		self.physical:bytes = None
		return

	def read(self):
		super().read()

		self.name = self.reader.read_name()
		self.physical = self.reader.read_byte_string(10)
		return

	def print(self, fd):
		super().print(fd)

		print("  Name: %s" % (self.decode_name(self.name, self.physical)), file=fd)
		return

class vss_destroy_revision_record(vss_revision_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.name:vss_name = None
		self.was_deleted:int = None
		self.physical:bytes = None
		return

	def read(self):
		super().read()

		self.name = self.reader.read_name()
		# 'was_deleted' is non-zero if the item was previously deleted, and now purged
		# It is zero if the item has been destroyed without having been deleted
		self.was_deleted = self.reader.read_uint16()
		self.physical = self.reader.read_byte_string(10)
		return

	def print(self, fd):
		super().print(fd)

		if self.was_deleted:
			print("  Previously deleted: %d" % (self.was_deleted), file=fd)
		print("  Name: %s" % (self.decode_name(self.name, self.physical)), file=fd)
		return

class vss_rename_revision_record(vss_revision_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.name:vss_name = None
		self.old_name:vss_name = None
		self.physical:bytes = None
		return

	def read(self):
		super().read()

		self.name = self.reader.read_name()
		self.old_name = self.reader.read_name()
		self.physical = self.reader.read_byte_string(10)
		return

	def print(self, fd):
		super().print(fd)

		print("  Name: %s -> %s" % (self.decode_name(self.old_name),
								self.decode_name(self.name, self.physical)), file=fd)
		return

class vss_move_revision_record(vss_revision_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.project_path:str = None
		self.name:vss_name = None
		self.physical:bytes = None
		return

	def read(self):
		super().read()

		self.project_path = self.reader.read_byte_string(260)
		self.name = self.reader.read_name()
		self.physical = self.reader.read_byte_string(10)
		return

	def print(self, fd):
		super().print(fd)

		print("  Project path: %s" % (self.decode(self.project_path)), file=fd)
		print("  Name: %s" % (self.decode_name(self.name, self.physical)), file=fd)
		return

class vss_share_revision_record(vss_revision_record):
	vss_share_unpack_struct = struct.Struct(b'<hhh')

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.project_path:bytes = None
		self.name:vss_name = None
		self.unpinned_revision:int = None
		self.pinned_revision:int = None
		self.project_idx:int = None
		self.physical:bytes = None
		return

	def read(self):
		super().read()
		reader = self.reader

		self.project_path = reader.read_byte_string(260)
		self.name = reader.read_name()
		(
			self.unpinned_revision,
			self.pinned_revision,
			# Index in the project items file:
			self.project_idx,
		) = reader.unpack(self.vss_share_unpack_struct)
		self.physical = reader.read_byte_string(10)
		return

	def print(self, fd):
		super().print(fd)

		print("  Name: %s" % (self.decode_name(self.name, self.physical)), file=fd)
		print("  Share from path: %s" % (self.decode(self.project_path)), file=fd)
		print("  Index in items array: %d" % (self.project_idx), file=fd)
		if self.unpinned_revision == 0:
			print("  Pinned at revision: %d" % (self.pinned_revision), file=fd)
		elif self.unpinned_revision > 0:
			print("  Unpinned at revision: %d" % (self.unpinned_revision), file=fd)
		return

class vss_branch_revision_record(vss_common_revision_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.branch_file:str = None
		return

	def read(self):
		super().read()

		self.branch_file = self.reader.read_byte_string(10)
		return

	def print(self, fd):
		super().print(fd)

		print("  Branched from file: %s" % (self.decode(self.branch_file)), file=fd)
		return

class vss_checkin_revision_record(vss_revision_record):
	vss_checkin_unpack_struct = struct.Struct(b'<II')

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.project_path:bytes = None
		self.prev_delta_offset:int = None
		return

	def read(self):
		super().read()

		(
			self.prev_delta_offset,
			self.filler,
		) = self.reader.unpack(self.vss_checkin_unpack_struct)
		self.project_path = self.reader.read_byte_string(260)

		return

	def print(self, fd):
		super().print(fd)

		print("  Prev delta offset: %06X" % (self.prev_delta_offset), file=fd)
		if self.filler:
			print("  Filler: %08X" % (self.filler), file=fd)
		print("  Project path: %s" % (self.decode(self.project_path)), file=fd)
		return

class vss_archive_restore_revision_record(vss_common_revision_record):

	def __init__(self, header:vss_record_header):
		super().__init__(header)

		self.archive_path:bytes = None
		return

	def read(self):
		super().read()

		self.filler16 = self.reader.read_uint16()
		self.archive_path = self.reader.read_byte_string(260)
		self.filler32 = self.reader.read_uint32()
		# NOTE: Two more words in the record may be meaningful
		return

	def print(self, fd):
		super().print(fd)

		if self.filler16:
			print("  Filler: %04X" % (self.filler16), file=fd)
		print("  Archive path: %s" % (self.decode(self.archive_path)), file=fd)
		if self.filler32:
			print("  Filler: %08X" % (self.filler32), file=fd)
		return

class vss_revision_record_factory:
	class_dict = {
		int(VssRevisionAction.Label) : vss_label_revision_record,
		int(VssRevisionAction.DestroyProject) : vss_destroy_revision_record,
		int(VssRevisionAction.DestroyFile) : vss_destroy_revision_record,
		int(VssRevisionAction.RenameProject) : vss_rename_revision_record,
		int(VssRevisionAction.RenameFile) : vss_rename_revision_record,
		int(VssRevisionAction.MoveFrom) : vss_move_revision_record,
		int(VssRevisionAction.MoveTo) : vss_move_revision_record,
		int(VssRevisionAction.ShareFile) : vss_share_revision_record,
		int(VssRevisionAction.BranchFile) : vss_branch_revision_record,
		int(VssRevisionAction.CreateBranch) : vss_branch_revision_record,
		int(VssRevisionAction.CheckinFile) : vss_checkin_revision_record,
		int(VssRevisionAction.ArchiveFile) : vss_archive_restore_revision_record,
		int(VssRevisionAction.ArchiveProject) : vss_archive_restore_revision_record,
		int(VssRevisionAction.RestoreFile) : vss_archive_restore_revision_record,
		int(VssRevisionAction.RestoreProject) : vss_archive_restore_revision_record,
		int(VssRevisionAction.CreateProject) : vss_common_revision_record,
		int(VssRevisionAction.CreateFile) : vss_common_revision_record,
		int(VssRevisionAction.AddProject) : vss_common_revision_record,
		int(VssRevisionAction.AddFile) : vss_common_revision_record,
		int(VssRevisionAction.DeleteProject) : vss_common_revision_record,
		int(VssRevisionAction.DeleteFile) : vss_common_revision_record,
		int(VssRevisionAction.RecoverProject) : vss_common_revision_record,
		int(VssRevisionAction.RecoverFile) : vss_common_revision_record,
	}

	@classmethod
	def create_record(cls, record_header)->vss_revision_record:
		action = record_header.reader.read_int16_at(4)
		record_class = cls.class_dict.get(action, None)
		if record_class is not None:
			return record_class.create_record(record_header)
		raise UnrecognizedRevActionException("Unrecognized revision action", str(action))

	@classmethod
	def valid_record_class(cls, record):
		record_class = cls.class_dict.get(record.action, None)
		return record_class is not None and \
			record_class.valid_record_class(record)

