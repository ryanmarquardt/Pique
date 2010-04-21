import ConfigParser
import os
import signal
import sys
import threading
import time
import traceback

import pygtk, gtk, gobject
import pygst
pygst.require('0.10')
import gst

import library

from common import *
TIME_FORMAT = 'hms'

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
	
class Time(long):
	@classmethod
	def from_ns(cls, ns):
		return Time(ns)
		
	@classmethod
	def from_s(cls, s):
		return Time(s*gst.SECOND)
		
	def __repr__(self):
		return self.format('s.')
		
	def __str__(self):
		return self.format('hms')
		
	def format(self, f):
		if f == 'hms':
			m,s = divmod(self/gst.SECOND, 60)
			h,m = divmod(m,60)
			return '%d:%02d:%02d' % (h,m,s) if h else '%d:%02d' % (m,s)
		elif f == 's.':
			return '%f' % (self / float(gst.SECOND))
			
class Toggle(object):
	def __init__(self, get, set, unset):
		self.__nonzero__ = get
		self.set = set
		self.unset = unset
	
	def switch(self):
		if self:
			self.unset()
		else:
			self.set()
		
from thread import BgThread
from network import NetThread
from console import ConsoleThread

class PlayThread(BgThread):
	def main(self, update):
		while True:
			update()
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
			return '%s / %s' % (Time(pos),Time(dur))
		
	def set_duration(self, dur):
		self.position.set_upper(float(dur))
		
	def set_position(self, pos):
		self.position.set_value(pos)
		
	def set_volume(self, vol):
		self.volume.get_child().set_value(vol)
		
class KeyMap(object):
	def __init__(self, config, commandmap):
		self.keys = dict((str(k).lower(),v) for k,v in config.items('KeyMap'))
		self.commandmap = commandmap
		
	def setup_console(self, console):
		console.handler = self.interpret
		
	def setup_gtk_window(self, window):
		window.add_events(gtk.gdk.KEY_PRESS_MASK)
		window.set_flags(gtk.CAN_FOCUS)
		window.connect('key-press-event', lambda w,e:self.interpret(gtk.accelerator_name(e.keyval, e.state)))
		
	def add(self, key, cmd):
		self.keys[key] = cmd
		
	def interpret(self, key):
		try:
			func = self.commandmap[self.keys[key.lower()]]
			return func()
		except KeyError:
			debug('No key binding for', key)
			
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

class VideoBox(gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self)
		self.movie_window = gtk.DrawingArea()
		
		self.buttons = MediaButtons()
		
		self.movie_window.add_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.movie_window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(0,0,0))
		
		self.sidebar = Sidebar(self.movie_window)
		
		gtk.VBox.pack_start(self, self.sidebar, True, True)
		gtk.VBox.pack_start(self, self.buttons, False, False)
		
		self.controls_visible = Toggle(
			lambda:self.buttons.get_property('visible'),
			self.buttons.show,
			self.buttons.hide
		)
		self.menu_visible = Toggle(
			lambda:self.sidebar.menu.get_property('visible'),
			self.sidebar.menu.show,
			self.sidebar.menu.hide
		)
		
		
	def connect(self, which, *args):
		if which in ('play-pause','next','previous', 'position', 'volume'):
			self.buttons.connect(which, *args)
		elif which == 'xid-request':
			self.movie_window.connect('expose-event', *args)
		elif which == 'clicked':
			self.movie_window.connect('button-press-event', *args)
		
	def update(self, bus, message):
		debug('update', message.structure.to_string())
		struct = message.structure
		try:
			self.buttons.set_position(struct['position'])
			self.buttons.set_duration(struct['duration'])
			self.buttons.slider.queue_draw()
		except:
			traceback.print_exc()
		finally:
			return True
			
