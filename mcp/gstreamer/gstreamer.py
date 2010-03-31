import gst
import threading
import gstreamer
import gobject
import Queue
import os

gobject.threads_init()

import sys
import traceback
import collections

class ordered_dict(dict):
	def __init__(self, new):
		self.order = []
		d = {}
		for k, v in new:
			d[k] = v
			self.order.append(k)
		dict.__init__(self,d)
	def __getitem__(self, key):
		if isinstance(key, str):
			return dict.__getitem__(self, key)
		elif isinstance(key, int):
			return dict.__getitem__(self, self.order[key])
		else:
			raise TypeError, 'Expected str or int'
	def get_key(self, index):
		return self.order[index]
	def __setitem__(self, key, value):
		if dict.has_key(self, key):
			if isinstance(key, str):
				dict.__setitem__(self, key, value)
			elif isinstance(key, int):
				dict.__setitem__(self, self.order[key], value)
		else:
			raise KeyError
	def __delitem__(self, key):
		if isinstance(key, int):
			i, key = key, dict.__getitem__(self, key)
			del self.order[i]
		elif isinstance(key, str):
			self.order.remove(key)
		dict.__delitem__(self, key)
	def append(self, key, value):
		dict.__setitem__(key, value)
		self.order.append(key)
	def extend(self, iterable):
		for k, v in iterable:
			self.append(k, v)
	def remove(self, key):
		del self[key]
	def __iter__(self):
		for k in self.order:
			yield k, dict.__getitem__(self, k)
	def __repr__(self):
		return '{' + ', '.join(['%r: %r' % (k,v) for k, v in self]) + '}'
	__str__ = __repr__

_message_types = dict((2**i, gst.MessageType(2**i).first_value_nick) for i in range(22))

def GstreamerErrorFactory(error, debug):
	code = error.code
	info = '\n'.join(debug.splitlines()[1:])
	msg = error.message
	if error.domain == gst.RESOURCE_ERROR:
		cls = ResourceError
	elif error.domain == gst.STREAM_ERROR:
		cls = StreamError
	else:
		print 'Unrecognized error', error, debug
		cls = GstreamerError
	return cls(code, info, msg)

class GstreamerError(Exception):
	name = 'GstreamerError'
	def __init__(self, code, info, msg):
		self.code = code
		self.info = info
		self.msg = msg
	def __str__(self):
		return '(%i) %s' % (self.code, self.info)
	def __repr__(self):
		return '<%s %r>' % (self.name, self.msg)
		
class ResourceError(GstreamerError):
	name = 'ResourceError'
	
class StreamError(GstreamerError):
	name = 'StreamError'
		
def convert(value):
	if isinstance(value, gst.Date):
		value = Date(value)
	elif isinstance(value, gst.Buffer):
		value = Buffer(value)
	elif hasattr(value, '__iter__'):
		value = [convert(v) for v in value]
	elif isinstance(value, gst.State):
		value = value.value_nick
	return value
	
class Structure(collections.MutableMapping):
	def __init__(self, struct=None):
		if struct is None:
			self._struct = gst.Structure('None')
		elif isinstance(struct, str):
			self._struct = gst.structure_from_string(struct)
		else:
			self._struct = struct
	@property
	def name(self):
		return self._struct.get_name()
	@name.setter
	def name(self, new):
		self._struct.set_name()
		
	def __contains__(self, key):
		return self._struct.has_field(key)
		
	def __len__(self):
		return self._struct.n_fields()
		
	def __getitem__(self, key):
		return convert(self._struct[key])
		
	def __setitem__(self, key, value):
		self._struct.set_value(key, value)
		
	def __delitem__(self, key):
		self._struct.remove_field(key)
		
	def __str__(self):
		return self._struct.to_string()
		
	def __iter__(self):
		return iter(self._struct.keys())
		
	def clear(self):
		self._struct.remove_all_fields()
		
def Caps(caps=None, **kargs):
	if caps is None:
		caps = gst.Caps()
	else:
		#print ', '.join([caps.to_string()] + ['='.join(map(str,i)) for i in kargs.items()])
		caps = gst.Caps(', '.join([caps.to_string()] + ['='.join(map(str,i)) for i in kargs.items()]))
	return caps
	#caps.__len__ = caps.get_size
	#del caps.get_size
	
	#caps.__str__ = caps.to_string
	#del caps.to_string

class Buffer:
	def __init__(self, buff):
		self.caps = Caps(buff.caps)
		self.data = buff.data
		
	def __str__(self):
		return '<Buffer %r of length %i>' % (self.caps.to_string(), len(self.data))
		
	__repr__ = __str__
		
