import shelve
import os

from mcp.debug import *

import collections
import gstreamer
import gst
import xmlrpclib
import datetime
import Queue
import random
import threading

from mcp.types import stack_dict, checklist, Song

lib_entry = Song

class playlist(checklist):
	def __init__(self, *args, **kargs):
		##A lock to make playlist edits thread-safe, and to handle proper
		#  playlist versioning
		self.__edit_lock = threading.RLock()
		self.history = collections.deque([None])
		self.loop = False
		self.random = False
		self.version = 0
		
	def __enter__(self):
		self.__edit_lock.acquire()
		
	def __exit__(self, typ, exc, traceback):
		self.__edit_lock.release()
		if self.__edit_lock._RLock__count == 0:
			##Only increment version when the current thread is done making edits.
			self.version += 1
			
	def __delitem__(self, index):
		with self:
			checklist.__delitem__(self, index)
		
	def clear(self):
		with self:
			while len(self):
				self.pop()
		
	def __getitem__(self, index):
		##	If index is None, we're being requested by the player, so we need to
		#	mark the song as played. Otherwise just return the song and be done
		#	with it. This behavior will soon be REMOVED
		#TODO:	Implement looping and randomness here. Shuffle should still work
		#	fine though.
		##
		print '__getitem__', index
		#if index is None:
			#index = len(checklist.checked(self))
			#print index, checklist.checked(self)
			#checklist.check(self, index)
		return checklist.__getitem__(self, index)
		
	def __setitem__(self, index, value):
		with self:
			checklist.__setitem__(self, index, value)
		
	def insert(self, index, item):
		##Creates a new member, changing the instance's length
		with self:
			checklist.insert(self, index, item)
		
	def move(self, key, offset=1):
		item = self[key]
		del self[key]
		self.insert(offset, item)
		self.version -= 1
	
	def shuffle(self):
		with self:
			random.shuffle(self)
	
	def next(self):
		if self.history[-1] is None:
			index = len(checklist.checked(self))
			if index == len(self):
				#End of the list
				return None
			checklist.check(self, index)
			self.history.append(self[index])
		self.history.rotate(1)
		return self.history[0]
	
	def prev(self):
		self.history.rotate(-1)
		song = self.history[0]
		if song is None:
			return None
		else:
			return song
		
class task_queue(Queue.Queue):
	pass

def multikeysort(items, columns):
	comparers = [(lambda x:x[abs(col)], (1 if col > 0 else -1)) for col in columns]
	def comparer(left, right):
		for col in columns:
			c = abs(col)
			if left[c] != right[c]:
				return cmp(left[c], right[c]) if col > 0 else cmp(right[c], left[c])
		return 0
	return sorted(items, cmp=comparer)

class library(object):
	def __init__(self, libpath='/home/ryan/testdb'):
		self.db = shelve.open(libpath)
		self.task_queue = task_queue()
		
	def __iter__(self):
		for hash in self.db.iterkeys():
			yield self.db[hash]

	def __del__(self):
		print 'Closing database'
		self.db.close()

	def add_uri(self, uri, normalize=False):
		hash = uri.rsplit('/',1)[1] #TODO Crappy hash
		song = mcp.types.Song(uri, hash)
		if uri.startswith('file:'):
			song.orig.update(gstreamer.get_tags(song.uri, normalize=True))
		elif uri.startswith('http:'):
			song.orig.update(gstreamer.get_tags(song.uri, normalize=False))
		self.db[hash] = song
		self.db.sync()
		return self.db[hash]

	def add_local_path(self, path):
		path = os.path.abspath(path)
		if not os.path.exists(path):
			raise OSError("No such file: " + path)
		if os.path.isdir(path):
			hashes = []
			for f in os.listdir(path):
				r = self.add_local_path(os.path.join(path,f))
				hashes.extend(r if isinstance(r,list) else [r])
			return hashes
		elif os.path.isfile(path):
			print 'Adding file', path
			return self.add_uri('file://' + path, True)
		
	def import_uri(self, uri):
		#TODO Handle ripping/downloading here
		self.task_queue.put(('import', uri))
		
	def remove_hash(self, hash):
		pass
		#TODO Handle removal from library

	def query(self, *args):
		results, sortkeys, sortids, kargs, i = [], [], [], {}, 0
		args = ['sort=album', 'sort=track-number'] + list(args)
		for a in args:
			if a.startswith('sort='):
				i += 1
				if a[5] == '!':
					sortkeys.append(a[6:])
					sortids.append(-i)
				else:
					sortkeys.append(a[5:])
					sortids.append(i)
			else:
				k,v = a.split('=',1)
				kargs[k] = v
		for hash in self.db.keys():
			match = True
			entry = self.db[hash]
			for w,v in [(entry.get(k,''),v) for k,v in kargs.items()]:
				match = match and (v == w or str(v) == str(w))
			if match:
				new = [entry] + [entry.get(k,'') for k in sortkeys]
				results.append(new)
		results = [r[0] for r in multikeysort(results, sortids)]
		return results
		
	def info_update(self, hash, **kargs):
		pass
