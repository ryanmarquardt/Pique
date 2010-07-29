#!/usr/bin/env python
#       Redistribution and use in source and binary forms, with or without
#       modification, are permitted provided that the following conditions are
#       met:
#       
#       * Redistributions of source code must retain the above copyright
#         notice, this list of conditions and the following disclaimer.
#       * Redistributions in binary form must reproduce the above
#         copyright notice, this list of conditions and the following disclaimer
#         in the documentation and/or other materials provided with the
#         distribution.
#       * Neither the name of the  nor the names of its
#         contributors may be used to endorse or promote products derived from
#         this software without specific prior written permission.
#       
#       THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#       "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#       LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#       A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#       OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#       SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#       LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#       DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#       THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#       (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#       OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from common import *
import threading
import traceback
import Queue

class JobsManager(PObject):
	def __init__(self, conf):
		self.commands = {
			'jobstatus': self.jobstatus,
		}
		self.highest = 0
		count = dict(conf).get('max_threads', 2)
		self.queue = Queue.Queue()
		self.result = {}
		for i in range(count):
			t = threading.Thread(target=self.consume)
			t.daemon = True
			t.start()
	
	def consume(self):
		while True:
			id, func, args, kwargs = self.queue.get()
			debug('Running task', id)
			try:
				r = func(*args, **kwargs)
			except Exception, e:
				self.result[id] = None, e
				print traceback.format_exc()
			else:
				self.result[id] = r, None
			debug('Finished task', id)
			self.queue.task_done()
	
	def submit(self, func, *args, **kwargs):
		self.highest += 1
		id = self.highest
		self.queue.put((id, func, args, kwargs))
		return id
		
	def jobstatus(self, id):
		id = int(id)
		if id in self.result:
			if self.result[id][1] is None:
				return 'done'
			else:
				return 'error'
		else:
			return 'pending'
		
	def join(self):
		self.queue.join()

if __name__=='__main__':
	def long_running_task(input):
		t = 1
		for a in range(input):
			t = (t * a) or 1
			t = t & 0xffffffffffffffff
		return t
	
	JM = JobsManager(())
	
	import random
	ids = [JM.submit(long_running_task, random.randint(2**15,2**16)) for i in range(50)]
	JM.join()
	for id in ids:
		print JM.result[id]
