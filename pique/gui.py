#!/usr/bin/env python
#
# Copyright (c) 2010, Ryan Marquardt
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without 
# modification, are permitted provided that the following conditions are
# met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the project nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from common import *

import sys
import thread
import threading
import Queue
args, sys.argv = sys.argv, []

import pygtk
import gtk
import gobject

sys.argv = args

class VideoBox(PObject, gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self)
		
		self.movie_window = gtk.DrawingArea()
		self.movie_window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(0,0,0))
		self.movie_window.add_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.movie_window.add_events(gtk.gdk.KEY_PRESS_MASK)
		self.movie_window.set_flags(gtk.CAN_FOCUS)
		self.movie_window.grab_focus()
		self.movie_window.connect('key-press-event', self.on_keypress)
		self.movie_window.connect('button-press-event', self.on_button_press_event)
		
		self.previous = gtk.ToolButton(gtk.STOCK_MEDIA_PREVIOUS)
		self.previous.get_child().unset_flags(gtk.CAN_FOCUS)
		self.previous.connect('clicked', self.on_signal, 'previous')
		
		self.play_pause = gtk.ToolButton(gtk.STOCK_MEDIA_PLAY)
		self.play_pause.get_child().unset_flags(gtk.CAN_FOCUS)
		self.play_pause.connect('clicked', self.on_signal, 'play-pause')
		
		self.next = gtk.ToolButton(gtk.STOCK_MEDIA_NEXT)
		self.next.get_child().unset_flags(gtk.CAN_FOCUS)
		self.next.connect('clicked', self.on_signal, 'next')
		
		self.position = gtk.Adjustment(step_incr=Time.FromSec(15),page_incr=Time.FromSec(60))
		
		self.scale = gtk.HScale(self.position)
		self.scale.connect('format-value', self.on_format_time)
		self.scale.unset_flags(gtk.CAN_FOCUS)
		
		self.slider = gtk.ToolItem()
		self.slider.set_expand(True)
		self.slider.add(self.scale)
		self.slider.get_child().connect('change-value', self.on_slider)
		
		self.volume = gtk.ToolItem()
		self.volume.add(gtk.VolumeButton())
		self.volume.up = False
		self.volume.get_child().unset_flags(gtk.CAN_FOCUS)
		
		self.settingsmenu = gtk.ToolButton(gtk.STOCK_INDEX)
		self.settingsmenu.get_child().unset_flags(gtk.CAN_FOCUS)
		self.settingsmenu.get_child().connect('button-press-event', self.on_show_menu)
		
		self.buttons = gtk.Toolbar()
		self.buttons.unset_flags(gtk.CAN_FOCUS)
		self.buttons.set_orientation(gtk.ORIENTATION_HORIZONTAL)
		self.buttons.set_show_arrow(False)
		self.buttons.insert(self.previous, -1)
		self.buttons.insert(self.play_pause, -1)
		self.buttons.insert(self.next, -1)
		self.buttons.insert(self.slider, -1)
		self.buttons.insert(self.volume, -1)
		self.buttons.insert(self.settingsmenu, -1)
		
		self.tracklist_model = gtk.ListStore(str)
		self.tracklist = gtk.TreeView(self.tracklist_model)
		self.tracklist.unset_flags(gtk.CAN_FOCUS)
		tracks_col = gtk.TreeViewColumn('Playlist', gtk.CellRendererText(), text=0)
		tracks_col.set_property('sizing', gtk.TREE_VIEW_COLUMN_FIXED)
		self.tracklist.append_column(tracks_col)
		self.tracklist.set_property('fixed-height-mode', True)
		
		self.scrolled_tracklist = gtk.ScrolledWindow()
		self.scrolled_tracklist.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.scrolled_tracklist.add(self.tracklist)
		
		self.update_playlist(['track 1', 'track 2', 'track 3'])
		
		self.menu = gtk.Menu()
		self.append_menu('Toggle Sidebar', 'menu')
		self.append_menu('Fullscreen', 'fullscreen')
		self.append_menu('Quit', 'quit')
		
		self.sidebar = self.scrolled_tracklist
		
		self.panes = gtk.HPaned()
		self.panes.pack1(self.movie_window, shrink=False)
		self.panes.pack2(self.sidebar, resize=False)
		self.panes.set_position(300)
		
		gtk.VBox.add_events(self, gtk.gdk.BUTTON_PRESS_MASK)
		#gtk.VBox.pack_start(self, self.movie_window, True, True)
		gtk.VBox.pack_start(self, self.panes, True, True)
		gtk.VBox.pack_start(self, self.buttons, False, False)
		
	def append_menu(self, title, cmd):
		menuitem = gtk.MenuItem(title)
		menuitem.show()
		if hasattr(cmd, '__call__'):
			menuitem.connect('activate', cmd)
		else:
			menuitem.connect('activate', self.on_menu_clicked, cmd)
		self.menu.append(menuitem)
		return menuitem
		
	def update_playlist(self, entries):
		self.tracklist_model.clear()
		for e in entries:
			self.tracklist_model.append((e,))
		
	def on_show_menu(self, widget, event):
		self.popup_menu(event)
		return True
		
	def popup_menu(self, event):
		self.menu.popup(None, None, None, event.button, event.time)
		
	def popdown_menu(self):
		self.menu.popdown()
		
	def on_keypress(self, window, event):
		modifiers = gtk.gdk.SHIFT_MASK | gtk.gdk.CONTROL_MASK | gtk.gdk.MOD1_MASK
		accel = gtk.accelerator_name(event.keyval, event.state & modifiers)
		self.emit('keypress', accel)
		
	def on_menu_clicked(self, menu, cmd):
		self.emit('menu', cmd)
		
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
		self.play_pause.set_stock_id(
			gtk.STOCK_MEDIA_PAUSE if new == 'playing' else gtk.STOCK_MEDIA_PLAY
		)

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
			'Player': self.on_set_player,
			'Playlist': self.on_set_playlist,
			'Library': self.on_set_library,
			'KeyMap': self.on_set_keymap,
			'commandmap': self.on_set_commandmap,
		}
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		
		accelgroup = gtk.AccelGroup()
		connect_accel(accelgroup, 'F11', self.toggle_fullscreen)
		connect_accel(accelgroup, '<Control>W', self.destroy)
		
		self.__fullscreen = False
		
		self.videobox = VideoBox()
		self.videobox.connect('clicked', self.on_movie_window_clicked)
		self.videobox.connect('keypress', self.on_keypress)
		
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
			'show_menu':	self.show_menu,
			'hide_menu':	self.hide_menu,
		}
		
		self.playlist_format = '{0.track_number} - {0.title}'
	
	def on_set_player(self, player):
		self.player = player
		self.player.window = self.videobox.movie_window
		self.player.connect('state-changed', self.update_state)
		self.player.connect('update', self.update_time)
		self.stop = player.stop
		#self.connect('volume', player.set_volume)
		
	def on_set_playlist(self, playlist):
		self.playlist = playlist
		self.playlist.connect('changed', self.on_playlist_changed)
		
	def on_playlist_changed(self):
		self.videobox.update_playlist(self.playlist_format.format(self.lib[uri]) for uri in self.playlist.entries)
		
	def on_set_library(self, lib):
		self.lib = lib
		
	def on_set_keymap(self, keymap):
		self.keymap = keymap
		
	def on_keypress(self, accel):
		self.keymap.interpret(accel)
		
	def on_set_commandmap(self, commandmap):
		self.commandmap = commandmap
		self.quit = self.commandmap['quit']
		self.videobox.connect('play-pause', self.commandmap.async, 'play_pause')
		self.videobox.connect('next', self.commandmap.async, 'next')
		self.videobox.connect('previous', self.commandmap.async, 'previous')
		self.videobox.connect('position', lambda pos:self.commandmap.async('seek',pos/SECOND))
		self.videobox.connect('menu', self.on_menu_clicked)
		
	def update_time(self, pos, dur):
		self.videobox.update_time(pos, dur)
		
	def update_state(self, new):
		self.videobox.update_state(new)
		
	def start(self):
		gtk.gdk.threads_init()
		
	def destroy(self, window=None):
		self.stop()
		self.quit()
		
	def on_movie_window_clicked(self, window, event):
		debug(event.type, event.button)
		if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
			self.show_menu(event)
		elif event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
			self.toggle_fullscreen()
			
	def on_menu_clicked(self, command, args=(), kwargs={}):
		self.commandmap.async(command, *args, **kwargs)
	
	def on_window_state_event(self, window, event):
		if event.changed_mask & gtk.gdk.WINDOW_STATE_FULLSCREEN:
			self.__fullscreen = bool(event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN)
		
	def fullscreen(self):
		self.window.freeze_updates()
		gtk.Window.fullscreen(self)
		self.hide_controls()
		self.window.thaw_updates()
		
	def unfullscreen(self):
		self.window.freeze_updates()
		gtk.Window.unfullscreen(self)
		self.show_controls()
		self.window.thaw_updates()
		
	def toggle_fullscreen(self):
		'''fullscreen() -> None

Switch between windowed and fullscreen views.'''
		if self.__fullscreen:
			self.unfullscreen()
		else:
			self.fullscreen()
		
	def show_controls(self):
		self.videobox.buttons.show()
		
	def hide_controls(self):
		self.videobox.buttons.hide()
		
	def toggle_controls(self):
		'''controls() -> None

Toggle whether control bar is shown.'''
		if self.videobox.buttons.get_property('visible'):
			self.hide_controls()
		else:
			self.show_controls()
		
	def show_menu(self, event=None):
		'''show_menu() -> None

Show the menu.'''
		self.videobox.sidebar.show()
		
	def hide_menu(self):
		'''hide_menu() -> None

Hide the menu.'''
		self.videobox.sidebar.hide()
		
	def toggle_menu(self):
		'''menu() -> None

Toggle whether menu is shown.'''
		if self.videobox.sidebar.get_property('visible'):
			self.hide_menu()
		else:
			self.show_menu()
