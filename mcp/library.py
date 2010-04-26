#!/usr/bin/env python

import collections
import os.path
import re
import sqlite3
import threading
import traceback

from player import *

VERBOSE = True

DEFAULT_PATH = os.path.expanduser('~/.mcp-library')

COLUMNS = [
	('uri','text unique on conflict replace'),
	('title','text'),
	('artist','text'),
	('album','text'),
	('date','text'),
	('track_number','integer'),
	('replaygain_track_peak','real'),
	('replaygain_track_gain','real'),
	('replaygain_reference_level','real'),
	('audio_codec','text'),
	('duration','real'),
]
columns = [i[0] for i in COLUMNS]

Row = collections.namedtuple('Row', [i[0] for i in COLUMNS])

TABLE_NAME = u"media"

CREATE_SQL = u"create table %s (%s) " % (TABLE_NAME, ", ".join(["%s %s" % i[0:2] for i in COLUMNS]))
INSERT_SQL = u"insert or replace into %s values (%s) " % (TABLE_NAME, ",".join("?"*len(COLUMNS)))
ORDER_SQL = u"order by artist,album,track_number "
SEARCH_SQL = u'where %s=? '
SELECT_SQL = u'select * from %s ' % TABLE_NAME
DELETE_SQL = u'delete from %s where uri=?' % TABLE_NAME

from common import *

def gsub(func):
	main = gobject.MainLoop()
	def f(*args):
		try:
			func(*args)
		except KeyboardInterrupt:
			exit()
		finally:
			main.quit()
	def g(*args):
		gobject.idle_add(f,*args)
		main.run()
	return g
	
class tag_reader(object):
	def __init__(self):
		self.playbin = Element('playbin')
		self.playbin.set_property('audio-sink', Bin(Element('rganalysis'), Element('fakesink')))
		self.playbin.set_property('video-sink', Element('fakesink'))
		
	def on_update(self):
		sys.stdout.write('.')
		sys.stdout.flush()
		
	def __call__(self, uri, update_callback=None, update_frequency=1, normalize=True):
		try:
			self.playbin.set_property('uri', uri)
			tags = {}
			self.playbin.set_state('playing')
			bus = self.playbin.get_bus()
			while True:
				msg = bus.poll(gst.MESSAGE_ANY, update_frequency*gst.SECOND)
				if msg is None:
					self.on_update()
					continue
				elif msg.type & gst.MESSAGE_EOS:
					break
				elif msg.type & gst.MESSAGE_ERROR:
					raise GstError(*msg.parse_error())
				elif not normalize and msg.type & gst.MESSAGE_ASYNC_DONE:
					break
				elif msg.type & gst.MESSAGE_TAG:
					taglist = msg.parse_tag()
					for k in taglist.keys():
						tags[k.replace('-','_')] = taglist[k]
			tags['duration'] = self.playbin.query_duration(gst.FORMAT_TIME, None)[0]
		finally:
			self.playbin.set_state('null')
		return tags

class library(collections.MutableMapping):
	def __init__(self, path):
		self.__db = {}
		self.__db[threading.currentThread()] = sqlite3.connect(path)
		self.path = path
		
	def __del__(self):
		for db in self.__db.values():
			db.commit()
			db.close()
			
	@property
	def db(self):
		t = threading.currentThread()
		if t not in self.__db:
			self.__db[t] = sqlite3.connect(self.path)
		self.__db[t].create_function('regexp', 2, lambda x,i:bool(re.match(x,i)))
		return self.__db[t]

	def init(self):
		c = self.db.cursor()
		c.execute('drop table media')
		c.execute(CREATE_SQL)
		self.db.commit()
		verbose("Successfully initialized library at", repr(self.path))
		
	def __iter__(self):
		debug('__iter__')
		c = self.db.cursor()
		c.execute('select uri from %s' % TABLE_NAME)
		for row in c:
			yield row[0]
		
	def __len__(self):
		debug('__len__')
		c = self.db.cursor()
		c.execute('select uri from %s' % TABLE_NAME)
		return len(list(c))
		
	def __getitem__(self, uri):
		debug('__getitem__', uri)
		c = self.db.cursor()
		c.execute('select * from %s where uri=?' % TABLE_NAME, (uri,))
		r = c.fetchone()
		if r is None:
			raise KeyError('library[%s]: no such entry' % uri)
		else:
			return Row._make(r)
		
	def __setitem__(self,key,value):
		debug('__setitem__',key,value)
		c = self.db.cursor()
		c.execute(INSERT_SQL, value)
		self.db.commit()
		
	def __delitem__(self, uri):
		debug('__delitem__', uri)
		self.db.cursor().execute(DELETE_SQL, (uri,))
		self.db.commit()
		
	@gsub
	def add(self, files, force=False, **kwargs):
		uris = []
		for i in files:
			if os.path.isdir(i):
				for root,dirs,files in os.walk(i):
					uris.extend([uri(os.path.join(root,f)) for f in files])
					#for f in files:
						#uris.append(uri((os.path.join(root,f))))
			else:
				uris.append(uri(i))
		tagger = tag_reader()
		for uri in uris:
			if not force and unicode(uri) in self:
				verbose('Skipping', uri)
			else:
				verbose('Adding', uri)
				tags = collections.defaultdict(lambda:None, tagger(uri, normalize=True))
				print '{\n\t%s\n}' % ',\n\t'.join(["%r: %r" % item for item in sorted(tags.items())])
				tags['uri'] = uri
				if 'date' in tags:
					tags['date'] = unicode(tags['date'])
				rowtags = dict((k,tags.get(k,None)) for k in [i[0] for i in COLUMNS])
				print rowtags
				NewRow = Row(**rowtags)
				self[NewRow.uri] = NewRow
				self.db.commit()

	def members(self, column):
		c = self.db.cursor()
		if column in [i[0] for i in COLUMNS]:
			c.execute('select distinct %s from %s' % (column,TABLE_NAME))
		for i in c:
			yield i[0]
		
	def select(self, **kwargs):
		c = self.db.cursor()
		c.execute('select * from %s where ' + ','.join(['%s=?' for k in kwargs.keys()]), kwargs.values())
		for i in c:
			yield Row._make(i)
			
	def select_uris(self, **kwargs):
		c = self.db.cursor()
		if kwargs:
			sql = 'select uri from %s where ' % TABLE_NAME + \
			  ','.join([k + ' regexp ?' for k in kwargs.keys()])
		else:
			sql = 'select uri from %s' % TABLE_NAME
		c.execute(sql, kwargs.values())
		for i in c:
			yield i[0]
			
	def update(self, uri, **kwargs):
		c = self.db.cursor()
		sql = 'update or abort %s set %s where uri=?' % (
		  TABLE_NAME,
		  ','.join(['%s=?' % k for k in kwargs.keys()]),
		)
		#print sql, kwargs.values() + [uri,]
		if kwargs:
			c.execute(sql, kwargs.values() + [uri,])
			self.db.commit()

class uri(tuple):
	def __new__(self, path):
		if re.match('[a-zA-Z0-9]+://.*', path):
			return tuple(path.partition('://')[0::2])
		else:
			return 'file', path

	def __str__(self):
		return '%s://%s' % self

	@property
	def protocol(self):
		return self[0]

__all__ = ['uri', 'library', 'tag_reader', 'gsub', 'DEFAULT_PATH']
