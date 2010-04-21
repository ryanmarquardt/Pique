import ConfigParser
import os
import signal
import sys

import pygtk
import gtk
import gobject

from common import *
from library import library, uri
from library import DEFAULT_PATH as LIB_DEFAULT_PATH
from network import NetThread
from console import ConsoleThread
from player import Player

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
		
		self.position = gtk.Adjustment(step_incr=15*SECOND,page_incr=60*SECOND)
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
		
		self.controls_visible = Toggle(lambda:self.buttons.get_property('visible'),
		  self.buttons.show, self.buttons.hide)
		self.menu_visible = Toggle(lambda:self.sidebar.menu.get_property('visible'),
		  self.sidebar.menu.show, self.sidebar.menu.hide)
		
		
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
		playing = (new == 'playing')
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
		

class Main(object):
	def __init__(self):
		self.lib = library(LIB_DEFAULT_PATH)
		self.configuration = ConfigParser.SafeConfigParser()
		self.configuration.read((
			os.path.join(os.curdir, 'mcp.conf'),
			'/home/ryan/Projects/mcp/mcp.conf',
		))
		self.playlist = Playlist()
		self.player = Player(self.configuration, self.lib, self.playlist)
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
			'forward-near': lambda:self.player.seek(15*SECOND, False, False),
			'forward-far': lambda:self.player.seek(60*SECOND, False, False),
			'beginning': lambda:self.player.seek(0, True, True),
			'end': lambda:self.player.seek(self.player.get_duration(), True, False),
			'back-near': lambda:self.player.seek(-15*SECOND, False, False),
			'back-far': lambda:self.player.seek(-60*SECOND, False, False),
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
		