class Date:
	def __init__(self, date):
		self.year = date.year
		self.month = date.month
		self.day = date.day
		
	def __str__(self):
		return '%i/%i/%i' % (self.month, self.day, self.year)
		
	__repr__ = __str__

class Element(gst.Element):
	def __new__(self, name, **props):
		g = gst.element_factory_make(name) if isinstance(name, str) else name
		for k in props:
			g.set_property(k,props[k])
		return g
		
	@property
	def name(self):
		return self.get_name()
	@name.setter
	def name(self, new):
		self.set_name(new)
		
	@classmethod
	def src_from_uri(cls, uri, **props):
		return cls(gst.element_make_from_uri('src', uri), **props)
	@classmethod
	def sink_from_uri(cls, uri, **props):
		return cls(gst.element_make_from_uri('sink', uri), **props)

class TextMenu(object):
	def __init__(self, struct):
		#print 'Building menu'
		self.struct = {}
		def fill(iterable):
			od = ordered_dict(iterable)
			for k, v in od:
				if isinstance(v, list):
					od[k] = fill(v)
			return od
		for k, v in struct.iteritems():
			self.struct[k] = fill(v)
		#print 'Built menu', self.struct
		self.element = Element('textoverlay', line_alignment=1, halignment=1, valignment=1)
		self.level = []
		self.index = 0
		self.bullets = ' *-'
		self.len = 0

	def __len__(self):
		return self.len

	def render_text(self):
		text = []
		menu = self.struct
		if self.level:
			for title in self.level:
				menu = menu[title]
			text.append(' '.join([self.bullets[2],title,self.bullets[2]]))
			for i, (k,v) in enumerate(menu):
				if self.index == i:
					text.append(' '.join([self.bullets[1],k,' ']))
				else:
					text.append(' '.join([self.bullets[0],k,' ']))
			self.len = i + 1
			self.element.props.text = '\n'.join(text)
			self.element.props.silent = False
		else:
			self.element.props.silent = True

	def up(self):
		try:
			self.index = (self.index - 1) % len(self)
		except ZeroDivisionError:
			return
		else:
			self.render_text()

	def down(self):
		try:
			self.index = (self.index + 1) % len(self)
		except ZeroDivisionError:
			return
		else:
			self.render_text()
			
	def left(self):
		#TODO: Handle left-right menu motion (selection, or adjustment of values,
		# possibly volume setting by default)
		pass
	
	def right(self):
		pass

	def run(self, path):
		menu = self.struct
		for title in path:
			menu = menu[title]
		v = menu[self.index]
		k = menu.get_key(self.index)
		if callable(v):
			#print 'Calling', v.__name__
			r = v(self.level + [k])
			if hasattr(r,'__iter__'):
				print 'Returned iterable'
				pass # TODO Dynamic menus
			elif not r:
				print 'Returned False'
				self.exit()
			else:
				print 'Returned True'
				pass
		elif isinstance(v, ordered_dict):
			self.level.append(k)
			self.index = 0
			self.render_text()

	def select(self):
		if self.level:
			self.run(self.level)

	def exit(self):
		self.element.props.silent = True
		self.index = 0
		self.level = []
		self.len = 0

	def back(self):
		if self.level:
			self.level.pop()
			self.render_text()

	def show(self, topmenu, *submenus):
		self.level = [topmenu]
		self.level.extend(submenus)
		self.render_text()
	
class Bin(gst.Bin):
	def __init__(self, *elements, **kargs):
		gst.Bin.__init__(self, kargs.get('name',None))
		elements = [Element(e) for e in elements]
		if len(elements) > 0:
			gst.Bin.add(self, *elements)
			if len(elements) > 1:
				gst.element_link_many(*elements)
			for typs, dir, index in (('sinks', gst.PAD_SINK, 0),('srcs', gst.PAD_SRC, -1)):
				if typs in kargs:
					for name in kargs[typs]:
						if isinstance(name, gst.Pad):
							pad, name = name, name.get_name()
						else:
							pad = elements[index].get_pad(name)
						gst.Bin.add_pad(self, gst.GhostPad(name, pad))
				else:
					i = 0
					for pad in elements[index].pads():
						if pad.props.direction == dir:
							gst.Bin.add_pad(self, gst.GhostPad(typs[:-1] + str(i), pad))
							i += 1
						
	def add_and_link(self, *elements):
		elements = [Element(e) for e in elements]
		gst.Bin.add(self, *elements)
		gst.element_link_many(*elements)
	
	def __getitem__(self, key):
		return list(gst.Bin.elements(self))[key]