class GUI(gtk.Window):
	def __init__(self):
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		
		self.accelgroup = gtk.AccelGroup()
		self.add_accel('F11', self.toggle_fullscreen)
		self.add_accel('<Control>W', self.destroy)
		gtk.Window.add_accel_group(self, self.accelgroup)
		
		gtk.Window.set_title(self, 'Video-Player')
		gtk.Window.set_default_size(self, 500, 400)
		self.__fullscreen = False
		gtk.Window.connect(self, 'window-state-event', self.on_window_state_event)
		
		self.videobox = VideoBox()
		gtk.Window.add(self, self.videobox)
		gtk.Window.show_all(self)
		
	def connect(self, which, *args):
		if which in ('clicked', 'play-pause', 'next', 'previous', 'position', 'volume', 'xid-request'):
			self.videobox.connect(which, *args)
		else:
			gtk.Window.connect(self, which, *args)
		
	def add_accel(self, gtkaccel, func):
		key, mod = gtk.accelerator_parse(gtkaccel)
		debug(gtkaccel, key, mod, func.__name__)
		self.accelgroup.connect_group(key, mod, gtk.ACCEL_VISIBLE,
		  lambda g,w,k,m:(func(),))
	
	def on_window_state_event(self, window, event):
		if event.changed_mask & gtk.gdk.WINDOW_STATE_FULLSCREEN:
			self.__fullscreen = bool(event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN)
		
	def on_state_changed(self, bus, message):
		old, new, pending = message.parse_state_changed()
		playing = (new == gst.STATE_PLAYING)
		self.videobox.buttons.widgets['play-pause'].set_stock_id(gtk.STOCK_MEDIA_PAUSE if playing else gtk.STOCK_MEDIA_PLAY)
		
	def fullscreen(self):
		gtk.Window.fullscreen(self)
		self.hide_controls()
		
	def unfullscreen(self):
		gtk.Window.unfullscreen(self)
		self.show_controls()
		
	def toggle_fullscreen(self):
		if self.__fullscreen:
			self.unfullscreen()
		else:
			self.fullscreen()
		
	def show_controls(self):
		self.videobox.controls_visible.set()
		
	def hide_controls(self):
		self.videobox.controls_visible.unset()
		
	def toggle_controls(self):
		self.videobox.controls_visible.switch()
		
	def show_menu(self):
		self.videobox.menu_visible.set()
		
	def hide_menu(self):
		self.videobox.menu_visible.unset()
		
	def toggle_menu(self):
		self.videobox.menu_visible.switch()
		
class Player(object):
	def __init__(self, config, lib):
		self.lib = lib
		
		self.taginject = Element('taginject')
		audio_sink = Element(config.get('Gstreamer', 'audio-plugin'))
		self.audio_bin = Bin(self.taginject, Element('rgvolume'), audio_sink)
		
		self.video_sink = Element(config.get('Gstreamer', 'video-plugin'))
		self.video_sink.set_property('force-aspect-ratio', True)
		
		self.player = Element('playbin')
		self.player.set_property('audio-sink', self.audio_bin)
		self.player.set_property('video-sink', self.video_sink)
		self.player.set_property('vis-plugin', Element(config.get('Gstreamer','vis-plugin')))
		
		self.playlist = Playlist()
		
		self._window = None
		self.bus.add_signal_watch()
		self.bus.enable_sync_message_emission()
		
		self.last_update = ()
		self.updatethread = PlayThread(self.emit_update)
		self.updatethread.start()
		
	def emit_update(self):
		try:
			pos, dur = self.get_position(), self.get_duration()
			if (pos,dur) != self.last_update:
				self.last_update = pos,dur
				debug(pos, dur)
				struct = gst.structure_from_string('update,position=%d,duration=%d' % (pos,dur))
				m = gst.message_new_custom(gst.MESSAGE_APPLICATION, self.player, struct)
				self.bus.post(m)
		except:
			traceback.print_exc()
		
	@property
	def bus(self):
		return self.player.get_bus()
		
	@property
	def window(self):
		return self._window
	@window.setter
	def window(self, w):
		if self._window is not None:
			self._window.disconnect(self._window_handler)
		self._window = w
		self._window_handler = self._window.connect('expose-event', self.refresh_xid)
		
	def refresh_xid(self, widget=None, event=None):
		self.video_sink.set_xwindow_id(self._window.window.xid)
		
	def connect(self, which, *args):
		debug('player.connect', which, args)
		self.bus.connect('message::%s' % which, *args)
	
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
		self.refresh_xid()
		
	def pause(self):
		debug('pause')
		self.player.set_state('paused')
		
	def stop(self):
		debug('stop')
		self.player.set_state('null')
		
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
		

