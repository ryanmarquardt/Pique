DEBUG = True
TIME_FORMAT = 'hms'
def debug(*args):
	if DEBUG:
		print ' '.join(map(str,args))

#import collections
import ConfigParser
import os
#import select
import signal
#import socket
import sys
#import threading
import time
import traceback

import pygtk, gtk, gobject
import pygst
pygst.require('0.10')
import gst

import library
#import rawtty

Element = gst.element_factory_make
def Bin(*elements):
	bin = gst.Bin()
	if len(elements):
		bin.add(*elements)
		if len(elements)-1:
			gst.element_link_many(*elements)
		for t,d,i in (('sinks',gst.PAD_SINK,0),('srcs',gst.PAD_SRC,-1)):
			j = 0
			for pad in elements[i].pads():
				if pad.props.direction == d:
					bin.add_pad(gst.GhostPad(t[:-1] + str(j), pad))
					j+=1
	return bin
	
def time_from_ns(ns):
	m,s = divmod(ns/gst.SECOND, 60)
	h,m = divmod(m,60)
	return '%d:%02d:%02d' % (h,m,s) if h else '%d:%02d' % (m,s)

from thread import BgThread
from network import NetThread
from console import ConsoleThread

class PlayThread(BgThread):
	def main(self, gui):
		while True:
			gui.update()
			time.sleep(0.1)
			
class MediaButtons(gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self)
		self.toolbar = gtk.Toolbar()
		self.toolbar.unset_flags(gtk.CAN_FOCUS)
		self.toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
		self.toolbar.set_show_arrow(False)
		
		self.widgets = {}
		for name,stock in (
			 ('previous',gtk.STOCK_MEDIA_PREVIOUS),
			 ('play-pause',gtk.STOCK_MEDIA_PLAY),
			 #('stop',gtk.STOCK_MEDIA_STOP),
			 ('next',gtk.STOCK_MEDIA_NEXT),):
			self.widgets[name] = gtk.ToolButton(stock)
			self.toolbar.insert(self.widgets[name], -1)
			self.widgets[name].get_child().unset_flags(gtk.CAN_FOCUS)
		
		self.position = gtk.Adjustment(step_incr=15*gst.SECOND,page_incr=60*gst.SECOND)
		self.slider = gtk.ToolItem()
		self.slider.set_expand(True)
		self.slider.add(gtk.HScale(self.position))
		self.slider.get_child().connect('format-value', self.format_time)
		self.slider.get_child().unset_flags(gtk.CAN_FOCUS)
		self.toolbar.insert(self.slider, -1)
		
		self.volume = gtk.ToolItem()
		self.volume.add(gtk.VolumeButton())
		self.volume.up = False
		self.volume.get_child().unset_flags(gtk.CAN_FOCUS)
		self.toolbar.insert(self.volume, -1)
		
		scale = self.volume.get_child().get_popup().get_child().get_child().get_children()[1]
		scale.connect('change-value', debug)
		
		#self.widgets['fullscreen'] = gtk.ToggleToolButton(gtk.STOCK_FULLSCREEN)
		#self.toolbar.insert(self.widgets['fullscreen'], -1)
		#self.widgets['fullscreen'].get_child().unset_flags(gtk.CAN_FOCUS)
		
		self.pack_start(self.toolbar, expand=True, fill=True)
		
	def connect(self, which, func, *extra):
		if which in ('play-pause','stop','previous','next','fullscreen'):
			self.widgets[which].connect('clicked', func, *extra)
		elif which == 'position':
			self.slider.get_child().connect('change-value', func, *extra)
		elif which == 'volume':
			self.volume.get_child().get_popup().get_child().get_child().get_children()[1].connect('change-value', func, *extra)
		else:
			gtk.VBox.connect(self, which, func, *extra)
			
	def format_time(self, w, v):
		pos, dur = self.position.get_value(), self.position.get_upper()
		if TIME_FORMAT == 'percent':
			return "%2d%%" % (100 * pos / dur)
		elif TIME_FORMAT == 'hms':
			return ' / '.join([time_from_ns(x) for x in (pos,dur)])
		
	def set_duration(self, dur):
		self.position.set_upper(float(dur))
		
	def set_position(self, pos):
		self.position.set_value(pos)
		
	def set_volume(self, vol):
		self.volume.get_child().set_value(vol)
		
class CommandMap(dict):
	def __call__(self, command, *args):
		func = dict.__getitem__(self, command)
		return func(*args)
		
class KeyMap(object):
	def __init__(self, config, commandmap, console, window):
		self.keys = dict((str(k).lower(),v) for k,v in config.items('KeyMap'))
		self.commandmap = commandmap
		self.console = console
		self.console.handler = self.interpret
		self.window = window
		self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
		self.window.set_flags(gtk.CAN_FOCUS)
		self.window.connect('key-press-event', lambda w,e:self.interpret(gtk.accelerator_name(e.keyval, e.state)))
		
	def add(self, key, cmd):
		self.keys[key] = cmd
		
	def interpret(self, key):
		try:
			return self.commandmap(self.keys[key.lower()])
		except KeyError:
			print 'No key binding for', key
			
