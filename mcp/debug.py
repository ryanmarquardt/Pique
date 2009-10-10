#!/usr/bin/python

DEBUG = True

def public_callables(cls, ignore=[]):
	for name in dir(cls):
		method = getattr(cls, name)
		if not name.startswith('_') and callable(method) and name not in ignore:
			yield name, method
			
def all_callables(cls):
	for name in dir(cls):
		method = getattr(cls, name)
		if callable(method):
			yield name, method

def wraps(wrapped):
	def update_wrapper(wrapper):
		for attr in ('__name__','__doc__','__module__'):
			try:
				setattr(wrapper, attr, getattr(wrapped, attr))
			except AttributeError:
				pass
		for attr in ('__dict__',):
			try:
				getattr(wrapper, attr).update(getattr(wrapped, attr, {}))
			except AttributeError:
				pass
		return wrapper
	return update_wrapper

def debug_method(f):
	if DEBUG:
		@wraps(f)
		def new_f(*args, **kargs):
			print f.__name__, args, kargs
			r = f(*args, **kargs)
			print f.__name__, 'returned', r
			return r
		return new_f
	else:
		return f

def debug_methods(cls):
	if DEBUG:
		for name, method in public_callables(cls): #:
			setattr(cls, name, debug_method(method))
	return cls

_property = property

class property(_property):
	def __get__(self, obj, type=None):
		r = _property.__get__(self, obj, type)
		if r is not self:
			print 'get', self.fget.__name__, '->', r
		return r
	def __set__(self, obj, value):
		print 'set', self.fset.__name__, 'to', value
		return _property.__set__(self, obj, value)
	def __delete__(self, obj):
		print 'delete', self.fdel.__name__
		return _property.__delete__(self, obj)
		
property = _property

if DEBUG:
	__all__ = ['public_callables', 'all_callables', 'debug_method', 'debug_methods', 'property']
else:
	__all__ = ['debug_method', 'debug_methods', 'public_callables', 'all_callables']