class Main(object):
	def __init__(self):
		self.lib = library.library(library.DEFAULT_PATH)
		self.configuration = ConfigParser.SafeConfigParser()
		self.configuration.read((
			os.path.join(os.curdir, 'mcp.conf'),
			'/home/ryan/Projects/mcp/mcp.conf',
		))
		
		self.player = Player(self.configuration, self.lib)
		self.gui = GUI()
		
		self.commandmap = {
			'fullscreen': self.gui.toggle_fullscreen,
			'next': self.player.next,
			'play-pause': self.player.play_pause,
			'play': self.player.play,
			'pause': self.player.pause,
			'stop': self.player.stop,
			'previous': self.player.previous,
			'controls': self.gui.toggle_controls,
			'forward-near': lambda:self.player.seek(15*gst.SECOND, False, False),
			'forward-far': lambda:self.player.seek(60*gst.SECOND, False, False),
			'beginning': lambda:self.player.seek(0, True, True),
			'end': lambda:self.player.seek(self.player.get_duration(), True, False),
			'back-near': lambda:self.player.seek(-15*gst.SECOND, False, False),
			'back-far': lambda:self.player.seek(-60*gst.SECOND, False, False),
			'volume-up': lambda:self.player.set_volume(.05, False),
			'volume-down': lambda:self.player.set_volume(-.05, False),
			'mute': lambda:self.player.set_volume(0, True),
			'menu': self.gui.toggle_menu,
			'show-menu': self.gui.show_menu,
			'hide-menu': self.gui.hide_menu,
		}
		
		self.gui.connect('play-pause', lambda b:self.player.play_pause())
		self.gui.connect('next', lambda b:self.player.next())
		self.gui.connect('previous', lambda b:self.player.previous())
		self.gui.connect('position', lambda a,t,v:self.player.seek(v, absolute=True, percent=False))
		self.gui.connect('volume', lambda b,s,v:self.player.set_volume(v))
		self.gui.connect('destroy', self.on_destroy)
		self.gui.connect('clicked', self.on_movie_window_clicked)
		#self.gui.connect('xid-request', self.gui.on_xid_request, self.player.video_sink)
		self.player.window = self.gui.videobox.movie_window
		self.player.connect('eos', self.on_eos)
		self.player.connect('error', self.on_error)
		self.player.connect('state-changed', self.gui.on_state_changed)
		self.player.connect('application', self.gui.videobox.update)
		
		self.console = ConsoleThread()
		self.keymap = KeyMap(self.configuration, self.commandmap)
		self.keymap.setup_console(self.console)
		self.keymap.setup_gtk_window(self.gui.videobox)
		
		self.server = NetThread(self.configuration, self.commandmap)
		
	def start(self):
		gtk.gdk.threads_init()
		
		self.server.start()
		self.console.start()
		
		self.player.next()
		
		signal.signal(signal.SIGINT, lambda s,f: self.quit())
		gtk.main()
		
	def quit(self):
		self.player.stop()
		gtk.main_quit()
		
	def on_movie_window_clicked(self, window, event):
		if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
			self.show_menu()
		elif event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
			self.toggle_fullscreen()
		
	def on_eos(self, bus, message):
		debug('eos')
		self.next()
		
	def on_error(self, bus, message):
		self.stop()
		err, debug = message.parse_error()
		print "Error: %s" % err, debug
		
	def on_destroy(self, *args):
		self.quit()
		

