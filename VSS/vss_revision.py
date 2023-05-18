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
from .vss_item_file import *
from .vss_revision_record import *
from .vss_verbose import *

### vss_revision is associated with logical item: project or an instance of file
class vss_revision:

	PROJECT_REVISION = NotImplemented

	def __init__(self, record:vss_revision_record, database, item_file:vss_item_file):
		self.revision_num:int = record.revision_num
		self.action = int(record.action)
		self.timestamp:int = record.timestamp
		self.author = record.decode(record.user)
		self.revision_data:bytes = None
		self.encoding = database.encoding
		self.label_comment:str = None
		if record.comment_offset > 0 and record.comment_length > 0:
			comment_record:vss_comment_record = item_file.get_record(
							record.comment_offset, vss_comment_record)
			self.comment:str = comment_record.comment
		else:
			self.comment:str = None
		self.item_index:int = None
		return

	def set_revision_data(self, data:bytes):
		self.revision_data = data
		return data

	# This function is called to reconstruct item directory
	def apply_to_project_items(self, item_file:vss_project_item_file):
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		print("%sRevision: %d" % (indent, self.revision_num), file=fd)
		print("%sBy: '%s', at: %s (%d)" % (indent, self.author,
						timestamp_to_datetime(self.timestamp), self.timestamp), file=fd)
		print("%s%s (%d)" % (indent, VssRevisionAction(self.action), self.action), file=fd)

		if self.comment:
			indent += '  '
			print("%sComment: %s" % (indent, indent_string(self.comment, indent + '         ')), file=fd)
		return

class vss_label_revision(vss_revision):

	def __init__(self, record:vss_revision_record, database, item_file:vss_item_file):
		super().__init__(record, database, item_file)
		self.label:str = record.decode(record.label)

		if record.label_comment_offset > 0 and record.label_comment_length > 0:
			label_comment_record:vss_comment_record = item_file.get_record(
								record.label_comment_offset, vss_comment_record)
			self.label_comment:str = label_comment_record.comment
		else:
			self.label_comment:str = None
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		if self.label_comment:
			indent += '  '
			print("%sLabel comment: %s" % (indent, indent_string(
							self.label_comment, indent + '               ')), file=fd)
		return

class vss_full_name:
	def __init__(self, database, logical_name:vss_name, physical_name:bytes):
		self.is_project:bool = logical_name.is_project()
		self.name:bytes = database.get_long_name(logical_name)
		self.physical_name = database.get_physical_name(physical_name)
		self.index_name:bytes = database.get_index_name(logical_name.short_name)
		return

	def __str__(self):
		s = self.name
		if self.is_project:
			s += '/'
		if self.physical_name:
			s += " (%s)" % (self.physical_name,)
		return s

class vss_named_revision(vss_revision):

	def __init__(self, record:vss_revision_record, database, item_file:vss_item_file):
		super().__init__(record, database, item_file)
		self.full_name = vss_full_name(database, record.name, record.physical)
		if self.full_name.is_project != self.PROJECT_REVISION:
			assert(self.full_name.is_project == self.PROJECT_REVISION)
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		print("%sName: %s" % (indent, self.full_name), file=fd)
		return

class vss_create_revision(vss_named_revision):
	...

class vss_create_project_revision(vss_create_revision):
	PROJECT_REVISION = True

class vss_create_file_revision(vss_create_revision):
	PROJECT_REVISION = False

class vss_add_revision(vss_named_revision):

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index = item_file.add_item(self.full_name)
		return

class vss_add_project_revision(vss_add_revision):
	PROJECT_REVISION = True

class vss_add_file_revision(vss_add_revision):
	PROJECT_REVISION = False

class vss_delete_revision(vss_named_revision):

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index = item_file.find_item(self.full_name)
		assert(self.item_index >= 0)
		return

class vss_delete_project_revision(vss_delete_revision):
	PROJECT_REVISION = True

class vss_delete_file_revision(vss_delete_revision):
	PROJECT_REVISION = False

class vss_recover_revision(vss_named_revision):

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index = item_file.find_item(self.full_name)
		assert(self.item_index >= 0)
		return

class vss_recover_project_revision(vss_recover_revision):
	PROJECT_REVISION = True

