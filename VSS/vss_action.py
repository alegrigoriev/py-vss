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
from .vss_item import ProjectEntryFlag

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

	# The changelist is reconstructed from the most recent state of the project tree
	# back in time. This call reverses the revision being processed
	def apply_to_item_backwards(self, action_item):
		return

	# The function calls functions of the invocation-specific revision action handler
	# to create, modify, label, delete files and directories.
	# For example, such an action handler can convert the actions
	# to Git invocations
	def perform_revision_action(self, revision_action_handler):
		return

# Action on a project file with name
class named_action(vss_action):

	def __init__(self, revision:vss_named_revision, base_path:str):
		super().__init__(revision, base_path, revision.full_name.name)
		self.physical_name = revision.full_name.physical_name
		self.item_index = revision.item_index
		return

	def assert_valid_item(self, item, name=None, physical_name=None):
		if name is None:
			name = self.logical_name
		if physical_name is None:
			physical_name = self.physical_name
		assert(item is not None and item.physical_name == physical_name and item.logical_name == name)
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

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_file_label(path=self.pathname, label=self.label)
		return

class label_project_action(label_action):
	project_action = True

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_dir_label(path=self.pathname, label=self.label)
		return

class add_item_action(named_action):

	def apply_to_item_backwards(self, action_item):
		# In some conditions AddProject action can come before all its child history completes
		# (later on the timeline).
		item = action_item.remove_item_by_index(self.item_index, remove_from_directory=False)
		self.assert_valid_item(item)

		if item.item_file is None:
			self.add_error_string("%s %s could not be added: file %s missing" %
					(self.Project_or_File(), self.pathname, self.physical_name))
		elif self.project_action:
			# If item file is present, the directory will be created by CreateProject
			self.perform_revision_action = super().perform_revision_action
		return

class add_file_action(add_item_action):

	ACTION_STR = "Add File"
	project_action = False

class add_project_action(add_item_action):

	ACTION_STR = "Add Project"
	project_action = True

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_directory(path=self.pathname)
		return

class delete_item_action(named_action):

	def apply_to_item_backwards(self, action_item):
		item = action_item.unset_item_deleted(self.item_index, self.timestamp)
		self.assert_valid_item(item)

		if item.item_file is None:
			self.add_error_string("%s %s could not be deleted: file %s missing" %
					(self.Project_or_File(), self.pathname, self.physical_name))
			if not self.project_action:
				self.perform_revision_action = super().perform_revision_action
		return

class delete_file_action(delete_item_action):

	ACTION_STR = "Delete File"
	project_action = False

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.delete_file(path=self.pathname)
		return

class delete_project_action(delete_item_action):

	ACTION_STR = "Delete Project"
	project_action = True

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.delete_directory(path=self.pathname)
		return

class file_create_action(vss_action):

	# CreateFile action is normally the first in the file item.
	# It contains its initial path and filename

	ACTION_STR = "Create File"
	project_action = False

	def apply_to_item_backwards(self, action_item):
		self.physical_name = action_item.physical_name	# For __str__
		action_item.next_revision = None
		action_item.parent.remove_from_directory(action_item)
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_file(path=self.pathname,
						data=self.revision.revision_data)
		return

class project_create_action(vss_action):

	# CreateProject action is normally the first in the directory item.
	# It contains its initial pathname

	ACTION_STR = "Create Project"
	project_action = True

	def apply_to_item_backwards(self, action_item):
		self.physical_name = action_item.physical_name	# For __str__
		action_item.next_revision = None
		# In some conditions CreateProject action can come later on the timeline,
		# before all its child history completes.
		# This may happen if some of its projects has been restored from an archive
		if action_item.parent is not None:
			action_item.parent.remove_from_directory(action_item)
		else:
			# 'parent' is None for the root project, don't call "create_directory"
			self.perform_revision_action = super().perform_revision_action
		action_item.parent = None
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_directory(path=self.pathname)
		return

class recover_file_action(named_action):

	ACTION_STR = "Recover File"
	project_action = False

	def apply_to_item_backwards(self, action_item):
		item = action_item.set_item_deleted(self.item_index)
		self.assert_valid_item(item)

		if item.item_file is None:
			self.add_error_string("File %s could not be recovered: file %s missing"
					% (self.pathname, self.physical_name))
			self.perform_revision_action = super().perform_revision_action
		else:
			self.data = item.get_next_revision_data()
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_file(path=self.pathname, data=self.data)
		return

