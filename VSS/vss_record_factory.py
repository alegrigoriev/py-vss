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

from .vss_record import (
	vss_record,
	vss_comment_record,
	vss_checkout_record,
	vss_project_record,
	vss_branch_record,
	vss_delta_record)
from .vss_revision_record import vss_revision_record, vss_revision_record_factory

class vss_item_record_factory:
	class_dict = {
			vss_comment_record.SIGNATURE : vss_comment_record,
			vss_checkout_record.SIGNATURE : vss_checkout_record,
			vss_project_record.SIGNATURE : vss_project_record,
			vss_branch_record.SIGNATURE : vss_branch_record,
			vss_revision_record.SIGNATURE : vss_revision_record_factory,
			vss_delta_record.SIGNATURE : vss_delta_record,
		}

	@classmethod
	def create_record(cls, record_header)->vss_record:
		record_class = cls.class_dict.get(record_header.signature, None)
		if record_class is None:
			return None
		return record_class.create_record(record_header)

	@classmethod
	def valid_record_class(cls, record):
		record_class = cls.class_dict.get(record.header.signature, None)
		return record_class is not None and \
			record_class.valid_record_class(record)