class vss_recover_file_revision(vss_recover_revision):
	PROJECT_REVISION = False

class vss_destroy_revision(vss_named_revision):

	def __init__(self, record:vss_destroy_revision_record, database, item_file:vss_project_item_file):
		super().__init__(record, database, item_file)
		self.was_deleted = record.was_deleted != 0
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		if self.was_deleted:
			print(indent + "Previously deleted", file=fd)
		return

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index, item = item_file.remove_item(self.full_name)
		assert(item is not None and self.item_index >= 0)
		return

class vss_destroy_project_revision(vss_destroy_revision):
	PROJECT_REVISION = True

class vss_destroy_file_revision(vss_destroy_revision):
	PROJECT_REVISION = False

class vss_rename_revision(vss_named_revision):
	def __init__(self, record:vss_rename_revision_record, database, item_file:vss_project_item_file):
		super().__init__(record, database, item_file)
		self.old_full_name = vss_full_name(database, record.old_name, record.physical)
		return

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.old_item_index, item = item_file.remove_item(self.old_full_name)
		assert(item is not None and self.old_item_index >= 0)
		self.item_index = item_file.add_item(self.full_name)
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		print("%sOld name: %s" % (indent, self.old_full_name), file=fd)
		return

class vss_rename_project_revision(vss_rename_revision):
	PROJECT_REVISION = True

class vss_rename_file_revision(vss_rename_revision):
	PROJECT_REVISION = False

class vss_move_revision(vss_named_revision):
	PROJECT_REVISION = True

	def __init__(self, record:vss_move_revision_record, database, item_file:vss_project_item_file):
		super().__init__(record, database, item_file)
		self.project_path = record.decode(record.project_path)
		return

class vss_move_from_revision(vss_move_revision):

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index = item_file.add_item(self.full_name)
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		print("%sMove from: %s" % (indent, self.project_path), file=fd)
		return

class vss_move_to_revision(vss_move_revision):

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index, item = item_file.remove_item(self.full_name)
		assert(item is not None and self.item_index >= 0)
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		print("%sMove to: %s" % (indent, self.project_path), file=fd)
		return

class vss_share_revision(vss_named_revision):
	PROJECT_REVISION = False

	def __init__(self, record:vss_share_revision_record, database, item_file:vss_project_item_file):
		super().__init__(record, database, item_file)
		self.project_path = record.decode(record.project_path)
		self.item_index = record.project_idx
		self.pinned_revision = record.pinned_revision
		self.unpinned_revision = record.unpinned_revision
		return

	def apply_to_project_items(self, item_file:vss_project_item_file):
		if self.unpinned_revision < 0:
			item_file.insert_item(self.item_index, self.full_name)
		else:
			# Pin or unpin file
			item = item_file.get_item(self.item_index)
			assert(item is not None and item.physical_name == self.full_name.physical_name)
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		if self.unpinned_revision == 0:
			print("%sPinned revision: %d" % (indent, self.pinned_revision), file=fd)
		elif self.unpinned_revision > 0:
			print("%sUnpinned revision: %d" % (indent, self.unpinned_revision), file=fd)
		else:
			print("%sShare from: %s" % (indent, self.project_path), file=fd)
		return

class vss_checkin_revision(vss_revision):

	def __init__(self, record:vss_checkin_revision_record, database, item_file:vss_item_file):
		super().__init__(record, database, item_file)

		self.project_path = record.decode(record.project_path)
		if record.prev_delta_offset > 0:
			self.delta_record = item_file.get_record(record.prev_delta_offset, vss_delta_record)
		else:
			self.delta_record = None
		return

	def set_revision_data(self, data:bytes):
		data = super().set_revision_data(data)
		if self.delta_record is not None:
			data = self.delta_record.apply_delta(data)
		return data

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		print("%sChecked in at: %s" % (indent, self.project_path), file=fd)
		return

class vss_branch_revision(vss_named_revision):
	PROJECT_REVISION = False

	def __init__(self, record:vss_branch_revision_record, database, item_file:vss_item_file):
		super().__init__(record, database, item_file)

		self.source_full_name = vss_full_name(database, record.name, record.branch_file)
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		print("%sBranched from: %s" % (indent, self.source_full_name), file=fd)
		return

