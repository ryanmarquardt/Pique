import gtk

class VideoWidget(gtk.Container):
	def __init__(self, gst, window):
		vbox = gtk.VBox()
		self.add(vbox)
		drawingarea = gtk.DrawingArea()
		vbox.pack_start(drawingarea)
		controlbar = gtk.HButtonBox()
		buttons = {}
		for b in ('play','pause','stop'):
			buttons[b] = gtk.Button(stock='stock-media-%s' % b)
			controlbar.pack_start(buttons[b])
		vbox.pack_end(controlbar)
		self.add(vbox)
		
class VideoWidget(gtk.DrawingArea):
	"""VideoWidget(gtk.DrawingArea) -> 
	
constructor: VideoWidget(self, gst, ...)
returns a gtk.DrawingArea which is set as the target xwindow for gst.
"""
	def __init__(self, sink, *args, **kargs):
		gtk.DrawingArea.__init__(self, *args, **kargs)
		gtk.DrawingArea.connect(self, 'realize', self._realized)
		self._sink = sink

	def _realized(self, sender):
		self._sink.set_xwindow_id(self.window.xid)
		return True

