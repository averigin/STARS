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
from collections import namedtuple
import os
import subprocess

from util import display, loadConfig, OUTPUT_MINOR, OUTPUT_DEBUG, OUTPUT_ERROR

class DataAccess(object):

	_global = None
	_store_path = None
	_store_host = None
	_config = None
	_host = None
	_ssh_o = None

	CommandResult = namedtuple('CommandResult', ['returncode','stdout','stderr'])

	def __init__(self, configFile):

		try:
			self._config = loadConfig( configFile )
		except:
			self._config = None

		strict = False
		key = None
		if not self._config == None and 'dataaccess' in self._config:
			if 'global' in self._config['dataaccess']:
				self._global = True
			else:
				self._global = False

			if 'store_path' in self._config['dataaccess']:
				self._store_path = self._config['dataaccess']['store_path']
			else:
				raise Exception('DataAccess','required field [dataaccess]:store_path not found in %s' % configFile )

			if 'store_host' in self._config['dataaccess']:
				self._store_host = self._config['dataaccess']['store_host']
			elif not self._global:
				raise Exception('DataAccess','required field [dataaccess]:store_host not found in %s' % configFile )

			if 'key' in self._config['dataaccess']:
				key = self._config['dataaccess']['key']

			if 'StrictHostKeyChecking' in self._config['dataaccess']:
				strict = True

		res = self.__run_shell_cmd('stat %s/hostname' % os.environ['STARSPATH'])
		if res.returncode == 0:
			f = open( os.environ['STARSPATH'] + '/hostname' )
			self._host = f.read().strip()
			f.close()
		else:
			self._host = os.environ['HOSTNAME']
		self._ssh_o = ''

		if not strict:
			self._ssh_o = '-o StrictHostKeyChecking=no'
		if key is not None:
			self._shh_o = '-i %s %s' % ( key, self._ssh_o )

	@staticmethod
	def __run_shell_cmd( command ):
		proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
		output,error = proc.communicate()
		return DataAccess.CommandResult(proc.returncode, output.strip(), error.strip())

	def setStore(self, storeHost, storePath, storeGlobal):
		#if not storeHost == None:
		self._store_host = storeHost
		#if not storePath == None:
		self._store_path = storePath
		#if not storeGlobal == None:
		self._global = storeGlobal
		display( OUTPUT_DEBUG, "data_access configured for store host %s, store path %s, and global %s." % ( storeHost, storePath, str(storeGlobal) ) )

	def store(self,subPath,fileHost,filePath,fileName):
		cmdline = "exit 1"

		display( OUTPUT_DEBUG, "data_access.store called" )

		if not fileName.find('*') == -1:
			display( OUTPUT_DEBUG, "data_access.store multiple files" )
			if self._global:
				display( OUTPUT_DEBUG, "data_access.store local file" )
				cmdline = "cp %s/%s %s/%s/" % ( filePath, fileName, self._store_path, subPath )
			else:
				if not fileHost == None:
					display( OUTPUT_DEBUG, "data_access.store remote file, remote store" )
					cmdline = "scp %s %s:%s/%s %s:%s/%s/" % ( self._ssh_o, fileHost, filePath, fileName, self._store_host, self._store_path, subPath )
				else:
					display( OUTPUT_DEBUG, "data_access.store remote file, local store" )
					cmdline = "scp %s %s/%s %s:%s/%s/" % ( self._ssh_o, filePath, fileName, self._store_host, self._store_path, subPath )
		else:
			display( OUTPUT_DEBUG, "data_access.store single file" )
			if self._global:
				display( OUTPUT_DEBUG, "data_access.store local file" )
				cmdline = "mv %s/%s %s/%s/%s" % ( filePath, fileName, self._store_path, subPath, fileName )
			else:
				if not fileHost == None:
					display( OUTPUT_DEBUG, "data_access.store remote file, remote store" )
					cmdline = "scp %s %s:%s/%s %s:%s/%s/" % ( self._ssh_o, fileHost, filePath, fileName, self._store_host, self._store_path, subPath )
				else:
					display( OUTPUT_DEBUG, "data_access.store remote file, local store" )
					cmdline = "scp %s %s/%s %s:%s/%s/" % ( self._ssh_o, filePath, fileName, self._store_host, self._store_path, subPath )

		display( OUTPUT_DEBUG, 'data_access' )
		self.touchPath( self._store_host, "%s/%s" % (self._store_path, subPath) )

		display( OUTPUT_DEBUG, "running: %s" % cmdline )

		res = self.__run_shell_cmd( cmdline )
		if res.returncode == 0:
			if not fileHost == None:
				display( OUTPUT_MINOR, "stored file %s:%s/%s in store:%s/" % ( fileHost, filePath, fileName, subPath ) )
			else:
				display( OUTPUT_MINOR, "stored file %s/%s in store:%s/" % ( filePath, fileName, subPath ) )
			return True
		else:
			display( OUTPUT_ERROR, 'Unable to store %s:%s/%s' % (fileHost or 'localhost', filePath, fileName))
			display( OUTPUT_ERROR, '%s' % res.stderr )
			return False	

	def remove(self,fileHost,filePath,fileName):
		cmdline = 'exit 1'

		if self._global or fileHost == None:
			cmdline = "rm -f %s/%s" % ( filePath, fileName )
		else:
			cmdline = "ssh %s %s 'rm -f %s/%s'" % ( self._ssh_o, fileHost, filePath, fileName )

		display( OUTPUT_DEBUG, 'running: %s' % cmdline )

		res = self.__run_shell_cmd(cmdline)
		if res.returncode == 0:
			display( OUTPUT_MINOR, 'Removed %s' % fileName )
			return True
		else:
			display( OUTPUT_ERROR, 'Unable to remove %s:%s/%s' % (fileHost or 'localhost', filePath, fileName) )
			display( OUTPUT_ERROR, '%s' % res.stderr )
			return False

	def retrieve(self,subPath,filePath,fileName):
		cmdline = "exit 1"

		if self._global:
			cmdline = "ln -s %s/%s/%s %s/%s" % ( self._store_path, subPath, fileName, filePath, fileName )
		else:
			cmdline = "scp %s %s:%s/%s/%s %s/%s" % ( self._ssh_o, self._store_host, self._store_path, subPath, fileName, filePath, fileName )

		self.touchPath( None, filePath )

		display( OUTPUT_DEBUG, "running: %s" % cmdline )

		res = self.__run_shell_cmd(cmdline)
		if res.returncode == 0:
			display( OUTPUT_MINOR, "retrieved file %s from store:%s/" % ( fileName, subPath ) )
			return True
		else:
			display( OUTPUT_ERROR, 'Unable to retrieve %s from store:%s' % ( fileName, subPath ) )
			display( OUTPUT_ERROR, '%s' % res.stderr )
			return False

	def deploy(self,filePath,fileName,destHost,destPath,destName):
		cmdline = "exit 1"
		if self._global:
			cmdline = "cp %s/%s %s/%s" % ( filePath, fileName, destPath, destName )
		else:
			cmdline = "scp %s %s/%s %s:%s/%s" % ( self._ssh_o, filePath, fileName, destHost, destPath, destName )

		self.touchPath( destHost, destPath )

		display( OUTPUT_DEBUG, "running: %s" % cmdline )

		res = self.__run_shell_cmd(cmdline)
		if res.returncode == 0:
			display( OUTPUT_MINOR, "deployed file %s to %s:%s" % ( fileName, destHost, destPath ) )
			return True
		else:
			display( OUTPUT_ERROR, 'Unable to deploy %s to %s:%s' % ( fileName, destHost, destPath ) )
			display( OUTPUT_ERROR, '%s' % res.stderr )
			return False

	def deploy_direct(self,srcHost,srcPath,srcName,destHost,destPath,destName):
		cmdline = 'exit 1'

		if self._global:
			cmdline = "cp %s/%s %s/%s" % ( srcPath, srcName, destPath, destName )
		else:
			opts = self._ssh_o
			cmdline = "ssh %(opts)s %(destHost)s 'scp %(srcHost)s:%(srcPath)s/%(srcName)s %(destPath)s/%(destName)s'" % locals()

		self.touchPath( destHost, destPath )

		display( OUTPUT_DEBUG, "running: %s" % cmdline )

		res = self.__run_shell_cmd(cmdline)
		if res.returncode == 0:
			display( OUTPUT_MINOR, "deployed file %s:%s/%s to %s:%s" % ( srcHost, srcPath, srcName, destHost, destPath ) )
			return True
		else:
			display( OUTPUT_ERROR, 'Direct deploy failed')
			display( OUTPUT_ERROR, 'Command: %s' % cmdline )
			display( OUTPUT_ERROR, '%s' % res.stderr )
			return False

	def collect(self,filePath, fileName, srcHost, srcPath, srcName ):
		cmdline = "exit 1"

		if self._global or srcHost == None:
			cmdline = "ln -s %s/%s %s/%s" % (srcPath, srcName, filePath, fileName )
		else:
			cmdline = "scp %s %s:%s/%s %s/%s" % ( self._ssh_o, srcHost, srcPath, srcName, filePath, fileName )

		self.touchPath( None, filePath )

		res = self.__run_shell_cmd(cmdline)
		if res.returncode == 0:
			display( OUTPUT_MINOR, "Collected file %s/%s from %s:%s" % ( filePath, fileName, srcHost, srcPath ) )
			return True
		else:
			display( OUTPUT_ERROR, "Unable to collect file %s/%s from %s:%s" % ( filePath, fileName, srcHost, srcPath ) )
			display( OUTPUT_ERROR, '%s' % res.stderr )
			return False

	def checkStore(self,subPath, fileName ):
		cmdline = "exit 1"

		if self._global:
			cmdline = "stat %s/%s/%s" % ( self._store_path, subPath, fileName )
		else:
			cmdline = "ssh %s %s 'stat %s/%s/%s'" % ( self._ssh_o, self._store_host, self._store_path, subPath, fileName )

		display( OUTPUT_DEBUG, "running: %s" % cmdline )

		res = self.__run_shell_cmd(cmdline)
		if res.returncode == 0:
			display( OUTPUT_DEBUG, "Found file %s in store:%s/" % ( fileName, subPath ) )
			return True
		else:
			display( OUTPUT_MINOR, "Unable to find file %s in store:%s/" % ( fileName, subPath ) )
			display( OUTPUT_DEBUG, '%s' % res.stderr )
			return False

	def touchPath(self,fileHost,filePath):
		cmdline = "exit 1"

		display( OUTPUT_DEBUG, "data_access.touchPath called" )
		if self._global or fileHost == None:
			cmdline = "mkdir -p %s" % filePath
		else:
			cmdline = "ssh %s %s 'mkdir -p %s'" % ( self._ssh_o, fileHost, filePath )

		display( OUTPUT_DEBUG, "running: %s" % cmdline )

		res = self.__run_shell_cmd(cmdline)
		if res.returncode == 0:
			display( OUTPUT_DEBUG, "Created path: %s" % filePath)
			return True
		else:
			display( OUTPUT_ERROR, "Unable to create path: %s" % filePath)
			display( OUTPUT_ERROR, '%s' % res.stderr )
			return False
