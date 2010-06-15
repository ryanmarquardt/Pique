import thread

from common import *
import sys
args, sys.argv = sys.argv, []

import pygtk
import gtk
import gobject

sys.argv = args

class VideoBox(PObject, gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self)
		PObject.__init__(self)
		
		self.movie_window = gtk.DrawingArea()
		self.movie_window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(0,0,0))
		
		self.previous = gtk.ToolButton(gtk.STOCK_MEDIA_PREVIOUS)
		self.previous.get_child().unset_flags(gtk.CAN_FOCUS)
		
		self.play_pause = gtk.ToolButton(gtk.STOCK_MEDIA_PLAY)
		self.play_pause.get_child().unset_flags(gtk.CAN_FOCUS)
		
		self.next = gtk.ToolButton(gtk.STOCK_MEDIA_NEXT)
		self.next.get_child().unset_flags(gtk.CAN_FOCUS)
		
		self.position = gtk.Adjustment(step_incr=Time.FromSec(15),page_incr=Time.FromSec(60))
		
		self.scale = gtk.HScale(self.position)
		self.scale.connect('format-value', self.on_format_time)
		self.scale.unset_flags(gtk.CAN_FOCUS)
		
		self.slider = gtk.ToolItem()
		self.slider.set_expand(True)
		self.slider.add(self.scale)
		
		self.volume = gtk.ToolItem()
		self.volume.add(gtk.VolumeButton())
		self.volume.up = False
		self.volume.get_child().unset_flags(gtk.CAN_FOCUS)
		
		self.buttons = gtk.Toolbar()
		self.buttons.unset_flags(gtk.CAN_FOCUS)
		self.buttons.set_orientation(gtk.ORIENTATION_HORIZONTAL)
		self.buttons.set_show_arrow(False)
		self.buttons.insert(self.previous, -1)
		self.buttons.insert(self.play_pause, -1)
		self.buttons.insert(self.next, -1)
		self.buttons.insert(self.slider, -1)
		self.buttons.insert(self.volume, -1)
		
		self.tracklist_model = gtk.ListStore(str)
		self.tracklist = gtk.TreeView(self.tracklist_model)
		self.tracklist.unset_flags(gtk.CAN_FOCUS)
		self.tracklist_model.append(('track 1',))
		self.tracklist.append_column(gtk.TreeViewColumn('Title', gtk.CellRendererText(), text=0))
		
		self.menu = gtk.VBox()
		self.menu.pack_end(self.tracklist)
		
		#self.sidebar = gtk.HPaned()
		#self.sidebar.pack1(self.menu)
		#self.sidebar.pack2(self.movie_window)
		#self.sidebar.set_position(200)
		
		gtk.VBox.add_events(self, gtk.gdk.BUTTON_PRESS_MASK)
		gtk.VBox.pack_start(self, self.movie_window, True, True)
		gtk.VBox.pack_start(self, self.buttons, False, False)
		
		self.play_pause.connect('clicked', self.on_signal, 'play-pause')
		self.previous.connect('clicked', self.on_signal, 'previous')
		self.next.connect('clicked', self.on_signal, 'next')
		self.slider.get_child().connect('change-value', self.on_slider)
		self.slider.get_child().connect('scroll-event', debug)
		self.movie_window.connect('button-press-event', self.on_button_press_event)
		self.movie_window.connect('expose-event', self.on_signal, 'xid-request')
		
	def set_keymap(self, keymap):
		debug('GUI Set Keymap')
		self.movie_window.add_events(gtk.gdk.KEY_PRESS_MASK)
		self.movie_window.set_flags(gtk.CAN_FOCUS)
		self.movie_window.grab_focus()
		self.movie_window.connect('key-press-event', self.on_keypress)
		self.keymap = keymap
		
	def on_keypress(self, window, event):
		modifiers = gtk.gdk.SHIFT_MASK | gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK
		accel = gtk.accelerator_name(event.keyval, event.state & modifiers)
		thread.start_new_thread(self.keymap.interpret, (accel,))
		
	def on_button_press_event(self, window, event):
		self.emit('clicked', window, event)
		
	def on_signal(self, *args):
		self.emit(args[-1])

	def on_slider(self, range, scroll, value):
		self.emit('position', value)
		
	def on_format_time(self, w, v):
		pos, dur = self.position.get_value(), self.position.get_upper()
		if TIME_FORMAT == 'percent':
			return "%2d%%" % (100 * pos / dur)
		elif TIME_FORMAT == 'hms':
			return '%s / %s' % (Time(pos),Time(dur))
		
	def update_state(self, new):
		if new == 'playing':
			self.play_pause.set_stock_id(gtk.STOCK_MEDIA_PAUSE)
		else:
			self.play_pause.set_stock_id(gtk.STOCK_MEDIA_PLAY)

	def update_time(self, position, duration):
		try:
			self.position.set_value(position)
			self.position.set_upper(duration)
			self.slider.queue_draw()
		except:
			traceback.print_exc()
		finally:
			return True
	
