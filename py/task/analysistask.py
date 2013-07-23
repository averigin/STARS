# Copyright (C) 2011 Eamon Millman
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#

from task import Task, ERROR
from util import OUTPUT_ERROR

import os
import os.path as path
import shutil

class AnalysisTask(Task):
	_resources = None

	def __init__(self,*args,**kwargs):
		Task.__init__(self, *args, **kwargs )

		self._statemembers.append('_resources')

		if self._resources is None:
			self._resources = []

	def add_resource(self, file_name, store_path, deployed_path=None):
		# Deployed path is relative to the process root
		if deployed_path is None:
			deployed_path = ""

		self._resources.append( (store_path, deployed_path, file_name) )

	def setup(self, worker_id, worker_name):
		'''
		Deploy resources to worker node.

		Run from the management node.
		'''
		dest_host = worker_name
		dest_root = "%s/dep/%d/%d" % ( os.environ['STARSPATH'], worker_id, self.owner )

		res_pieces = self._config['general']['results'].split(':')
		if len(res_pieces) == 1:
			source_host = None
		else:
			source_host = res_pieces[0]
		source_root = res_pieces[-1]

		for (resource_subpath, deployed_path, resource_name) in self._resources:
			source_path = path.join( source_root, resource_subpath )
			dest_path = path.join( dest_root, deployed_path or '' )

			if not self._data_access.deploy_direct( source_host, source_path, resource_name, dest_host, dest_path, resource_name ):
				self.display( OUTPUT_ERROR, 'failed to send analysis resources to worker: %s' % worker_id )
				self.state = ERROR
				break

	def cleanup(self):
		'''
		Clean up resources.

		Run from the worker node.
		'''
		for (resource_subpath, deployed_path, resource_name) in self._resources:
			os.system( "rm -rf '%s'" % path.join(self._root, deployed_path, resource_name) )