class _Message(Structure):
	def __init__(self, msg):
		Structure.__init__(self, msg.structure)
		self.src = msg.src
		self.type = _message_types[msg.type]
		self.timestamp = msg.timestamp
		
	def __repr__(self):
		return ('<Message %s>' % self.type) if len(self) == 0 else ('<Message %s %r>' % (self.type, self.keys()))
	def __str__(self):
		return self.__repr__()
		
def Message(msg):
	if msg.type & gst.MESSAGE_TAG:
		return MessageTag(msg)
	elif msg.type & gst.MESSAGE_EOS:
		return MessageEos(msg)
	elif msg.type & (gst.MESSAGE_ERROR | gst.MESSAGE_WARNING):
		return MessageError(msg)
	elif msg.type & gst.MESSAGE_ASYNC_DONE:
		return MessageAsyncDone(msg)
	elif msg.type & gst.MESSAGE_STATE_CHANGED:
		return MessageStateChanged(msg)
	else:
		pass
		#print 'Unknown message %s' % msg.type
		
class MessageStateChanged(_Message):
	name = 'state-changed'
	def __init__(self, msg):
		_Message.__init__(self, msg)
	def __repr__(self):
		return '<Message %s %s>' % (self.type, self['new-state'])
		
class MessageTag(_Message):
	name = 'tag'
		
class MessageEos(_Message):
	name = 'eos'
	
class MessageAsyncDone(_Message):
	name = 'async-done'
	
class MessageError(_Message):
	name = 'error'
	def __init__(self, msg):
		_Message.__init__(self, msg)
		if msg.type & gst.MESSAGE_ERROR:
			self.error = GstreamerErrorFactory(*msg.parse_error())
		elif msg.type & gst.MESSAGE_WARNING:
			self.error = GstreamerErrorFactory(*msg.parse_warning())
	
	def __repr__(self):
		return '<Message %s %s>' % (self.error.name, str(self.error))
		
def queue_get(queue, timeout=1):
	while True:
		try:
			e = queue.get(True, timeout)
			return e
		except Queue.Empty:
			pass
		else:
			break

class object_proxy(object):
	def __init__(self, obj):
		self.__object = obj
		self.__props = {}
		
	def add_prop(self, name, get=None, set=None):
		self.__props[name] = (get, set)
		
	def __getattr__(self, name):
		if name in self.__props:
			return self.__props[name][0]()
		else:
			return getattr(self.__object, name)
		
class dict_proxy(collections.MutableMapping):
	def __init__(self, keys=None, get=None, set=None, delete=None):
		self.__keys = keys
		self.__get = get
		self.__set = set
		self.__del = delete
	
	def __getitem__(self, key):
		if self.__get:
			return self.__get(key)
		else:
			raise NotImplementedError
	def __setitem__(self, key, value):
		if self.__set:
			self.__set(key, value)
		else:
			raise NotImplementedError
	def __delitem__(self, key):
		if self.__delete:
			self.__delete(key)
		else:
			raise NotImplementedError
	def __len__(self):
		if self.__keys:
			return len(self.__keys())
		else:
			raise NotImplementedError
	def __iter__(self):
		if self.__keys:
			return iter(self.__keys())
		else:
			raise NotImplementedError