class Sidebar(gtk.HPaned):
	def __init__(self, moviewindow):
		gtk.HPaned.__init__(self)
		self.menu = gtk.VBox()
		gtk.HPaned.pack1(self, self.menu)
		gtk.HPaned.pack2(self, moviewindow)
		gtk.HPaned.set_position(self, 200)
		
		self.tracklist_model = gtk.ListStore(str)
		self.tracklist = gtk.TreeView(self.tracklist_model)
		self.tracklist_model.append(('track 1',))
		self.tracklist.append_column(gtk.TreeViewColumn('Title', gtk.CellRendererText(), text=0))
		self.menu.pack_end(self.tracklist)
		
from playlist import Playlist

class Main(object):
	def __init__(self):
		self.lib = library.library(library.DEFAULT_PATH)
		self.configuration = ConfigParser.SafeConfigParser()
		self.configuration.read((
			os.path.join(os.curdir, 'mcp.conf'),
			'/home/ryan/Projects/mcp/mcp.conf',
		))
		
		def add_accel(gtkaccel, func, *args):
			key, mod = gtk.accelerator_parse(gtkaccel)
			debug(gtkaccel, key, mod, func.__name__, args)
			self.accelgroup.connect_group(key, mod, gtk.ACCEL_VISIBLE,
			  lambda g,w,k,m:(func(*args),))
		
		self.accelgroup = gtk.AccelGroup()
		add_accel('F11', self.toggle_fullscreen)
		add_accel('<Control>W', self.quit)
		
		self.movie_window = gtk.DrawingArea()
		vbox = gtk.VBox()
		
		self.console = ConsoleThread()
		self.commandmap = CommandMap({
			'fullscreen': self.toggle_fullscreen,
			'next': self.next,
			'play-pause': self.play_pause,
			'play': self.play,
			'pause': self.pause,
			'stop': self.stop,
			'previous': self.previous,
			'controls': self.toggle_controls,
			'forward-near': lambda:self.seek(15*gst.SECOND, False, False),
			'forward-far': lambda:self.seek(60*gst.SECOND, False, False),
			'beginning': lambda:self.seek(0, True, True),
			'end': lambda:self.seek(self.get_duration(), True, False),
			'back-near': lambda:self.seek(-15*gst.SECOND, False, False),
			'back-far': lambda:self.seek(-60*gst.SECOND, False, False),
			'volume-up': lambda:self.set_volume(.05, False),
			'volume-down': lambda:self.set_volume(-.05, False),
			'mute': lambda:self.set_volume(0, True),
			'menu': self.toggle_menu,
			'show-menu': self.show_menu,
			'hide-menu': self.hide_menu,
		})
		self.keymap = KeyMap(self.configuration, self.commandmap, self.console, vbox)
		
		self.console.start()
		
		self.win = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.win.add_accel_group(self.accelgroup)
		self.win.set_title('Video-Player')
		self.win.set_default_size(500, 400)
		self.win.connect('destroy', self.on_destroy)
		self.win.__fullscreen = False
		self.win.connect('window-state-event', self.on_window_state_event)
		self.win.add(vbox)
		
		self.buttons = MediaButtons()
		self.buttons.connect('play-pause', lambda b:self.play_pause())
		self.buttons.connect('next', lambda b:self.next())
		self.buttons.connect('previous', lambda b:self.previous())
		self.buttons.connect('position', lambda a,t,v:self.seek(v, absolute=True, percent=False))
		self.buttons.connect('volume', lambda b,s,v:self.set_volume(v))
		#self.buttons.connect('fullscreen', lambda b:self.fullscreen() if b.get_active() else self.unfullscreen())
		
		self.movie_window.add_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.movie_window.connect('button-press-event', self.on_movie_window_clicked)
		self.movie_window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(0,0,0))
		
		self.sidebar = Sidebar(self.movie_window)
		
		vbox.pack_start(self.sidebar, True, True)
		vbox.pack_start(self.buttons, False, False)
		self.win.show_all()
		
		self.player = gst.element_factory_make('playbin', 'player')
		
		self.taginject = Element('taginject')
		audio_sink = Element(self.configuration.get('Gstreamer', 'audio-plugin'))
		audio_bin = Bin(self.taginject, Element('rgvolume'), audio_sink)
		self.player.set_property('audio-sink', audio_bin)
		
		video_sink = Element(self.configuration.get('Gstreamer', 'video-plugin'))
		self.movie_window.connect('expose-event', self.on_expose_event, video_sink)
		video_sink.set_property('force-aspect-ratio', True)
		self.player.set_property('video-sink', video_sink)
		self.player.set_property('vis-plugin', Element(self.configuration.get('Gstreamer','vis-plugin')))
		
		self.playlist = Playlist()

		bus = self.player.get_bus()
		bus.add_signal_watch()
		bus.enable_sync_message_emission()
		bus.connect('message::eos', self.on_eos)
		bus.connect('message::error', self.on_error)
		bus.connect('message::state-changed', self.on_state_changed)
		
	def start(self):
		gtk.gdk.threads_init()
		
		NetThread(self.configuration, self.commandmap).start()
		PlayThread(self).start()
		
		self.buttons.set_volume(0.8)
		self.next()
		
		signal.signal(signal.SIGINT, lambda s,f: self.quit())
		gtk.main()
		
	def seek(self, new, absolute=True, percent=False):
		format = gst.FORMAT_PERCENT if percent else gst.FORMAT_TIME
		if not absolute:
			new = max(0, new + self.get_position(percent=percent))
		debug('seek', format, new, absolute, percent)
		self.player.seek_simple(format, gst.SEEK_FLAG_FLUSH, new)
			 
	def isplaying(self):
		return self.player.get_state()[1] == gst.STATE_PLAYING
			 
	def play_pause(self):
		if self.isplaying():
			self.pause()
		else:
			self.play()
		
	def play(self):
		debug('play')
		self.player.set_state('playing')
		self.player.get_property('video_sink').set_xwindow_id(self.movie_window.window.xid)
		
	def pause(self):
		debug('pause')
		self.player.set_state('paused')
		
	def stop(self):
		debug('stop')
		self.player.set_state('null')
		
	def show_controls(self):
		debug('show controls')
		self.buttons.show()
		
	def hide_controls(self):
		self.buttons.hide()
		
	def toggle_controls(self):
		if self.buttons.get_property('visible'):
			self.buttons.hide()
		else:
			self.buttons.show()
		
	def fullscreen(self):
		self.win.fullscreen()
		self.hide_controls()
		
	def unfullscreen(self):
		self.win.unfullscreen()
		self.show_controls()
		
	def toggle_fullscreen(self):
		if self.win.__fullscreen:
			self.unfullscreen()
		else:
			self.fullscreen()
			
	def show_menu(self):
		self.sidebar.menu.show()
		
	def hide_menu(self):
		self.sidebar.menu.hide()
		
	def toggle_menu(self):
		if self.sidebar.menu.get_property('visible'):
			self.hide_menu()
		else:
			self.show_menu()
			
	def get_volume(self):
		return self.player.get_property('volume')
		
	def set_volume(self, level, absolute=True):
		if not absolute:
			level = max(0, min(1, self.get_volume() + level))
		self.player.set_property('volume', level)
		
	def get_position(self, percent=False):
		try:
			return max(0, self.player.query_position(gst.FORMAT_PERCENT if percent else gst.FORMAT_TIME, None)[0])
		except gst.QueryError:
			return 0
		
	def get_duration(self):
		try:
			return max(0, self.player.query_duration(gst.FORMAT_TIME, None)[0])
		except gst.QueryError:
			return 0
		
	def previous(self):
		debug('previous')
		pos = self.get_position()
		self.stop()
		if pos < 3 * gst.SECOND:
			try:
				self.load(self.playlist.previous())
			except StopIteration:
				return
		self.play()
		
	def next(self):
		debug('next')
		self.stop()
		try:
			self.load(self.playlist.next())
		except StopIteration:
			return
		self.play()
			
	def load(self, uri):
		debug('load', uri)
		tags = self.lib[uri]._asdict()
		self.player.set_property('uri', uri)
		rgtags = 'replaygain-reference-level','replaygain-track-gain','replaygain-track-peak'
		self.taginject.props.tags = ','.join(['%s=%s' % (k,tags[k.replace('-','_')]) for k in rgtags])
		
	def quit(self):
		self.player.set_state('null')
		gtk.main_quit()
		
	def update(self):
		try:
			self.buttons.set_position(self.get_position())
			self.buttons.set_duration(self.get_duration())
			self.buttons.slider.queue_draw()
			self.buttons.set_volume(self.get_volume())
		finally:
			return True
			
	def on_movie_window_clicked(self, window, event):
		if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
			self.show_menu()
		elif event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
			self.toggle_fullscreen()
		
	def on_about_to_finish(self, player):
		debug('about to finish')
		self.load(self.playlist.next())
		
	def on_window_state_event(self, window, event):
		if event.changed_mask & gtk.gdk.WINDOW_STATE_FULLSCREEN:
			self.win.__fullscreen = bool(event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN)
		
	def on_expose_event(self, window, event, sink):
		sink.set_xwindow_id(window.window.xid)
		
	def on_state_changed(self, bus, message):
		old, new, pending = message.parse_state_changed()
		playing = (new == gst.STATE_PLAYING)
		self.buttons.widgets['play-pause'].set_stock_id(gtk.STOCK_MEDIA_PAUSE if playing else gtk.STOCK_MEDIA_PLAY)
		
	def on_tag(self, bus, message):
		for k in message.structure.keys():
			print k, '=', message.structure[k]
		
	def on_eos(self, bus, message):
		debug('eos')
		print threading.currentThread()
		self.next()
		
	def on_error(self, bus, message):
		self.stop()
		err, debug = message.parse_error()
		print "Error: %s" % err, debug
		
	def on_destroy(self, *args):
		self.quit()

