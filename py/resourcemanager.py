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

from tarfile import TarFile
from os import mkdir, getcwd, chdir, listdir, environ, rename
from os.path import dirname
from shutil import move, rmtree
from sys import path, maxint
from time import asctime, time
from statusprocess import StatusProcess

from util import *

from task import Task, ERROR
from controltask import ControlTask
from deploytask import DeployTask
from cleanuptask import CleanupTask
from shutdowntask import ShutdownTask
from killtask import KillTask

from timer import Timer



class ResourceManager:

	_frmk = None
	_pm = None
	_done = False
	_waiting = True

	_tracking = None
	_timer = None

	def __init__(self, frmk, pmanager ):
		self._frmk = frmk
		self._pm = pmanager
		self._done = False
		self._waiting = True

		self._tracking = {}
		self._timer = Timer(self.__class__.__name__)

		self.display( OUTPUT_VERBOSE, 'initialized' )

	def _nextTask(self, slots_available):
		task = None
		pid = True
		while not pid == None:
			pid = self._pm.nextProc()
			if not pid == None:
				task = self._pm.nextTask( pid, slots_available )
				if isinstance( task, Task ):

					if not pid in self._tracking:
						self._tracking[pid] = { 'out':{}, 'workers':[], 'done':False, 'noderef':{} }

					self._tracking[pid]['out'][task.key] = task
					self._timer.start( task.key )

					self.display( OUTPUT_LOGIC, 'got next task from process manager' )
					break
				else:
					self.display( OUTPUT_DEBUG, 'got invalid task from process manager' )
					pid = None


		return task

	def returnTask(self, task):
		if isinstance( task, Task ):
			pid = task.pid
			if task.sender in self._frmk.workers:
				winfo = self._frmk.workers[task.sender]
				winfo['slots'] = winfo['slots'] + task.slots

				if winfo['slots'] > winfo['mslots']:
					winfo['slots'] = winfo['mslots']

				if pid in self._tracking and task.key in self._tracking[pid]['out']:
					self.display( OUTPUT_DEBUG, 'known task returned' )
					del self._tracking[pid]['out'][task.key]
					self._timer.stop( task.key )
					self._timer.record()

				if isinstance( task, ControlTask ):
					if isinstance( task, CleanupTask ):
						self.display( OUTPUT_DEBUG, 'cleanup task completed')
						if self._pm.delProc( pid ) == pid:
							if pid in self._tracking:
								del self._tracking[pid]
					elif isinstance( task, DeployTask ):
						self.display( OUTPUT_DEBUG, 'deploy task completed')

					elif isinstance( task, ShutdownTask ):
						self.display( OUTPUT_DEBUG, 'shutdown task completed' )
						self._done = True

					elif isinstance( task, KillTask ):
						self.display( OUTPUT_DEBUG, 'kill task completed' )

					else:
						self.display( OUTPUT_DEBUG, 'control task belongs to process %d' % pid )
						self._pm.returnTask( task )
				else:
					self.display( OUTPUT_LOGIC, 'task returned to process %d' % pid )
					self._pm.returnTask( task )
			else:
				self.display( OUTPUT_DEBUG, 'got task from unknown sender' )

	def ready(self):
		result = False

		if not self._done:
			if not self._pm.nextProc() == None:
				result = True

			if not self._pm.firstDoneProc() == None:
				result = True

		return result

	def done(self):
		return self._done

	def step(self):
		self._cleanupProcs()
		if not self._done:
			ctask = True
			self.display( OUTPUT_VERBOSE, 'checking for pending control tasks from process manager' )
			while not ctask == None:
				ctask = self._pm.nextControlTask()
				if not ctask == None:
					self.display( OUTPUT_DEBUG, 'sending control task to framework' )
					self._frmk.queueFirst( ctask )

			self._issueTask()

		if not self._waiting and self._pm.done():
			self._waiting = True
			self.display( OUTPUT_MAJOR, 'sending shutdown task' )
			self._frmk.queue( ShutdownTask( 0, 0, None ) )


	def _cleanupProcs(self):
		pid = True
		while not pid == None:
			pid = self._pm.firstDoneProc()
			if not pid == None and pid in self._tracking:
				if not self._tracking[pid]['done']:
					if pid in self._tracking:
						self._tracking[pid]['done'] = True
					
					if not self._frmk == None and len( self._tracking[pid]['workers'] ) > 0:
						self.display( OUTPUT_MINOR, 'cleanup issued for process %d' % pid )
						ctask = CleanupTask(pid,0,None)
						ctask.pid = pid
						self._frmk.queueFirst( ctask )
						break
					else:
						if self._pm.delProc( pid ) == pid:
							if pid in self._tracking:
								del self._tracking[pid]
				else:
					break
			elif not pid == None:
				self._pm.delProc( pid )

	def _issueTask(self):
		if self._availableWorker():
			slots_available = self._maxSlotsAvailable()

			task = self._nextTask(slots_available)
			if isinstance( task, Task ):
				# place recovery here?
				pid = task.pid
				wid = self._selectWorker( task )
				if wid is None:
					return
				if wid in self._frmk.workers.keys():

					pinfo = self._tracking[pid]
					winfo = self._frmk.workers[wid]

					if pinfo['workers'].count( wid ) == 0:

						config = self._pm.getProcConfig( pid )

						if not config == None and not winfo['proc'].count( pid ) > 0:

							self.display( OUTPUT_MINOR, 'deploying process %d resources to worker %d' % ( pid, wid ) )
							ctask = DeployTask( pid,0, config, { wid:winfo['name'] } )
							pinfo['workers'].append( wid )
							
							ctask.pid = pid
							ctask.destination = wid
							self._frmk.queueFirst( ctask )

					if 'noderef' in pinfo:
                                                pinfo['noderef'][task.key] = wid

					self.display( OUTPUT_MINOR, 'task assigned to worker %d, sending to queue. %s' % (wid, task.id()) )
					task.destination = wid
					winfo['slots'] = winfo['slots'] - task.slots
					self._frmk.queue( task )

				else:
					self.display( OUTPUT_DEBUG, 'error! unknown worker assigned when one was ready' )
			

	def _availableWorker(self):
		"""
		Checks for an available worker.

		Returns True if there is a worker available to perform a task
		"""
		result = False
		if not self._frmk == None:
			for wid in self._frmk.workers.keys():
				info = self._frmk.workers[wid]
				# must have task slots available and not be reserved in order
				# to be considered available
				if info['slots'] > 0 and not info['reserved']:
					result = True
					self.display( OUTPUT_VERBOSE, 'found available worker %d' % wid )
					break
		return result

	def _maxSlotsAvailable(self):
		return max( worker['slots'] for worker in self._frmk.workers.values() )

	def _selectWorker(self,task):
		"""
		Select the best worker for the given task.

		Returns the wid of the best worker if one is found, otherwise None.

		Favours workers that are already deployed to and are idle
		"""

		pid = task.pid
		required_slots = task.slots

		# NOTE: None always evaluates less than any number
		best_deployed_worker = {'free_slots' : None, 'worker_id' : None}
		best_undeployed_worker = {'free_slots' : None, 'worker_id' : None}

		for worker_id in self._frmk.workers.keys():
			worker_info = self._frmk.workers[worker_id]

			# never select a reserved worker
			if worker_info['reserved']:
				continue

			available_slots = worker_info['slots']
			if available_slots < required_slots:
				continue

			free_slots = available_slots - required_slots

			# choose the most available worker with task resources setup
			if pid in worker_info['proc']:
				if best_deployed_worker.get('free_slots') < free_slots:
					best_deployed_worker['free_slots'] = free_slots
					best_deployed_worker['worker_id'] = worker_id
			# choose the most available worker without task resources setup
			else:
				if best_undeployed_worker.get('free_slots') < free_slots:
					best_undeployed_worker['free_slots'] = free_slots
					best_undeployed_worker['worker_id'] = worker_id

		if best_deployed_worker['worker_id'] is not None:
			result = best_deployed_worker['worker_id']
		elif best_undeployed_worker['worker_id'] is not None:
			result = best_undeployed_worker['worker_id']
		else:
			result = None

		if result is not None:
			self.display( OUTPUT_DEBUG, 'selected worker %d' % result )
		else:
			self.display( OUTPUT_DEBUG, 'failed to select worker' )

		return result

	def reserveWorker(self, wid):
		"""
		Reserve a worker to the exclusion of all processes.

		This allows dynamic restriction of resources without needing a stop/start
		"""
		if wid in self._frmk.workers:
			info = self._frmk.workers[wid]
			info['reserved'] = True
			self.display( OUTPUT_MINOR, 'worker %d reserved' % wid )

	def releaseWorker(self, wid):
		"""
		Releases a worker reservation.

		This allows dynamic reserved workers to be re-enabled for use without needing a stop/start
		"""
		if wid in self._frmk.workers:
			info = self._frmk.workers[wid]
			info['reserved'] = False
			self.display( OUTPUT_MINOR, 'worker %d reservation released' % wid )
		
	

	def stopTasks(self, pid):
		if pid in self._tracking:
			for key in self._tracking[pid]['noderef'].keys():
				wid = self._tracking[pid]['noderef'][key]
				task = KillTask( pid, 0, None, key )
				task.pid = pid
				task.destination = wid
				self.display( OUTPUT_MINOR, 'sending kill task for process %d task %s on worker %d' % (pid,key, wid) )
				self._frmk.queueFirst( task )
		else:
			self.display( OUTPUT_ERROR, 'stop now request for unknown process: %s' % str( pid ) )

	def shutdown(self, now ):

		if now:
			self.display( OUTPUT_MAJOR, 'stopping all running tasks' )
			for pid in self._tracking.keys():
				self.stopTasks( pid )
		else:
			self.display( OUTPUT_DEBUG, 'waiting for outstanding tasks to complete' )

		self._waiting = False


	def display(self,level,text):
		display( level, 'Resource Manager: %s' % text )