class Pipeline(object_proxy, dict_proxy, object):
	def xml_write(self):
		return gst.xml_write(self.__pipeline)
		
	def xml_write_file(self, f):
		if isinstance(f, str):
			gst.xml_write_file(self.__pipeline, open(f,'w'))
		else:
			gst.xml_write_file(self.__pipeline, f)
	
	def __init__(self, element):
		self.__pipeline = Element(element)
		object_proxy.__init__(self, self.__pipeline)
		object_proxy.add_prop(self, 'bus', self.__pipeline.get_bus, self.__pipeline.set_bus)
		object_proxy.add_prop(self, 'duration', lambda:self.__pipeline.query_duration(gst.FORMAT_TIME)[0] / float(gst.SECOND))
		object_proxy.add_prop(self, 'position', lambda:self.__pipeline.query_position(gst.FORMAT_TIME)[0] / float(gst.SECOND))
		dict_proxy.__init__(self, lambda:[p.name for p in self.__pipeline.props], self.__pipeline.get_property, self.__pipeline.set_property)
		self.property = dict_proxy(lambda:[p.name for p in self.__pipeline.props], self.__pipeline.get_property, self.__pipeline.set_property)
		self.xid_source = None
		
		self.bus.set_sync_handler(self.__sync_message_handler)
		self.bus.add_signal_watch()
		self.bus.connect('message', self.__message_handler)
		
		#self.__error = Queue.Queue()
		self.__cbs = collections.defaultdict(list)
		#self.__async = Queue.Queue()
		self.__messages = []#Queue.Queue()
		
	def connect(self, messages, callback, args=[], kargs={}):
		for m in messages:
			self.__cbs[m.name].append((callback, args, kargs))
		#print self.__cbs
		
	def seek(self, new):
		new = str(new)
		(additive,new) = (new[0],new[1:]) if new[0] in '-+' else (None,new)
		if new[-1] == '%':
			new = float(new[:-1]) * self.__pipeline.query_duration(gst.FORMAT_TIME)[0] / 100
		else:
			new = float(new) * gst.SECOND
		if additive == '+':
			new += self.__pipeline.query_position(gst.FORMAT_TIME)[0]
		elif additive == '-':
			new = self.__pipeline.query_position(gst.FORMAT_TIME)[0] - new
		self.__pipeline.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, new)
		
	def messages(self, timeout=1):
		q = Queue.Queue()
		try:
			self.__messages.append(q)
			m = queue_get(q, timeout)
			while not isinstance(m, MessageEos) and self.get_state() != 'null':
				yield m
				m = queue_get(q, timeout)
		finally:
			self.__messages.remove(q)
	
	def get_state(self):
		return self.__pipeline.get_state()[1].value_nick
	def set_state(self, new, wait=False):
		#print 'set_state', new, "don't wait" if not wait else 'wait'
		if self.get_state() == new:
			return
		result = self.__pipeline.set_state(new)
		#print result
		if result == gst.STATE_CHANGE_ASYNC and wait:
			print 'waiting on async'
			for e in self.messages():
				#print 'got message', e
				if isinstance(e, GstreamerError):
					raise e
				elif isinstance(e, MessageAsyncDone):
					break
		elif result == gst.STATE_CHANGE_FAILURE and wait:
			#print 'waiting on failure'
			raise queue_get(self.__error)
		else:
			#print 'not waiting'
			return result == gst.STATE_CHANGE_SUCCESS
	
	def __sync_message_handler(self, bus, message):
		m = Message(message)
		#print m
		for q in self.__messages:
			q.put(m)
		if message.type == gst.MESSAGE_ELEMENT:
			if message.structure is not None and message.structure.get_name() == 'prepare-xwindow-id':
				if hasattr(self.xid_source,'window') and self.xid_source.window is not None:
					message.src.set_property('force_aspect_ratio', True)
					message.src.set_xwindow_id(self.xid_source.window.xid)
		return True
	
	def __message_handler(self, bus, message):
		message = Message(message)
		if message is not None:
			for m in self.__cbs[message.name]:
				func, args, kargs = m
				r = func(*args, **kargs)
				if not (r or r is None):
					self.__cbs[type(message)].remove((func, args, kargs))
		return True

	def __del__(self):
		self.__async.put(None)
		self.set_state('null')
		self.bus.remove_signal_watch()

def uri(path):
	if ':' not in path.partition('/')[0]:
		return 'file://' + os.path.abspath(path)
	else:
		return path

class tag_reader(object):
	def __init__(self, normalize=False):
		self.pipeline = Pipeline(Element('playbin'))
		self.pipeline = Pipeline(Element('playbin'))
		self.pipeline['video-sink'] = Element('fakesink')
		if normalize:
			self.pipeline['audio-sink'] = Bin('rganalysis','fakesink')
		else:
			self.pipeline['audio-sink'] = Element('fakesink')

	def __call__(self, uri):
		try:
			pipeline['uri'] = uri
			tags = {}
			pipeline.set_state('playing', wait=False)
			for msg in pipeline.messages():
				if not normalize and isinstance(msg, MessageAsyncDone):
					break
				elif isinstance(msg, MessageTag):
					tags.update(msg)
				elif isinstance(msg, MessageError):
					raise msg.error
				elif isinstance(msg, MessageEos):
					break
			tags['duration'] = pipeline.duration
		except Exception,e:
			traceback.print_exc()
		finally:
			pipeline.set_state('null')
		return tags

def get_tags(uri, normalize=False):
	return tag_reader(normalize)(uri)

def gsub(func):
	def f(*args):
		try:
			func(*args)
		except KeyboardInterrupt:
			exit()
		finally:
			main_quit()
	def g(*args):
		gobject.idle_add(f,*args)
		main()
	return g

__MainLoop = gobject.MainLoop()

def main():
	__MainLoop.run()
	
def main_quit():
	__MainLoop.quit()
	
idle_add = gobject.idle_add

if __name__=='__main__':
	@gsub
	def f():
		print get_tags('/home/ryan/Music/test.mp3')
	f()
