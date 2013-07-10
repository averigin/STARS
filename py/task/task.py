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

from os import environ, path, system
from mpi import rank
from subprocess import Popen
from time import time, sleep

from dataaccess import DataAccess
from message import Message
from util import display, displayExcept, OUTPUT_ERROR, OUTPUT_MINOR, OUTPUT_DEBUG


INVALID = -1
NEW = 0
SUCCESS = 1
FAIL = 2
ERROR = 3
WAIT = 4
RUNNING = 5

class Task(Message):
	
	_key = None
	_pid = None

	_results = None
	_start = None
	_state = None
	#_failed = None

	_root = None

	_id = None
	_slots = None

	_ready = None

	_taskname = None

	_data_access = None

	_config = None

	def __init__(self,*args,**kwargs):

		if self._statemembers == None:
			self._statemembers = []

		self._statemembers.extend( ['_results','_logs','_id','key','pid','_ready','state','_start','_root','slots','_taskname','_config'] )

		Message.__init__(self, *args, **kwargs )

		self._data_access = DataAccess( environ['STARSPATH'] + '/stars.config' )

		if len(args) >= 3:
			self.display( OUTPUT_DEBUG, 'calling initializer for Task' )
			self._initTask( args[0], args[1], args[2] )
		elif 'stateobj' in kwargs:
			self.display( OUTPUT_DEBUG, 'decoding state object for Task' )
			self._root = "%s/dep/%d/%s" % (environ['STARSPATH'], rank, self.owner )

		if not self._config == None and 'general' in self._config:
			if 'results' in self._config['general']:
				temp = self._config['general']['results'].split(':')
				if len( temp ) == 1:
					self._data_access.setStore( None, temp[0], True )
				elif len( temp ) == 2:
					self._data_access.setStore( temp[0], temp[1], None )

	def _initTask(self, owner, tid, config):
		self._config = config
		self._results = []
		self._logs = []
		self._id = "%s%d" % ( self.__class__.__name__, tid)
		self.key = None
		self.pid = owner
		self._ready = True
		#self.failed = 0
		self.state = NEW
		self._start = time()
		self._root = "%s/dep/%d/%s" % (environ['STARSPATH'], rank, str(owner) )
		self.slots = 1

		self.display( OUTPUT_DEBUG, 'finished initializer for Task' )

	def __str__(self):
		return self.id()

	def target(self):
		return self._taskname

	def get_store_dir(self):
		if self.state == ERROR:
			return 'failed'
		else:
			return 'completed'

	def recover(self):
		if not self._results:
			return False

		display( OUTPUT_MINOR, 'Attempting to recover' )

		success = True
		for (directory, filename, store_dir) in self._results:
			try:
				if not store_dir:
					store_dir = self.get_store_dir()
				if not self._data_access.checkStore( store_dir, filename ):
					self.display( OUTPUT_DEBUG, 'Expected result missing: %s' % filename )
					success = False
					break
			except:
				success = False
				break

		if success:
			self.state = SUCCESS
			del self._results[:]
			self.display( OUTPUT_MINOR, 'Recovered results' )
		else:
			self.display( OUTPUT_MINOR, 'Task could not be recovered' )

		return success

	def store(self):
		success = True

		host = self.worker_hostname

		self.display( OUTPUT_DEBUG, 'logs: %r' % self._logs )
		for (directory, filename, store_dir) in self._logs:
			try:
				if not store_dir:
					store_dir = self.get_store_dir()
				self.display( OUTPUT_DEBUG, 'Storing log: %s:%s -> %s' % (host, path.join(directory, filename), path.join(store_dir,filename)))
				self._data_access.store( store_dir, host, directory, filename )
			except:
				# Ignore any errors
				pass
			self._data_access.remove(host, directory, filename)

		self.display( OUTPUT_DEBUG, 'results %s' % str( self._results ) )
		for (directory, filename, store_dir) in self._results:
			try:
				if not store_dir:
					store_dir = self.get_store_dir()
				self.display( OUTPUT_DEBUG, 'Storing result: %s:%s -> %s' % (host, path.join(directory, filename), path.join(store_dir,filename)))

				success = self._data_access.store( store_dir, host, directory, filename ) and success
			except:
				displayExcept()
				success = False

			self._data_access.remove(host, directory, filename)

		if not success:
			self.state = ERROR

		return success

	@property
	def key(self):
		return self._key

	@key.setter
	def key(self,value):
		if self._key == None:
			self._key = value

	@property
	def pid(self):
		return self._pid

	@pid.setter
	def pid(self,value):
		if self._pid == None:
			self._pid = value

	def id(self):
		return self._id

	def subprocess(self,cmdline,run_dir=None):
		rcode = -1
		p = None
		pid = None
		try:
			if run_dir == None:
				run_dir = self._root

			self.display( OUTPUT_DEBUG, 'starting sub process' )
			p = Popen( cmdline, shell=True, cwd=run_dir )
			if not p == None:
				pid = p.pid
				self.display( OUTPUT_DEBUG, 'writing pid file' )
				f = open( '%s/%d.pid' % ( self._root, pid ), 'w' )
				f.write( str(self.key) )
				f.close()

				self.display( OUTPUT_DEBUG, 'start polling for task finish or kill' )
				#while system() == 0:
				while p.poll() == None:
					if system( 'stat %s/%d.kill > /dev/null 2>&1' % ( self._root, pid ) ) == 0:
						self.display( OUTPUT_DEBUG, 'trying to shut down all child processes for pid %d' % pid ) 
						system( 'ps -o pid= --ppid %d | xargs kill -9' % pid )
						p.kill()
						self.state = ERROR
						self.display( OUTPUT_DEBUG, 'terminated running task.' )
						break

					sleep(10)

				if not p.returncode == None:
					self.display( OUTPUT_DEBUG, 'subprocess finished with code %d' % p.returncode )
					rcode = p.returncode

		except:
			displayExcept()
			self.display( OUTPUT_ERROR, 'error creating subprocess for task')
			self.state = ERROR

			if not p == None:

				p.kill()

			rcode = None
		
		if not pid == None:
			system( 'rm %s/%d.* > /dev/null 2>&1' % ( self._root, pid ) )
		
		
		return rcode

	def addResult(self, *path_pieces, **kwargs):
		store_dir = kwargs.get('store_dir')
		result_file = path.join( *path_pieces )
		entry = ( path.dirname(result_file), path.basename(result_file), store_dir )
		if entry not in self._results:
			self._results.append( entry )
			self.display( OUTPUT_DEBUG, 'Added result file: %s' % result_file )

	def addLog(self, *path_pieces, **kwargs):
		store_dir = kwargs.get('store_dir')
		log_file = path.join( *path_pieces )
		entry = ( path.dirname(log_file), path.basename(log_file), store_dir )
		if entry not in self._logs:
			self._logs.append( entry )
			self.display( OUTPUT_DEBUG, 'Added log file: %s' % log_file )
		
	@property
	def slots(self):
		return self._slots

	@slots.setter
	def slots(self,value):
		if value >= 0:
			self._slots = value

	@property
	def failed(self):
		return self._failed

	@failed.setter
	def failed(self,value):
		self._failed = self._failed + value
		if self._failed < 0:
			self._failed == 0
		
	def ready(self):
		return self._ready

	@property
	def state(self):
		return self._state

	@state.setter
	def state(self,value):
		if value == ERROR and not self._state == ERROR:
			self.display( OUTPUT_ERROR, '%s encountered an error' % self.id() )

		if not self._state == ERROR:
			self._state = value

	def finish(self):
		return True

	def execute(self):
		raise NotImplementedError

	def result(self):
		return self._results
		
	def display(self,level, text):
		if not self.worker == None and not self.hostname == None:
			display( level, '%s on %s: %s' % ( self.__class__.__name__, self.hostname, text) )
		else:
			display( level, '%s: %s' % ( self.__class__.__name__, text ) )

		

