class Playlist(object):
	def __init__(self, files=[]):
		self.files = files
		self.order = range(len(files))
		self.cursor = -1
		
	def next(self):
		self.cursor += 1
		if self.cursor >= len(self.order):
			self.cursor = -1
			raise StopIteration
		else:
			n = self.files[self.order[self.cursor]]
			return n
		
	def previous(self):
		self.cursor -= 1
		if self.cursor < 0:
			self.cursor = -1
			raise StopIteration
		else:
			n = self.files[self.order[self.cursor]]
			return n
		
	def append(self, uri):
		self.files.append(uri)
		self.order.append(len(self.order))
