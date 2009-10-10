import functools
import signal
import threading
import SimpleXMLRPCServer

import gtk
import gobject

import gstreamer

from decorators import *
from mcp.debug import *

class ExceptionInThread(Exception):
	pass

class ControllerThread(threading.Thread):
	def __init__(self, cleanup=lambda:None, *args, **kargs):
		threading.Thread.__init__(self, *args, **kargs)
		if not hasattr(self, 'cleanup'):
			self.cleanup = cleanup
		self.error = None
		
	def start(self):
		f = self.run
		@functools.wraps(self.run)
		def new_f(*args, **kargs):
			try:
				f(*args, **kargs)
			except:
				self.error = traceback.format_exc()
				raise ExceptionInThread(self.error)
		self.run = new_f
		threading.Thread.start(self)

@rpcinstance(ignore=['run','quit'])
class gui(gstreamer.player):
	threads = []
	def __init__(self):
		gstreamer.player.__init__(self)
		self.gst.video_sink='gconfvideosink'
		self.gst.audio_sink='gconfaudiosink'
		self.gst.vis_plugin='goom2k1'
		
		gtk.gdk.threads_init()
		self.errors = []
		
		rpc = rpc_thread(self)
		self.threads.append(rpc)
		self.cleaning_up = False

	def run(self):
		try:
			signal.signal(signal.SIGINT, lambda x,y:self.quit())
			self._build_gui()
			print 'Starting threads...',
			for thread in self.threads:
				print thread.name,
				thread.start()
			print 'gtk'
			gtk.main()
		finally:
			self.quit()
		
	def quit(self):
		#Quit might be called multiple times so we need to perform checks
		#  to make sure calls aren't run too many times.
		print 'quit from', threading.current_thread()
		if not self.cleaning_up:
			self.cleaning_up = True
			#for event in self._event:
				#if event != 'error':
					#self._event[event].set()
			print 'Cleaning up threads...',
			if gtk.main_level():
				print 'gtk',
				gtk.main_quit()
			for thread in self.threads:
				try:
					print thread.name,
					if thread.is_alive():
						thread.cleanup()
				except:
					#Propogate any errors that occur
					self.errors.append(traceback.format_exc())
				else:
					if thread.error is not None:
						self.errors.append(thread.error)
			print
			
			#Wait for all threads to end
			for t in self.threads:
				while t.is_alive():
					print 'Waiting for', t.name
					t.join(1)
			print 'Done'
			
			#Return any errors
			for error in self.errors:
				raise ExceptionInThread(error)
			
	def _build_gui(self):
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.video = gstreamer.video_widget.VideoWidget(self.gst)

		self.window.add(self.video)
		self.window.show_all()
		
	#Window specific commands
	def fullscreen(self, new=None):
		if new:
			gobject.idle_add(self.window.fullscreen)
		else:
			gobject.idle_add(self.window.unfullscreen)
			
	def kill(self):
		gobject.idle_add(self.quit)

class rpc_thread(ControllerThread):
	def __init__(self, gui, addr='localhost', port=8145):
		class ReqHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
			def do_GET(self, *args, **kargs):
				print 'GET', args, kargs
			def do_POST(self, *args, **kargs):
				print '-- POST', ":".join(str(i) for i in self.client_address), '-'*20
				SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.do_POST(self, *args, **kargs)
				print
		self.server = SimpleXMLRPCServer.SimpleXMLRPCServer((addr, port),
			requestHandler=ReqHandler, allow_none=True, logRequests=True)
		self.server.register_introspection_functions()
		self.server.register_multicall_functions()
		self.server.register_instance(gui)
		ControllerThread.__init__(self, name='rpc')

	def run(self):
		self.server.serve_forever()
	
	def cleanup(self):
		self.server.shutdown()

