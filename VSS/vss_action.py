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
from .vss_revision import *
from .vss_exception import UnrecognizedRevActionException

class vss_action:

	ACTION_STR = NotImplemented
	project_action = NotImplemented

	def __init__(self, revision:vss_revision, base_path:str, logical_name:str=''):
		self.revision = revision
		self.timestamp = revision.timestamp
		self.logical_name = logical_name
		self.base_path = base_path
		self.pathname = base_path + logical_name
		self.errors = []
		return

	def add_error_string(self, error_str):
		self.errors.append(error_str)
		return

	def __str__(self):
		return self.ACTION_STR + ' ' + self.pathname

	def project_or_file(self):
		if self.project_action:
			return 'project'
		return 'file'

	def Project_or_File(self):
		if self.project_action:
			return 'Project'
		return 'File'

# Action on a project file with name
class named_action(vss_action):

	def __init__(self, revision:vss_named_revision, base_path:str):
		super().__init__(revision, base_path, revision.full_name.name)
		self.physical_name = revision.full_name.physical_name
		self.item_index = revision.item_index
		return

class label_action(vss_action):

	def __init__(self, revision:vss_label_revision, base_path:str):
		super().__init__(revision, base_path)
		self.label = revision.label
		return

	def __str__(self):
		return "Label %s %s as:%s" % (self.project_or_file(), self.pathname, self.label)

class label_file_action(label_action):
	project_action = False

class label_project_action(label_action):
	project_action = True

class add_item_action(named_action):
	...

class add_file_action(add_item_action):

	ACTION_STR = "Add File"
	project_action = False

class add_project_action(add_item_action):

	ACTION_STR = "Add Project"
	project_action = True

class delete_item_action(named_action):
	...

class delete_file_action(delete_item_action):

	ACTION_STR = "Delete File"
	project_action = False

class delete_project_action(delete_item_action):

	ACTION_STR = "Delete Project"
	project_action = True

class file_create_action(vss_action):

	# CreateFile action is normally the first in the file item.
	# It contains its initial path and filename

	ACTION_STR = "Create File"
	project_action = False

class project_create_action(vss_action):

	# CreateProject action is normally the first in the directory item.
	# It contains its initial pathname

	ACTION_STR = "Create Project"
	project_action = True

class recover_file_action(named_action):

	ACTION_STR = "Recover File"
	project_action = False

class recover_project_action(named_action):

	ACTION_STR = "Recover Project"
	project_action = True

class destroy_action(named_action):

	def __init__(self, revision:vss_destroy_revision, base_path:str):
		super().__init__(revision, base_path)
		self.was_deleted = revision.was_deleted
		return

class destroy_project_action(destroy_action):

	ACTION_STR = "Destroy Project"
	project_action = True

class destroy_file_action(destroy_action):

	ACTION_STR = "Destroy File"
	project_action = False

class rename_action(named_action):

	def __init__(self, revision:vss_rename_revision, base_path:str):
		super().__init__(revision, base_path)
		self.old_item_index = revision.old_item_index
		self.original_name = revision.old_full_name.name
		self.original_pathname = base_path + self.original_name
		return

	def __str__(self):
		return "Rename %s %s to %s" % (self.project_or_file(), self.original_pathname, self.pathname)

class rename_file_action(rename_action):
	project_action = False

class rename_project_action(rename_action):
	project_action = True

class move_from_action(named_action):
	project_action = True
	# This action moves a directory from revision.project_path to the revision's project

	def __init__(self, revision:vss_move_revision, base_path:str):
		super().__init__(revision, base_path)
		self.original_pathname = revision.project_path
		return

	def __str__(self):
		return "Move %s from %s" % (self.pathname, self.original_pathname)

class move_to_action(named_action):
	project_action = True
	# This action moves a directory from revision's directory to revision.project_path

	def __init__(self, revision:vss_move_revision, base_path:str):
		super().__init__(revision, base_path)
		self.new_pathname = revision.project_path
		return

	def __str__(self):
		return "Move %s to %s" % (self.pathname, self.new_pathname)

class share_action(named_action):
	project_action = False

	def __init__(self, revision:vss_share_revision, base_path:str):
		super().__init__(revision, base_path)
		self.original_project = revision.project_path
		self.original_pathname = self.original_project + '/' + self.logical_name
		self.data = None
		return

	def __str__(self):
		return "Share %s from %s" % (self.pathname, self.original_project)

class pin_action(named_action):
	project_action = False

	def __init__(self, revision:vss_share_revision, base_path:str):
		super().__init__(revision, base_path)
		self.pinned_revision = revision.pinned_revision
		self.data = None
		return

	def __str__(self):
		return "Pin %s at revision %d" % (self.pathname, self.pinned_revision)

