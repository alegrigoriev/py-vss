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
from typing import DefaultDict, List, Tuple
import re

from .vss_record import timestamp_to_datetime, indent_string
from .vss_exception import VssFileNotFoundException
from .vss_database import vss_database
from .vss_item import vss_item, vss_file, vss_project
from .vss_action import vss_action, create_file_action, create_project_action
from .vss_revision import vss_revision
from .vss_verbose import VerboseFlags

### This is a context for a directory during revision processing.
# It can get moved to a different parent.
# Its files and subdirectories can get renamed and/or moved, created and deleted.
# An item can be created by share, add, branch, recover, restore operations
class vss_change:
	def __init__(self):
		self.action_list:List[vss_action] = []
		self.timestamp:int = None
		self.author:str = None
		self.comments = []
		return

	def get_author(self):
		return self.author

	def get_datetime(self):
		return self.datetime

	def get_timestamp(self):
		return self.timestamp

	def get_message(self):
		return '\n\n'.join(self.comments)

	def get_actions(self):
		return iter(self.action_list)

	def append(self, action:vss_action):
		if self.timestamp is None:
			self.timestamp = action.timestamp
			self.datetime = timestamp_to_datetime(self.timestamp)
		else:
			assert(self.timestamp == action.timestamp)

		if self.author is None:
			self.author = action.revision.author

		self.action_list.insert(0, action)
		for comment in action.revision.comment, action.revision.label_comment:
			if not comment:
				continue
			# Normalize line separators
			comment = comment.strip()
			comment = re.sub('\r+\n|\r+', '\n', comment)
			comment = re.sub('\n\n\n+', '\n\n', comment)
			if comment and comment not in self.comments:
				self.comments.append(comment)
		return

	def print(self, fd, indent=''):
		print("\n%sREVISION:\n%s  TIMESTAMP: %s (%d)" % (indent, indent,
					timestamp_to_datetime(self.timestamp), self.timestamp), file=fd)
		indent += '  '
		for comment in self.comments:
			print(indent + indent_string(comment, indent), file=fd)
		for action in self.action_list:
			print("%s%s" % (indent, action), file=fd)
			for err in action.errors:
				print("  " + err, file=fd)
			continue

		return

class vss_file_changeset_item(vss_file):

	def __init__(self, database:vss_database, physical_name:str, logical_name:str,
			flags:int, pinned_version:int=0):

		self.next_revision:vss_revision = None
		super().__init__(database, physical_name, logical_name, flags, pinned_version)

		if self.item_file is not None:
			self.next_revision_num = self.item_file.get_last_revision_num()
			self.next_revision:vss_revision = self.item_file.get_revision(self.next_revision_num)
			self.next_revision_num -= 1
		return

	# The following functions implement an iterator-like functionality for generating sequence of revisions

	def get_next_revision_timestamp(self):
		if self.next_revision is not None:
			return self.next_revision.timestamp
		return None

	def get_next_revision_data(self):
		return self.next_revision.revision_data

	def get_next_revision_action(self, base_path):
		revision = self.next_revision
		if self.next_revision_num != 0:
			self.next_revision = self.item_file.get_revision(self.next_revision_num)
			self.next_revision_num -= 1
		else:
			self.next_revision = None
		action = create_file_action(revision, base_path + self.logical_name)
		action.apply_to_item_backwards(self)
		return action