def connect_accel(acg, name, func):
	k,m = gtk.accelerator_parse(name)
	acg.connect_group(k, m, gtk.ACCEL_VISIBLE, lambda g,w,k,m:func())
	
class GUI(gtk.Window):
	def __init__(self, confitems):
		self.dependencies = {
			'pique.player.Player': self.on_set_player,
			'pique.keymap.KeyMap': self.on_set_keymap,
			'commandmap': self.on_set_commandmap,
		}
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		
		accelgroup = gtk.AccelGroup()
		connect_accel(accelgroup, 'F11', self.toggle_fullscreen)
		connect_accel(accelgroup, '<Control>W', self.destroy)
		
		self.__fullscreen = False
		
		self.videobox = VideoBox()
		self.videobox.connect('clicked', self.on_movie_window_clicked)
		
		gtk.Window.add_accel_group(self, accelgroup)
		gtk.Window.set_title(self, 'Video-Player')
		gtk.Window.set_default_size(self, 500, 400)
		gtk.Window.connect(self, 'window-state-event', self.on_window_state_event)
		gtk.Window.connect(self, 'destroy', self.destroy)
		gtk.Window.add(self, self.videobox)
		gtk.Window.show_all(self)
		
		self.commands = {
			'fullscreen':	self.toggle_fullscreen,
			'menu':			self.toggle_menu,
			'controls':		self.toggle_controls,
			'show-menu':	self.show_menu,
			'hide-menu':	self.hide_menu,
		}
	
	def on_set_player(self, player):
		player.window = self.videobox.movie_window
		player.connect('state-changed', self.update_state)
		player.connect('update', self.update_time)
		self.videobox.connect('play-pause', thread.start_new_thread, player.play_pause, ())
		self.videobox.connect('next', thread.start_new_thread, player.next, ())
		self.videobox.connect('previous', thread.start_new_thread, player.previous, ())
		self.videobox.connect('position', lambda x:thread.start_new_thread(player.seek,(x,)))
		self.stop = player.stop
		#self.connect('volume', player.set_volume)
		
	def on_set_keymap(self, keymap):
		self.videobox.set_keymap(keymap)
		
	def on_set_commandmap(self, commandmap):
		self.quit = commandmap['quit']
		
	def update_time(self, pos, dur):
		self.videobox.update_time(pos, dur)
		
	def update_state(self, new):
		self.videobox.update_state(new)
		
	def start(self):
		gtk.gdk.threads_init()
		
	def destroy(self, window=None):
		self.stop()
		self.quit()
		
	def on_movie_window_clicked(self, event):
		if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
			self.show_menu()
		elif event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
			self.toggle_fullscreen()
	
	def on_window_state_event(self, window, event):
		if event.changed_mask & gtk.gdk.WINDOW_STATE_FULLSCREEN:
			self.__fullscreen = bool(event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN)
		
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
		self.videobox.buttons.show()
		
	def hide_controls(self):
		self.videobox.buttons.hide()
		
	def toggle_controls(self):
		if self.videobox.buttons.get_property('visible'):
			self.hide_controls()
		else:
			self.show_controls()
		
	def show_menu(self):
		self.videobox.menu.show()
		
	def hide_menu(self):
		self.videobox.menu.hide()
		
	def toggle_menu(self):
		if self.menu.get_property('visible'):
			self.hide_menu()
		else:
			self.show_menu()