class recover_project_action(named_action):

	ACTION_STR = "Recover Project"
	project_action = True

	# Recreate previously deleted files and directories recursively
	def recover_directory(self, item):
		directory_items_list = [ (item.make_full_path(), None) ]
		for child_item in item.all_items():
			if child_item.is_deleted():
				continue
			if child_item.is_project():
				directory_items_list += self.recover_directory(child_item)
			else:
				directory_items_list.append( (child_item.make_full_path(), child_item.get_next_revision_data()) )
			continue
		return directory_items_list

	def apply_to_item_backwards(self, action_item):
		item = action_item.set_item_deleted(self.item_index)
		self.assert_valid_item(item)

		if item.item_file is None:
			self.add_error_string("Project %s could not be recovered: file %s missing"
					% (self.pathname, self.physical_name))
			self.tree_list = [ (self.pathname, None) ]
			return
		# Build and save the tree to be recovered.
		# It can't be done at the time of perform_revision_action call
		self.tree_list = self.recover_directory(item)
		return

	def perform_revision_action(self, revision_action_handler):
		for path, data in self.tree_list:
			if data is None:
				revision_action_handler.create_directory(path=path)
			else:
				revision_action_handler.create_file(path=path, data=data)
			continue
		return

class destroy_action(named_action):

	def __init__(self, revision:vss_destroy_revision, base_path:str):
		super().__init__(revision, base_path)
		self.was_deleted = revision.was_deleted
		return

	def apply_to_item_backwards(self, action_item):
		item = action_item.insert_new_item(self.physical_name, self.logical_name,
						self.project_action, ProjectEntryFlag.Deleted if self.was_deleted else 0,
						start_timestamp=self.timestamp, item_idx=self.item_index)
		if item.item_file is None:
			self.add_error_string("Destroyed item %s could not be traced back: file %s missing"
								% (self.pathname, self.physical_name))
			if not self.project_action or self.was_deleted:
				# The file has never been created, or the directory already deleted
				self.perform_revision_action = super().perform_revision_action
			# else: A directory
		elif self.was_deleted:
			# The directory/file has already been deleted
			self.perform_revision_action = super().perform_revision_action
		return

class destroy_project_action(destroy_action):

	ACTION_STR = "Destroy Project"
	project_action = True

	def perform_revision_action(self, revision_action_handler):
		# If the item still t exists, delete it
		revision_action_handler.delete_directory(path=self.pathname)
		return

class destroy_file_action(destroy_action):

	ACTION_STR = "Destroy File"
	project_action = False

	def perform_revision_action(self, revision_action_handler):
		# If the item still t exists, delete it
		revision_action_handler.delete_file(path=self.pathname)
		return

class rename_action(named_action):

	def __init__(self, revision:vss_rename_revision, base_path:str):
		super().__init__(revision, base_path)
		self.old_item_index = revision.old_item_index
		self.original_name = revision.old_full_name.name
		self.original_pathname = base_path + self.original_name
		return

	def apply_to_item_backwards(self, action_item):
		# Rename the item back
		item = action_item.remove_item_by_index(self.item_index, remove_from_directory=True)
		self.assert_valid_item(item)

		item.logical_name = self.original_name
		action_item.insert_item_by_idx(item, self.old_item_index)

		if item.item_file is None:
			self.add_error_string('Rename: physical name %s not present in the database' % (self.physical_name))
			if not self.project_action:
				self.perform_revision_action = super().perform_revision_action
		elif item.is_deleted():
			# Note that when a shared file is renamed, *all* its shared instances are renamed, even marked deleted
			self.perform_revision_action = super().perform_revision_action
		else:
			# We need to remove and reinsert the item in the pending list,
			# because its sort by name position may change among items with same timestamp
			action_item.remove_pending_item(item)
			action_item.insert_pending_item(item)

		return

	def __str__(self):
		return "Rename %s %s to %s" % (self.project_or_file(), self.original_pathname, self.pathname)

class rename_file_action(rename_action):
	project_action = False

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.rename_file(old_path=self.original_pathname, new_path=self.pathname)
		return

class rename_project_action(rename_action):
	project_action = True

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.rename_directory(old_path=self.original_pathname, new_path=self.pathname)
		return

