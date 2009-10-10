#!/usr/bin/python
import collections
import functools
import gobject

import gtk
import library
import trace
import types
import traceback
import sys
import video_widget
import xmlrpclib

from mcp.types import nested_dict, Song
from mcp.debug import *
from gstreamer import *

lib_entry = Song

class gui(object):
	def __init__(self, gst, height=100, width=100):
		self.__fullscreen = False
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.connect('window-state-event',self._events)
		self.window.set_default_size(width, height)
		self.video = video_widget.VideoWidget(gst)
		self.window.add(self.video)
		self.window.show_all()
		
	def _events(self, window, event):
		if event.type & gtk.gdk.WINDOW_STATE:
			self.__fullscreen = bool(gtk.gdk.WINDOW_STATE_FULLSCREEN & event.new_window_state)
		return False
		
	def fullscreen(self, new=None):
		if new is None:
			return self.__fullscreen
		elif new:
			gobject.idle_add(self.window.fullscreen)
		else:
			gobject.idle_add(self.window.unfullscreen)

def xml_marshal(tag):
	if isinstance(tag, Date):
		return xmlrpclib.DateTime('%04d%02d%02d' % (tag.year, tag.month, tag.day))
	elif isinstance(tag, Buffer):
		return {str(tag.caps):xmlrpclib.Binary(tag.data)}
	elif isinstance(tag, collections.Mapping):
		return dict((xml_marshal(k),xml_marshal(tag[k])) for k in tag)
	elif isinstance(tag, types.StringType):
		#Handle this first, because strings are also sequences
		return tag
	elif isinstance(tag, collections.Sequence):
		return [xml_marshal(t) for t in tag]
	else:
		return tag

