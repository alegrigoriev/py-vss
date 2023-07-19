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

from enum import IntFlag

class VerboseFlags(IntFlag):
	VerboseNone			= 0x00000000
	RecordHeaders		= 0x00000001	# For all records, print their headers
	Records				= 0x00000002	# For all records, print their headers
	RecordCrc			= 0x00000004	# Print the record CRC
	DeltaItems			= 0x00000010	# Print delta record items
	DeltaData			= 0x00000020	# Print delta record data
	FileHeaders			= 0x00000100	# For files, print their headers
	ProjectRevisions	= 0x00001000	# Print all revisions of projects (for a database), or include project revisions to changeset output
	FileRevisions		= 0x00002000	# Print revisions of all files (for a database), or include file revisions to changeset output
	Projects			= 0x00010000	# Print verbose contents of all projects
	Files				= 0x00020000	# Print contents of all child file items in the projects
	HexDump				= 0x00040000	# Print hex dump of all records
	DatabaseFiles		= 0x00100000	# Print contents of all files
	ProjectTree			= 0x00200000	# Print contents of project tree
	Database			= 0x80000000	# Print contents of database, according to other flags
	Revisions			= ProjectRevisions|FileRevisions
	AllDatabase			= Database|Projects|Files|ProjectRevisions|FileRevisions
