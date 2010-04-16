#!/usr/bin/env python

import sqlite3
import re
import os.path
import collections
import threading

VERBOSE = True

DEFAULT_PATH = os.path.expanduser('~/.mcp-library')

COLUMNS = [
	('uri','text unique on conflict replace'),
	('title','text'),
	('artist','text'),
	('album','text'),
	('date','text'),
	('track_number','integer'),
	('peak','real'),
	('gain','real'),
	('reference_level','real'),
	('audio_codec','text'),
	('duration','real'),
]

Row = collections.namedtuple('Row', [i[0] for i in COLUMNS])

TABLE_NAME = u"media"

CREATE_SQL = u"create table %s (%s) " % (TABLE_NAME, ", ".join(["%s %s" % i[0:2] for i in COLUMNS]))
INSERT_SQL = u"insert into %s values (%s) " % (TABLE_NAME, ",".join("?"*len(COLUMNS)))
ORDER_SQL = u"order by artist,album,track_number "
SEARCH_SQL = u'where %s=? '
SELECT_SQL = u'select rowid,* from %s ' % TABLE_NAME
DELETE_SQL = u'delete from %s where rowid=?' % TABLE_NAME

from gstreamer import *

class library(object):
	def __init__(self, path):
		self.db = {}
		self.db[threading.currentThread()] = sqlite3.connect(path)
		self.path = path

	def __del__(self):
		for db in self.db.values():
			db.commit()
			db.close()
			
	def _get_db(self):
		t = threading.currentThread()
		if t not in self.db:
			self.db[t] = sqlite3.connect(self.path)
		return self.db[t]

	def init(self):
		db = self._get_db()
		c = db.cursor()

		c.execute('drop table media')
		c.execute(CREATE_SQL)
		db.commit()
		if VERBOSE: print "Successfully initialized library at %r" % self.path

	def add(self, uri):
		self.addmany((uri,))

	@gsub
	def addmany(self, uris):
		tagger = tag_reader()
		db = self._get_db()
		for uri in uris:
			uri = unicode(uri)
			c = db.cursor()
			c.execute(SELECT_SQL + SEARCH_SQL % 'uri', (uri,))
			if c.fetchone():
				print >> sys.stderr, 'Skipping', uri
			else:
				if VERBOSE: print 'Adding', uri
				tags = collections.defaultdict(lambda:None, tagger(uri))
				print '{\n\t%s\n}' % ',\n\t'.join(["%r: %r" % item for item in sorted(tags.items())])
				if 'date' in tags:
					tags['date'] = unicode(tags['date'])
				NewRow = Row(
					uri = uri,
					title = tags['title'],
					artist = tags['artist'],
					album = tags['album'],
					date = tags['date'],
					track_number = tags['track-number'],
					peak = tags['replaygain-track-peak'],
					gain = tags['replaygain-track-gain'],
					reference_level = tags['replaygain-reference-level'],
					audio_codec = tags['audio-codec'],
					duration = tags['duration'],
				)
				print NewRow
				c.execute(INSERT_SQL, NewRow)
				db.commit()

	def remove(self, id):
		db = self._get_db()
		c = db.cursor()
		c.execute(DELETE_SQL, (id,))
		db.commit()

	def __iter__(self):
		db = self._get_db()
		c = db.cursor()
		c.execute('select rowid,* from %s' % TABLE_NAME)
		for row in c:
			yield row[0], Row._make(row[1:])

	def members(self, column):
		db = self._get_db()
		c = db.cursor()
		if column in [i[0] for i in COLUMNS]:
			c.execute('select distinct %s from %s' % (column,TABLE_NAME))
		for i in c:
			yield i[0]

	def filter(self, *criteria):
		db = self._get_db()
		c = db.cursor()

	def __getitem__(self, index):
		db = self._get_db()
		c = db.cursor()
		c.execute('select * from %s where rowid=?' % TABLE_NAME, (index,))
		r = c.fetchone()
		if r is None:
			raise IndexError('library[%i]: no such entry' % index)
		else:
			return Row._make(r)

	def index(self, uri):
		db = self._get_db()
		c = db.cursor()
		c.execute('select rowid from %s where uri=?' % TABLE_NAME, (uri,))
		try:
			return c.fetchone()[0]
		except TypeError:
			raise ValueError("library.index(uri): uri not in library")

def uri(path):
	return path if re.match('[a-zA-Z0-9]+://.*', path) else 'file://%s' % os.path.abspath(path)

if __name__=='__main__':
	import sys

	l = library(DEFAULT_PATH)

	if sys.argv[1] == 'init':
		l.init()
	elif sys.argv[1] == 'add':
		uris = []
		for i in sys.argv[2:]:
			if os.path.isdir(i):
				for root,dirs,files in os.walk(i):
					for f in files:
						uris.append(uri((os.path.join(root,f))))
			else:
				uris.append(uri(i))
		l.addmany(uris)
	elif sys.argv[1] == 'list':
		if len(sys.argv) < 3:
			for index, row in l:
				print row
		else:
			for row in l.members(sys.argv[2]):
				print row
	elif sys.argv[1] == 'edit':
		id = sys.argv[2]
		
	elif sys.argv[1] == 'find':
		pass
	else:
		print 'Error: No command specified'
		exit(1)
