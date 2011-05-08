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
import sys
args,sys.argv = sys.argv,[]

import pygst
pygst.require('0.10')
import gst
import gobject

sys.argv = args

import datetime
import Queue
import threading
import time
import traceback

from common import *
from bgthread import BgThread

TIMEOUT = 3

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
	
class Error(Exception):
	def __init__(self, error, dbg):
		debug('Error', error.code, error.domain, repr(error.message), repr(dbg))
		if error.domain == 'gst-resource-error-quark':
			if error.code == 3:
				Exception.__init__(self, error.message)
				return
		Exception.__init__(self, error.code, error.domain, error.message, dbg)
	
class PlayThread(BgThread):
	def main(self, update, frequency=0.1):
		while True:
			update()
			time.sleep(frequency)

STATE_PLAYING = 'playing'
STATE_PAUSED = 'paused'
STATE_STOPPED = 'stopped'
StateMap = {
	gst.STATE_PLAYING: STATE_PLAYING,
	gst.STATE_PAUSED: STATE_PAUSED,
	gst.STATE_NULL: STATE_STOPPED
}

class Player(PObject):
	def __init__(self, confitems):
		self.dependencies = {
			'Library':self.on_set_library,
			'Playlist':self.on_set_playlist,
			'JobsManager':self.on_set_jobsmanager,
		}
		config = dict(confitems)
		self.state_change_lock = threading.Lock()
		
		self.taginject = Element('taginject')
		audio_sink = Element(config.get('audio-plugin','gconfaudiosink'))
		self.audio_bin = Bin(self.taginject, Element('rganalysis'), Element('rgvolume'), audio_sink)
		
		self.video_sink = Element(config.get('video-plugin','gconfvideosink'))
		self.video_sink.set_property('force-aspect-ratio', True)
		
		self.player = Element('playbin')
		self.player.set_property('audio-sink', self.audio_bin)
		self.player.set_property('video-sink', self.video_sink)
		self.player.set_property('vis-plugin', Element(config.get('vis-plugin','fakesink')))
		
		self._window = None
		self.bus.add_signal_watch()
		self.bus.enable_sync_message_emission()
		self.bus.connect('message::async-done', self.on_async_done)
		self.bus.connect('message::state-changed', self.on_state_changed)
		self.bus.connect('message::error', self.on_error)
		self.bus.connect('message::eos', self.on_eos)
		self.bus.connect('message::tag', self.on_tag)
		self.connect('error', self.on_private_error)
		
		self.last_update = ()
		self.last_error = None
		self.state_change_pending = threading.Lock()
		self.state_change_done = threading.Event()
		self.updatethread = PlayThread(lambda:self.emit('update', self.get_position(), self.get_duration()), 0.1)
		
		self.tagger = tag_reader()
		
		self.commands = {
			'next':			self.next,
			'play_pause':	self.play_pause,
			'play':			self.play,
			'pause':		self.pause,
			'stop':			self.stop,
			'previous':		self.previous,
			'seek':			self.seek,
			'set_volume':	self.set_volume,
			'get_volume':	self.get_volume,
			'volume_up':	self.volume_up,
			'volume_down':	self.volume_down,
			'mute':			self.mute,
			'status':		self.status,
		}
		
	def on_set_library(self, library):
		self.lib = library
	
	def on_set_playlist(self, playlist):
		self.playlist = playlist
		self.playlist.connect('changed', self.on_playlist_changed)
		self.playlist.connect('new-uri-available', self.on_playlist_new_uri)
			
	def on_set_jobsmanager(self, jobsmanager):
		self.jobsmanager = jobsmanager
			
	def on_playlist_changed(self):
		debug('playlist changed')
		if not self.isplaying():
			self.next()
			
	def on_tag(self, bus, message):
		taglist = message.parse_tag()
		uri = self.player.get_property('uri')
		tags = dict((k.replace('-','_'),convert(taglist[k])) for k in taglist.keys())
		self.emit('new-tags', uri, tags)
			
	def on_playlist_new_uri(self, uri):
		self.load(uri)
			
	def on_private_error(self, error):
		debug('State Change Error')
		self.last_error = Error(*error)
		self.state_change_done.set()
		
	def on_async_done(self, bus, message):
		debug('State Change Finished')
		self.state_change_done.set()
		self.last_error = None
			
	def on_state_changed(self, bus, message):
		_, new, _ = message.parse_state_changed()
		if new in StateMap:
			self.emit('state-changed', StateMap[new])
			
	def on_error(self, bus, message):
		self.emit('error', message.parse_error())
		
	def on_eos(self, bus, message):
		self.emit('eos')
		
	def set_state(self, state):
		with self.state_change_pending:
			self.state_change_done.clear()
			result = self.player.set_state(state)
			debug('state change result =', result)
			if result != gst.STATE_CHANGE_SUCCESS:
				if self.state_change_done.wait(TIMEOUT):
					debug('State Change Timed Out')
				if self.last_error:
					raise self.last_error
			
	def start(self):
		self.updatethread.start()
		
	def quit(self):
		self.stop()
	
	@property
	def bus(self):
		return self.player.get_bus()
		
	@property
	def window(self):
		return self._window
	@window.setter
	def window(self, w):
		if self._window is not None:
			for h in self._window_handlers:
				self._window.disconnect(h)
		self._window = w
		self._window_handlers = (
			self._window.connect('expose-event', self.refresh_xid),
			self._window.connect('configure-event', self.refresh_xid),
		)
		
	def refresh_xid(self, widget=None, event=None):
		if self._window is not None:
			self.video_sink.set_xwindow_id(self._window.window.xid)
		
	def seek(self, new, absolute=True):
		'''seek(new_position, absolute=True) -> None

Move playback to a different point. If absolute is True, new_position is the
location to continue playback. If absolute is False, new_position is the
number of seconds forward or backward to move.'''
		new *= SECOND
		if not absolute:
			new = max(0, new + self.get_position())
		debug('seek', new)
		self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, new)
		
	def status(self):
		'''status() -> Dict

Returns the current playing state.'''
		return {
			'state':StateMap[self.player.get_state()[0]],
			'position':self.get_position() / SECOND,
			'duration':self.get_duration() / SECOND,
			'current_track':self.player.get_property('uri'),
		}
	
	def isplaying(self):
		return self.player.get_state()[1] == gst.STATE_PLAYING
			
	def play_pause(self):
		'''play_pause() -> None

Toggle player state between playing and paused.'''
		if self.isplaying():
			self.pause()
		else:
			self.play()
		
	def play(self):
		'''play() -> None

Start playback.'''
		debug('play')
		self.set_state('playing')
		
	def pause(self):
		'''pause() -> None

Pause playback.'''
		debug('pause')
		self.set_state('paused')
		
	def stop(self):
		'''stop() -> None

Stop playback.'''
		debug('stop')
		self.set_state('null')
		
	def get_volume(self):
		'''get_volume() -> Number

Returns the player's current volume, a number between 0 and 1.'''
		return self.player.get_property('volume')
		
	def set_volume(self, level, absolute=True):
		'''set_volume(level, absolute=True) -> None

Change the player volume. If absolute is True, volume is set to level. If
absolute is False, level is added to the volume. level is a number between 0 and
1.'''
		if not absolute:
			level = max(0, min(1, self.get_volume() + level))
		self.player.set_property('volume', level)
		
	def volume_up(self):
		'''volume_up() -> None

Raises the volume by 5%.'''
		self.set_volume(.05, False)
		
	def volume_down(self):
		'''volume_down() -> None

Lowers the volume by 5%.'''
		self.set_volume(-.05, False)
		
	def mute(self):
		'''mute() -> None

Sets the volume to 0'''
		self.set_volume(0, True)
		
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
		'''previous() -> None

Move playback to the beginning of the track, or to the previous track in the
playlist.'''
		debug('previous')
		pos = self.get_position()
		self.stop()
		if pos < 3 * gst.SECOND:
			try:
				self.playlist.previous()
			except StopIteration:
				return
		self.play()
		
	def next(self):
		'''next() -> None

Move playback to the next item in the playlist.'''
		debug('next')
		self.stop()
		try:
			self.playlist.next()
		except StopIteration:
			return
		self.play()
			
	def load(self, uri):
		debug('load', uri)
		tags = self.lib[uri]
		self.player.set_property('uri', uri)
		rgtags = 'replaygain_reference_level','replaygain_track_gain','replaygain_track_peak'
		injected = ','.join(['%s=%s' % (k.replace('_','-'),tags[k]) for k in rgtags if tags[k]])
		debug('Injecting tags', injected)
		self.taginject.props.tags = injected
		self.refresh_xid()
		
	def scan_uri(self, uri):
		tags = self.tagger(uri, normalize=False)
		self.emit('new-tags', uri, tags)
		
	def normalize_uri(self, uri):
		tags = self.tagger(uri, normalize=True)
		self.emit('new-tags', uri, tags)
		
