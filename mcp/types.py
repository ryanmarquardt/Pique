#!/usr/bin/python

import collections
import gst

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


class nested_dict(dict):
	def __init__(self,delimiter,*args,**kargs):
		self.__delimiter = delimiter
		dict.__init__(self, *args, **kargs)
		
	def __getitem__(self, key):
		path_members = key.split(self.__delimiter)
		item = dict.__getitem__(self,path_members[0])
		for key in path_members[1:]:
			item = item[key]
		return item
		
	def iterkeys(self):
		#TODO: only dives 1 level
		for k, v in dict.items(self):
			if isinstance(v, dict):
				for ky in v.keys():
					yield k + self.__delimiter + ky
			else:
				yield k
		
	def keys(self):
		return list(self.iterkeys())
		
class stack_dict(dict):
	def __init__(self, orig, *args, **kargs):
		self.orig = orig
		dict.__init__(self, *args, **kargs)
		
	def __len__(self):
		return len(set(self.keys() + self.orig.keys()))
		
	def __getitem__(self, k):
		#Return my item, otherwise orig's item, otherwise error
		if dict.__contains__(self, k):
			return dict.__getitem__(self, k)
		elif k in self.orig:
			return self.orig[k]
		else:
			raise KeyError('%r not in either dictionary' % k)
		
	def __contains__(self, k):
		return k in (dict.keys(self) + self.orig.keys())
		
	def keys(self):
		return list(self.iterkeys())
		
	def iterkeys(self):
		origs = self.orig.keys()
		for k in dict.keys(self):
			if k in origs:
				origs.remove(k)
			yield k
		for k in origs:
			yield k
	__iter__ = iterkeys
			
	def values(self):
		return list(self.itervalues())
	
	def itervalues(self):
		origs = self.orig.keys()
		for k in dict.keys(self):
			if k in origs:
				origs.remove(k)
			yield dict.__getitem__(self,k)
		for k in origs:
			yield self.orig[k]
			
	def items(self):
		return list(self.iteritems())
		
	def iteritems(self):
		origs = self.orig.keys()
		for k in dict.keys(self):
			if k in origs:
				origs.remove(k)
			yield (k, dict.__getitem__(self, k))
		for k in origs:
			yield (k, self.orig[k])
		
	def copy(self):
		return stack_dict(self.orig, dict.copy(self))
		
	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default
			
	def setdefault(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			self[key] = default
			return default
			
	def __eq__(self, x):
		return (self.items() == x.items())
		
	def __ne__(self, x):
		return (self.items() != x.items())
			
	has_key = __contains__
	
	def __str__(self):
		return str(dict(self.items()))
		
	def __repr__(self):
		return repr(dict(self.items()))

class checklist(collections.MutableSequence, list):
	__delitem__ = list.__delitem__
	
	def __setitem__(self, index, item):
		list.__setitem__(self, index, (False, item))
		
	def check(self, index, value=True):
		item = list.__getitem__(self, index)[1]
		list.__setitem__(self, index, (value, item))
		
	def uncheck(self, index):
		item = list.__getitem__(self, index)[1]
		list.__setitem__(self, index, (False, item))
		
	def __getitem__(self, index):
		return list.__getitem__(self, index)[1]
		
	def is_checked(self, index):
		return list.__getitem__(self, index)[0]
		
	def insert(self, index, item):
		list.insert(self, index, (False, item))
		
	__len__ = list.__len__
	
	def checked(self):
		return [a[1] for a in list.__iter__(self) if a[0]]
		
	def unchecked(self):
		return [a[1] for a in list.__iter__(self) if not a[0]]
		
	def __repr__(self):
		r = []
		for c, i in self:
			r.append('%s%r' % ('' if c else '~', i))
		return '[' + ', '.join(r) + ']'
		
class Song(stack_dict):
	def __init__(self, uri=None, hash=None):
		if uri is not None:
			self.uri = uri
			self.hash = hash
		stack_dict.__init__(self)
		
	def tag_list(self):
		t = gst.TagList()
		print t
		for k, v in self.items():
			try:
				t[k] = v
			except:
				print "Couldn't set t[%s] = %r" % (k,v)
		return t
		
	def __getstate__(self):
		return [self.uri, self.orig, dict.copy(self)]

	def __setstate__(self, state):
		self.uri = state[0]
		self.orig = state[1]
		self.update(state[2])
		
	def __repr__(self):
		return '<Song %s %s:%s:%s>' % (self.uri, self.get('artist',''), self.get('title',''), self.get('album',''))