class unpin_action(named_action):
	project_action = False

	def __init__(self, revision:vss_share_revision, base_path:str):
		super().__init__(revision, base_path)
		self.unpinned_revision = revision.unpinned_revision
		self.data = None
		return

	def __str__(self):
		return "Unpin %s at revision %d" % (self.pathname, self.unpinned_revision)

def create_share_action(revision:vss_share_revision, base_path):
	if revision.unpinned_revision == 0:
		return pin_action(revision, base_path)
	elif revision.unpinned_revision > 0:
		return unpin_action(revision, base_path)
	return share_action(revision, base_path)

class branch_file_action(named_action):
	project_action = True

	def __init__(self, revision:vss_branch_revision, base_path:str):
		super().__init__(revision, base_path)
		self.branch_file = revision.source_full_name.physical_name
		return

	def __str__(self):
		return "Branch File %s from %s" % (self.pathname, self.branch_file)

class create_branch_action(vss_action):
	project_action = False

	def __init__(self, revision:vss_branch_revision, base_path:str):
		super().__init__(revision, base_path)
		self.branch_file = revision.source_full_name.physical_name
		self.data = revision.revision_data
		return

	def __str__(self):
		return "Create Branch %s from %s" % (self.pathname, self.branch_file)

class checkin_action(vss_action):
	project_action = False

	ACTION_STR = "Checkin"

	def __init__(self, revision:vss_checkin_revision, base_path:str):
		super().__init__(revision, base_path)
		self.data = revision.revision_data
		return

class archive_restore_action(named_action):

	def __init__(self, revision:vss_archive_restore_revision, base_path:str):
		super().__init__(revision, base_path)
		self.archive_path = revision.archive_path
		return

class archive_action(archive_restore_action):

	def __str__(self):
		return "Archive %s %s to %s" % (self.project_or_file(), self.pathname, self.archive_path)

class archive_file_action(archive_action):
	project_action = False

class archive_project_action(archive_action):
	project_action = True

class restore_action(archive_restore_action):

	def __str__(self):
		return "Restore %s %s from archive %s" % (self.project_or_file(), self.pathname, self.archive_path)

class restore_file_action(restore_action):
	project_action = False

class restore_project_action(restore_action):
	project_action = True

file_action_dict = {
	int(VssRevisionAction.Label) : label_file_action,
	int(VssRevisionAction.CreateBranch) : create_branch_action,
	int(VssRevisionAction.CheckinFile) : checkin_action,
	int(VssRevisionAction.ArchiveFile) : archive_file_action,
	int(VssRevisionAction.CreateFile) : file_create_action,
}

def create_file_action(revision:vss_revision, base_path):
	action_class = file_action_dict.get(revision.action, None)
	if action_class is not None:
		return action_class(revision, base_path)
	raise UnrecognizedRevActionException("Unrecognized file revision action", str(revision.action))

project_action_dict = {
	int(VssRevisionAction.Label) : label_project_action,
	int(VssRevisionAction.DestroyProject) : destroy_project_action,
	int(VssRevisionAction.DestroyFile) : destroy_file_action,
	int(VssRevisionAction.RenameProject) : rename_project_action,
	int(VssRevisionAction.RenameFile) : rename_file_action,
	int(VssRevisionAction.MoveFrom) : move_from_action,
	int(VssRevisionAction.MoveTo) : move_to_action,
	int(VssRevisionAction.ShareFile) : create_share_action,
	int(VssRevisionAction.BranchFile) : branch_file_action,
	int(VssRevisionAction.ArchiveFile) : archive_file_action,
	int(VssRevisionAction.ArchiveProject) : archive_project_action,
	int(VssRevisionAction.RestoreFile) : restore_file_action,
	int(VssRevisionAction.RestoreProject) : restore_project_action,
	int(VssRevisionAction.CreateProject) : project_create_action,
	int(VssRevisionAction.AddProject) : add_project_action,
	int(VssRevisionAction.AddFile) : add_file_action,
	int(VssRevisionAction.DeleteProject) : delete_project_action,
	int(VssRevisionAction.DeleteFile) : delete_file_action,
	int(VssRevisionAction.RecoverProject) : recover_project_action,
	int(VssRevisionAction.RecoverFile) : recover_file_action,
}

def create_project_action(revision:vss_revision, base_path):
	action_class = project_action_dict.get(revision.action, None)
	if action_class is not None:
		return action_class(revision, base_path)
	raise UnrecognizedRevActionException("Unrecognized project revision action", str(revision.action))