class move_from_action(named_action):
	project_action = True
	# This action moves a directory from revision.project_path to the revision's project

	def __init__(self, revision:vss_move_revision, base_path:str):
		super().__init__(revision, base_path)
		self.original_pathname = revision.project_path
		return

	def apply_to_item_backwards(self, action_item):
		# Applied in reverse, it moves self.physical_name to self.original_pathname
		item = action_item.remove_item_by_index(self.item_index, remove_from_directory=True)
		self.assert_valid_item(item)

		if item.item_file is not None:
			action_item.remove_pending_item(item)

		if not action_item.move_from_self(item):
			self.perform_revision_action = super().perform_revision_action
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.rename_directory(old_path=self.original_pathname, new_path=self.pathname)
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

	def apply_to_item_backwards(self, action_item):
		# Applied in reverse, it moves self.new_pathname to self.logical_name
		item = action_item.move_to_self(self.physical_name, self.logical_name, self.item_index)
		if item is None:
			self.perform_revision_action = super().perform_revision_action
		elif item.item_file is None:
			self.add_error_string("Unable to move item %s: file %s missing"
								% (self.pathname, self.physical_name))
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.rename_directory(old_path=self.pathname, new_path=self.new_pathname)
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

	def apply_to_item_backwards(self, action_item):
		# Find context at original path and see what's the revision
		item = action_item.remove_item_by_index(self.item_index, remove_from_directory=True)
		self.assert_valid_item(item)

		if item.item_file is None:
			self.add_error_string("File %s could not be shared: file %s missing"
								% (self.pathname, self.physical_name))
			self.perform_revision_action = super().perform_revision_action
			return

		action_item.remove_pending_item(item)
		self.data = item.get_next_revision_data()
		# Find out the original file and see if it exists
		item = action_item.find_by_path_name(self.original_project)
		if item is None or item.item_file is None:
			self.original_pathname = None
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_file(path=self.pathname, data=self.data, copy_from=self.original_pathname)
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

	def apply_to_item_backwards(self, action_item):
		item = action_item.unset_item_pinned(self.item_index, self.timestamp)
		self.assert_valid_item(item)

		if item.item_file is not None:
			self.data = item.item_file.get_revision_data(self.pinned_revision)
		else:
			self.add_error_string("File %s could not be pinned: file %s missing"
								% (self.pathname, self.physical_name))
			self.perform_revision_action = super().perform_revision_action
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.change_file(path=self.pathname, data=self.data)
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

	def apply_to_item_backwards(self, action_item):
		item = action_item.set_item_pinned(self.item_index, self.unpinned_revision)
		self.assert_valid_item(item)

		if item.item_file is not None:
			self.data = item.get_next_revision_data()
		else:
			self.add_error_string("File %s could not be unpinned: file %s missing"
								% (self.pathname, self.physical_name))
			self.perform_revision_action = super().perform_revision_action
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.change_file(path=self.pathname, data=self.data)
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

	def apply_to_item_backwards(self, action_item):
		item = action_item.remove_item_by_index(self.item_index, remove_from_directory=True)
		self.assert_valid_item(item)

		if item.item_file is None:
			self.add_error_string("File %s could not be branched: file %s missing"
									% (self.pathname, self.physical_name))
		new_item = action_item.insert_new_item(self.branch_file, self.logical_name, False,
						start_timestamp=self.timestamp, item_idx=self.item_index)
		if new_item.item_file is None:
			self.add_error_string("Branch source item %s could not be reinserted: file %s missing"
								% (self.pathname, self.branch_file))
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

	def apply_to_item_backwards(self, action_item):
		action_item.next_revision = None
		return

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.change_file(path=self.pathname, data=self.data)
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

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.change_file(path=self.pathname, data=self.data)
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

	def apply_to_item_backwards(self, action_item):
		item = action_item.remove_item_by_index(self.item_index, remove_from_directory=False)
		self.assert_valid_item(item)

		if item.item_file is None:
			self.add_error_string("%s %s could not be restored: file %s missing"
							% (self.Project_or_File(), self.pathname, self.physical_name))
		elif self.project_action:
			# If the project file is present, the directory will be created by its CreateProject
			self.perform_revision_action = super().perform_revision_action
		return

	def __str__(self):
		return "Restore %s %s from archive %s" % (self.project_or_file(), self.pathname, self.archive_path)

class restore_file_action(restore_action):
	project_action = False

class restore_project_action(restore_action):
	project_action = True

	def perform_revision_action(self, revision_action_handler):
		revision_action_handler.create_directory(path=self.pathname)
		return

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