def gsub(func):
	main = gobject.MainLoop()
	q = Queue.Queue()
	def f(args,kwargs):
		try:
			r = func(*args, **kwargs)
		except Exception, e:
			q.put(e)
		else:
			q.put(r)
		finally:
			main.quit()
	def g(*args, **kwargs):
		gobject.idle_add(f, args, kwargs)
		main.run()
		r = q.get()
		if isinstance(r, Exception):
			raise r
		else:
			return r
	return g

def convert(obj):
	if hasattrs(obj, ['year','month','day']):
		return datetime.datetime(obj.year,obj.month,obj.day)
	else:
		return obj

class tag_reader(object):
	def __init__(self):
		self.playbin = Element('playbin')
		self.playbin.set_property('audio-sink', Bin(Element('rganalysis'), Element('fakesink')))
		self.playbin.set_property('video-sink', Element('fakesink'))
		
	def on_update(self):
		sys.stdout.write('.')
		sys.stdout.flush()
		
	@gsub
	def __call__(self, uri, update_callback=None, update_frequency=1, normalize=True):
		try:
			self.playbin.set_property('uri', uri)
			tags = {}
			self.playbin.set_state('playing')
			bus = self.playbin.get_bus()
			while True:
				msg = bus.poll(gst.MESSAGE_ANY, update_frequency*gst.SECOND)
				if msg is None:
					if update_callback:
						update_callback()
					continue
				elif msg.type & gst.MESSAGE_EOS:
					break
				elif not normalize and msg.type & gst.MESSAGE_ASYNC_DONE:
					break
				elif msg.type & gst.MESSAGE_ERROR:
					raise Error(*msg.parse_error())
				elif msg.type & gst.MESSAGE_TAG:
					taglist = msg.parse_tag()
					for k in taglist.keys():
						k,v = k.replace('-','_'),convert(taglist[k])
						tags[k] = v
			tags['duration'] = self.playbin.query_duration(gst.FORMAT_TIME, None)[0]
		except Exception, e:
			raise e
		finally:
			self.playbin.set_state('null')
		return tags
