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
import sys

def main():

	import argparse
	from VSS.vss_database import vss_database

	parser = argparse.ArgumentParser()
	parser.add_argument("database")
	parser.add_argument("--log", '-L', type=argparse.FileType('wt', encoding='utf-8'),
						help="Log file, default: standard output",
						default=sys.stdout)
	parser.add_argument("--encoding", '-E',
						help="Database encoding, default: current Windows code page",
						default='mbcs')
	parser.add_argument("--root-project-file", '-P',
				help='Dump from this project file, recursively')
	parser.add_argument("--verbose", '-V', nargs='+', action='extend',
					help="""Controls log output.
Values: 'projects' - print project structure;
        'records'  - print all records of database files;
        'revisions' - print all revisions of every item;""")

	options = parser.parse_args()
	log_file = options.log

	print("Loading database", options.database, file=sys.stderr)
	database = vss_database(options.database,
							encoding=options.encoding,
							root_project_file=options.root_project_file)

	# Preload files
	database.get_project_tree()
	print("Done", file=sys.stderr)

	from VSS.vss_verbose import VerboseFlags
	verbose_flags = VerboseFlags.Database
	verbose = options.verbose or ['revisions']

	verbose_hex = 'hex' in verbose
	verbose_records = 'records' in verbose or verbose_hex
	verbose_revisions = 'revisions' in verbose
	verbose_projects = 'projects' in verbose
	if verbose_records or verbose_revisions or verbose_projects:
		verbose_flags |= VerboseFlags.Projects|VerboseFlags.Files
		if verbose_records:
			verbose_flags |= VerboseFlags.Records|VerboseFlags.RecordHeaders|VerboseFlags.FileHeaders
			if verbose_hex:
				verbose_flags |= VerboseFlags.HexDump
		elif verbose_revisions:
			verbose_flags |= VerboseFlags.ProjectRevisions|VerboseFlags.FileRevisions
		database.print(log_file, verbose=verbose_flags)
		verbose_flags = 0

	return 0

if __name__ == "__main__":
	from VSS.vss_exception import VssException
	try:
		sys.exit(main())
	except VssException as ex:
		print("ERROR:", str(ex), file=sys.stderr)
		sys.exit(1)
	except FileNotFoundError as fnf:
		print("ERROR: %s: %s" % (fnf.strerror, fnf.filename), file=sys.stderr)
		sys.exit(1)
	except KeyboardInterrupt:
		# silent abort
		sys.exit(130)
