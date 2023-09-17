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

	options = parser.parse_args()
	log_file = options.log

	print("Loading database", options.database, file=sys.stderr)
	database = vss_database(options.database,
							encoding=options.encoding)

	# Preload files
	database.get_project_tree()
	print("Done", file=sys.stderr)

	database.print(log_file)
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
