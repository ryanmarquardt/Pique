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

import threading
import Queue

class JobsManager(object):
	def __init__(self, conf):
		simultaneous = dict(conf).get('max_threads', 2)
		self.jobs = {}
		self.queue = Queue.Queue()
		self.consumers = []
		for i in range(simultaneous):
			self.consumers.append(threading.Thread(target=JobConsumer, args=(self.queue,)))
		
	def submit(self, func, *args, **kwargs):
		id = max(self.jobs.keys())+1
		f = lambda:func(*args,**kwargs)
		self.jobs[id] = Job(id, f)
		
def JobConsumer(queue):
	while True:
		try:
			job = queue.get(timeout=1)
			job.run()
			queue.task_done()
		except Queue.Empty:
			pass
		
class Job(object):
	def __init__(self, id, callback):
		self.id = id
		self.callback = callback
		self.result = None,None
		self.status = 'pending'
		self.done_event = threading.Event()
		
	def run(self):
		job.status = 'running'
		self.done_event.clear()
		try:
			r = func(*args, **kwargs)
		except Exception, e:
			self.result = None, e
		else:
			self.result = r, None
		job.status = 'finished'
		self.done_event.set()
	
	def join(self):
		self.done_event.wait()
		if self.result[1] is not None:
			raise self.result[1]
		else:
			return self.result[0]