class player():
	def __init__(self):
		self.gst = Pipeline('playbin')
		
		self.gst.connect([MessageEos], self.next)
		#self.gst.connect([MessageTag], self.new_tag)
		
		##Video Sink
		self.timeoverlay = Element('timeoverlay', line_alignment=0, halignment=0, silent=True)
		self.textoverlay = Element('textoverlay', line_alignment=2, halignment=2, silent=False)
		def debug(path): print path
		self.menu = TextMenu({'Main Menu':[('Entry 1',debug),('Entry 2',debug),('Submenu 1',[('Subentry 1',debug),('Subentry 2',debug),])]})
		videocaps = Caps()
		for height in (480, 720, 1080): #DVD and HD resolutions
			for aspectratio in (4./3, 5./3, 16./9, 55./23): #TV, Widescreen PC, HD, Panavision
				for mediatype in ('video/x-raw-yuv', 'video/x-raw-rgb'):
					videocaps |= Caps(mediatype, height=height, width=int(height * aspectratio))
		self.capsfilter = Element('capsfilter', caps=videocaps)
		
		###Audio Sink
		self.taginject = Element('taginject')
		
		self.gst['video_sink'] = Bin(self.capsfilter, self.timeoverlay, self.textoverlay, self.menu.element, 'gconfvideosink')
		self.gst['audio_sink'] = Bin(self.taginject, 'rgvolume', 'gconfaudiosink')
		self.gst['vis_plugin'] = Bin('goom2k1')
		
		self.__song = None
		
		self.gui = gui(self.gst, height=480, width=768)
		self.gui.window.connect('destroy', self.kill)
		self.playlist = library.playlist()
		self.library = library.library()
		self.methods = nested_dict('.', {
			'kill':(self.kill,),
			'play':self.play,
			'pause':(self.gst.set_state,'paused'),
			'stop':(self.gst.set_state,'null'),
			'seek':(self.gst.seek,),
			'set_text':(self.textoverlay.set_property,'text'),
			'show_text':self.show_text,
			'show_time':self.show_time,
			'info':(self.info,),
			'next':self.next,
			'prev':self.prev,
			'status':self.status,
			'fullscreen':(self.gui.fullscreen,),
			'menu':{
				'show':(self.menu.show,'Main Menu'),
				'back':(self.menu.back,),
				'up':(self.menu.up,),
				'down':(self.menu.down,),
				'left':(self.menu.left,),
				'right':(self.menu.right,),
				'select':(self.menu.select,),
			},
			'playlist':{
				'add':(self.playlist.append,),
				'remove':(self.playlist.remove,),
				'clear':(self.playlist.clear,),
				'list':self.playlist_list,
				'loop':self.playlist_loop,
				'shuffle':(self.playlist.shuffle,),
				'random':self.playlist_random,
				'new':self.playlist_new,
			},
			'lib':{
				'add_local':(self.library.add_local_path,),
				'add_uri':(self.library.add_uri,),
				'import_uri':(self.library.import_uri,),
				'remove':(self.library.remove_hash,),
				'list':self.lib_list,
				'info':self.lib_info,
			},
		})
		print sorted(self.methods.keys())
		
	def get_song(self):
		return self.__song
		
	def set_song(self, song):
		print 'set_song', song
		self.__song = song
		self.gst.set_state('ready')
		if song is None:
			self.gst['uri'] = ''
			self.textoverlay.set_property('text', '')
			self.gst.set_state('null')
		else:
			print song
			self.gst['uri'] = song.uri
			self.taginject.props.tags = song.tag_list()
			artist = song.get('artist', 'Unknown Artist')
			title = song.get('title', 'Unknown Title')
			album = song.get('album', 'Unknown Album')
			self.textoverlay.props.text = '\n'.join([artist, title, album])
		
	def _dispatch(self, func, args):
		if func in self.methods.keys():
			sys.stdout.write(func)
			sys.stdout.write('(')
			sys.stdout.write(', '.join(map(repr,args)))
			sys.stdout.write(')\n')
			sys.stdout.flush()
			try:
				f = self.methods[func]
				if isinstance(f, tuple):
					r = f[0](*(f[1:] + args))
				else:
					r = f(*args)
				return xml_marshal(r)
			except GstreamerError, g:
				print g.name, g.msg, g.info
				code, message = ': '.join((g.name, g.msg)), g.info
				return xmlrpclib.Fault(code, message)
			except:
				t = traceback.format_exc()
				print t
				return xmlrpclib.Fault(1, t)
		else:
			print 'Unknown Command', func, args
			
	def _listMethods(self):
		return self.methods.keys()

	#Pure gstreamer methods
	def play(self):
		if self.get_song() is None:
			self.next()
		self.gst.set_state('playing')

	def show_text(self, new=None):
		if new is None:
			return self.textoverlay.props.silent
		elif new:
			self.textoverlay.props.silent = False
		else:
			self.textoverlay.props.silent = True
		
	def show_time(self, new=None):
		if new is None:
			return self.timeoverlay.props.silent
		elif new:
			self.timeoverlay.props.silent = False
		else:
			self.timeoverlay.props.silent = True
			
	def info(self):
		self.textoverlay.props.silent = not self.textoverlay.props.silent
		if self.textoverlay.props.silent:
			self.timeoverlay.props.silent = not self.timeoverlay.props.silent

	def next(self):
		song = self.playlist.next()
		self.set_song(song)
	
	def prev(self):
		if self.gst.get_state() in ('playing', 'paused') and self.gst.position > 5:
			self.gst.set_state('ready')
			self.gst.set_state('playing')
		else:
			song = self.playlist.prev()
			self.set_song(song)

	def status(self):
		d = {
			'volume': self.gst.props.volume,
			'repeat': int(self.playlist.loop),
			'random': int(self.playlist.random),
			'playlist': self.playlist.version,
			'playlistlength': len(self.playlist),
			'state': self.gst.get_state(),
			'song': self.get_song(),
		}
		try:
			d['position'] = self.gst.position
			d['duration'] = self.gst.duration
		except:
			pass
		return d

	##Playlist methods
	def playlist_list(self,*fields):
		if len(fields) == 0:
			return list(self.playlist)
		else:
			r = []
			for song in self.playlist:
				d = [song.get(t,'') for t in fields]
				r.append(d)
			return r

	def playlist_loop(self, new=None):
		if new is None:
			return self.playlist.loop
		else:
			self.playlist.loop = new

	def playlist_random(self, new=None):
		if new is None:
			return self.playlist.random
		else:
			self.playlist.random = new
			
	def playlist_new(self, *args):
		self.playlist.clear()
		self.playlist.extend(self.library.query(*args))
			
	##Library Methods
	def lib_list(self,*fields):
		if len(fields) == 0:
			return self.library.db.keys()
		else:
			r = []
			for song in self.library:
				d = [song.get(t,'') for t in fields]
				r.append(d)
			for a in sorted(r,key=lambda x:x[1]):
				print a
			return r
		
	def lib_info(self, *hashes):
		return [dict(self.library.db[hash].items()) for hash in hashes]