class vss_create_branch_revision(vss_branch_revision):
	...

class vss_branch_file_revision(vss_branch_revision):

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index = item_file.find_item(self.source_full_name)
		assert(self.item_index >= 0)
		item_file.remove_item_by_idx(self.item_index)
		item_file.insert_item(self.item_index, self.full_name)
		return

class vss_archive_restore_revision(vss_named_revision):

	def __init__(self, record:vss_revision_record, database, item_file:vss_project_item_file):
		super().__init__(record, database, item_file)
		self.archive_path = record.decode(record.archive_path)
		return

	def print(self, fd, indent:str='', verbose:VerboseFlags=VerboseFlags.FileRevisions):
		super().print(fd, indent, verbose)

		print("%sArchive path: %s" % (indent, self.archive_path), file=fd)
		return

class vss_archive_revision(vss_archive_restore_revision):
	...

class vss_archive_file_revision(vss_archive_revision):
	PROJECT_REVISION = False

class vss_archive_project_revision(vss_archive_revision):
	PROJECT_REVISION = True

class vss_restore_revision(vss_archive_restore_revision):

	def apply_to_project_items(self, item_file:vss_project_item_file):
		self.item_index = item_file.add_item(self.full_name)
		return

class vss_restore_file_revision(vss_restore_revision):
	PROJECT_REVISION = False

class vss_restore_project_revision(vss_restore_revision):
	PROJECT_REVISION = True

file_revision_class_dict = {
	int(VssRevisionAction.Label) : vss_label_revision,
	int(VssRevisionAction.CreateFile) : vss_create_file_revision,
	int(VssRevisionAction.CreateBranch) : vss_create_branch_revision,
	int(VssRevisionAction.CheckinFile) : vss_checkin_revision,
	int(VssRevisionAction.ArchiveFile) : vss_archive_file_revision,
}

def vss_file_revision_factory(record:vss_revision_record, database, item_file:vss_file_item_file)->vss_revision:
	revision_class = file_revision_class_dict.get(int(record.action), None)
	if revision_class is None:
		raise UnrecognizedRevActionException("Unrecognized file revision action", str(record.action))
	return revision_class(record, database, item_file)

project_revision_class_dict = {
	int(VssRevisionAction.Label) : vss_label_revision,
	int(VssRevisionAction.DestroyProject) : vss_destroy_project_revision,
	int(VssRevisionAction.DestroyFile) : vss_destroy_file_revision,
	int(VssRevisionAction.RenameProject) : vss_rename_project_revision,
	int(VssRevisionAction.RenameFile) : vss_rename_file_revision,
	int(VssRevisionAction.MoveFrom) : vss_move_from_revision,
	int(VssRevisionAction.MoveTo) : vss_move_to_revision,
	int(VssRevisionAction.ShareFile) : vss_share_revision,
	int(VssRevisionAction.BranchFile) : vss_branch_file_revision,
	int(VssRevisionAction.ArchiveFile) : vss_archive_file_revision,
	int(VssRevisionAction.ArchiveProject) : vss_archive_project_revision,
	int(VssRevisionAction.RestoreFile) : vss_restore_file_revision,
	int(VssRevisionAction.RestoreProject) : vss_restore_project_revision,
	int(VssRevisionAction.CreateProject) : vss_create_project_revision,
	int(VssRevisionAction.AddProject) : vss_add_project_revision,
	int(VssRevisionAction.AddFile) : vss_add_file_revision,
	int(VssRevisionAction.DeleteProject) : vss_delete_project_revision,
	int(VssRevisionAction.DeleteFile) : vss_delete_file_revision,
	int(VssRevisionAction.RecoverProject) : vss_recover_project_revision,
	int(VssRevisionAction.RecoverFile) : vss_recover_file_revision,
}

def vss_project_revision_factory(record:vss_revision_record, database, item_file:vss_project_item_file)->vss_revision:
	revision_class = project_revision_class_dict.get(int(record.action), None)
	if revision_class is None:
		raise UnrecognizedRevActionException("Unrecognized project revision action", str(record.action))
	return revision_class(record, database, item_file)