class vss_directory_changeset_item(vss_project):

	file_item_type = vss_file_changeset_item

	def __init__(self, database:vss_database,
			physical_name:str, logical_name:str, flags:int, recursive=True):

		# Sorted list in "latest last" order, as (timestamp, item) tuples
		# Initialize the list before the base constructor, as it will be used to load the child items
		self.pending_child_items:List[Tuple[int, vss_file_changeset_item|vss_directory_changeset_item]] = []
		self.next_revision:vss_revision = None

		super().__init__(database, physical_name, logical_name,
						flags, recursive=recursive)

		if self.item_file is not None:
			self.next_revision_num = self.item_file.get_last_revision_num()
			self.next_revision = self.item_file.get_revision(self.next_revision_num)
			self.next_revision_num -= 1

			self.insert_pending_item(self)
		return

	# The following functions implement an iterator-like functionality for generating sequence of revisions
	def get_next_revision_timestamp(self):
		if self.pending_child_items:
			return self.pending_child_items[-1][0]
		return None

	def insert_pending_item(self, item:vss_item):
		if item is None:
			return

		if item is not self:
			if item.is_deleted():
				return
			timestamp = item.get_next_revision_timestamp()
			if timestamp is None:
				return
		elif self.next_revision is not None:
			timestamp = self.next_revision.timestamp
		else:
			return

		# Item for a project is executed first in direct order,
		# or last in reverse order
		for i in range(len(self.pending_child_items), 0, -1):
			pending_timestamp = self.pending_child_items[i-1][0]
			if timestamp > pending_timestamp:
				break
			if item is self or timestamp < pending_timestamp:
				continue
			# To maintain stable changelist order,
			# sort child items with same timestamp by name
			if item.logical_name > self.pending_child_items[i-1][1].logical_name:
				break
			continue
		else:
			i = 0
		self.pending_child_items.insert(i, (timestamp, item))
		if self.next_revision is not None \
				and self.next_revision.revision_num == 1 \
				and len(self.pending_child_items) > 1 \
				and self.pending_child_items[-1][1] is self:
			# Hold the CreateProject (the first revision) until all child revisions are drained
			self.next_revision.timestamp = self.pending_child_items[0][0]
			self.pending_child_items.pop(-1)
			self.pending_child_items.insert(0, (self.next_revision.timestamp, self))
		return

	def remove_pending_item(self, item):
		for i in range(len(self.pending_child_items)):
			if item is self.pending_child_items[i][1]:
				self.pending_child_items.pop(i)
				break
			continue
		return

	def get_next_revision_action(self, base_path)->vss_action:
		if not self.pending_child_items:
			return None

		base_path += self.logical_name + '/'
		timestamp, item = self.pending_child_items.pop(-1)
		if item is self:
			# 'item' points to this object
			revision = self.next_revision
			if self.next_revision_num != 0:
				self.next_revision = self.item_file.get_revision(self.next_revision_num)
				self.next_revision_num -= 1
				if self.next_revision is None:
					self.next_revision_num = 0
			else:
				self.next_revision = None

			action = create_project_action(revision, base_path)
			action.apply_to_item_backwards(self)
		else:
			action = item.get_next_revision_action(base_path)

		# Insert back to self.pending_child_items
		self.insert_pending_item(item)
		return action

	def insert_new_item(self, physical_name:str, logical_name:str, is_project:bool,
				flags:int=0, pinned_version:int=0, start_timestamp=0xFFFFFFFF, item_idx:int=-1):
		item = super().insert_new_item(physical_name, logical_name, is_project,
			flags, pinned_version, item_idx)

		if pinned_version > 0:
			# Not inserting to pending
			return item
		if item.item_file is None:
			# This item has been purged from the database
			return item

		while start_timestamp < item.get_next_revision_timestamp():
			item.get_next_revision_action("")
		self.insert_pending_item(item)
		return item

	def set_item_deleted(self, item_idx):
		# Delete the file item from this directory
		item = super().set_item_deleted(item_idx)
		self.remove_pending_item(item)
		return item

	def unset_item_deleted(self, item_idx, timestamp=0xFFFFFFFF):
		# Un-delete the file item from this directory
		item = super().unset_item_deleted(item_idx)
		if item.item_file is None:
			return item

		# flush back the skipped revisions. Shared files could have had checkins in the meantime
		while timestamp < item.get_next_revision_timestamp():
			item.get_next_revision_action("")

		self.insert_pending_item(item)
		return item

	# The function is applied as a backwards action, for "Unpin"
	# revision action.
	def set_item_pinned(self, item_idx, pinned_revision):
		item = self.get_item_by_index(item_idx)

		self.remove_pending_item(item)
		return item

	def unset_item_pinned(self, item_idx, timestamp):
		item = self.get_item_by_index(item_idx)

		if item.item_file is None:
			return item

		while timestamp < item.get_next_revision_timestamp():
			item.get_next_revision_action("")

		self.insert_pending_item(item)
		return item

class vss_changeset_history:
	def __init__(self, database:vss_database):
		self.changeset_list:List[vss_change] = None
		self.build(database.open_root_project(vss_directory_changeset_item, recursive=True))
		return

	def build(self, root_project:vss_directory_changeset_item):
		action_list = []
		while root_project.get_next_revision_timestamp() is not None:
			action_list.append(root_project.get_next_revision_action(''))

		action_list.sort(key=lambda a: (a.timestamp, a.revision.author))
		self.changeset_list = []
		change = None
		for action in action_list:
			if change is None or change.timestamp != action.timestamp or change.author != action.revision.author:
				change = vss_change()
				self.changeset_list.append(change)
			change.append(action)
		return

	def get_changelist(self):
		return self.changeset_list

	def print(self, fd, verbose:VerboseFlags=VerboseFlags.ProjectRevisions|VerboseFlags.FileRevisions):
		for change in self.changeset_list:
			change.print(fd, '')
			continue
		return
