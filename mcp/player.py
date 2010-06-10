import sys
args,sys.argv = sys.argv,[]

import pygst
pygst.require('0.10')
import gst
import gobject

sys.argv = args

import Queue
import threading
import time
import traceback

from common import *
from thread import BgThread

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

class Player(object):
	def __init__(self, config, lib, pl):
		self.lib = lib
		self.state_change_lock = threading.Lock()
		
		self.taginject = Element('taginject')
		audio_sink = Element(config.get('Gstreamer', 'audio-plugin'))
		self.audio_bin = Bin(self.taginject, Element('rgvolume'), audio_sink)
		
		self.video_sink = Element(config.get('Gstreamer', 'video-plugin'))
		self.video_sink.set_property('force-aspect-ratio', True)
		
		self.player = Element('playbin')
		self.player.set_property('audio-sink', self.audio_bin)
		self.player.set_property('video-sink', self.video_sink)
		self.player.set_property('vis-plugin', Element(config.get('Gstreamer','vis-plugin')))
		
		self.playlist = pl
		
		self._window = None
		self.bus.add_signal_watch()
		self.bus.enable_sync_message_emission()
		self.bus.connect('message::async-done', self.on_async_done)
		self.connect('error', self.on_private_error)
		
		self.last_update = ()
		self.last_error = None
		self.state_change_pending = threading.Lock()
		self.state_change_done = threading.Event()
		self.updatethread = PlayThread(self.emit_update, 0.1)
		
		self.commands = {
			'next':			self.next,
			'play-pause':	self.play_pause,
			'play':			self.play,
			'pause':		self.pause,
			'stop':			self.stop,
			'previous':		self.previous,
			'seek':			lambda pos:self.seek(pos*SECOND, False),
			'jump':			lambda pos:self.seek(pos*SECOND, True),
			'beginning':	lambda:self.seek(0, True),
			'end':			lambda:self.seek(self.player.get_duration(), True),
			'volume-up':	lambda:self.set_volume(.05, False),
			'volume-down':	lambda:self.set_volume(-.05, False),
			'mute':			lambda:self.set_volume(0, True),
		}

	def on_private_error(self, error):
		self.last_error = Error(*error)
		self.state_change_done.set()
		
	def on_async_done(self, bus, message):
		self.state_change_done.set()
		self.last_error = None
			
	def set_state(self, state):
		with self.state_change_pending:
			self.state_change_done.clear()
			result = self.player.set_state(state)
			debug('state change result =', result)
			if result != gst.STATE_CHANGE_SUCCESS:
				self.state_change_done.wait(TIMEOUT)
				if self.last_error:
					raise self.last_error
			
	def start(self):
		self.updatethread.start()
		try:
			self.next()
		except StopIteration:
			pass
		
	def quit(self):
		self.stop()
		
	def emit_update(self):
		try:
			pos, dur = self.get_position(), self.get_duration()
			if (pos,dur) != self.last_update:
				self.last_update = pos,dur
				struct = gst.structure_from_string('update,position=(gint64)%d,duration=(gint64)%d' % (pos,dur))
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
		if self._window is not None:
			self.video_sink.set_xwindow_id(self._window.window.xid)
			
	def on_state_changed(self, bus, message, callback, *args):
		_, new, _ = message.parse_state_changed()
		if new in StateMap:
			callback(StateMap[new], *args)
			
	def on_update(self, bus, message, cb):
		func, args, kwargs = cb
		pos = message.structure['position']
		dur = message.structure['duration']
		return func(pos, dur, *args, **kwargs)
		
	def on_error(self, bus, message, cb):
		func, args, kwargs = cb
		return func(message.parse_error(), *args, **kwargs)
		
	def connect(self, which, func, *args, **kwargs):
		debug('connecting', which, func, args, kwargs)
		if which == 'state-changed':
			self.bus.connect('message::state-changed', self.on_state_changed, func, *args)
		elif which == 'update':
			self.bus.connect('message::application', self.on_update, (func, args, kwargs))
		elif which == 'error':
			self.bus.connect('message::error', self.on_error, (func, args, kwargs))
		else:
			self.bus.connect('message::%s' % which, func, *args)
	
	def seek(self, new, absolute=True):
		if not absolute:
			new = max(0, new + self.get_position(percent=percent))
		debug('seek', new)
		self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, new)
	
	def isplaying(self):
		return self.player.get_state()[1] == gst.STATE_PLAYING
			
	def play_pause(self):
		if self.isplaying():
			self.pause()
		else:
			self.play()
		
	def play(self):
		debug('play')
		self.set_state('playing')
		self.refresh_xid()
		
	def pause(self):
		debug('pause')
		self.set_state('paused')
		
	def stop(self):
		debug('stop')
		self.set_state('null')
		
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
				self.playlist.previous()
			except StopIteration:
				return
		self.play()
		
	def next(self):
		debug('next')
		self.stop()
		try:
			self.playlist.next()
		except StopIteration:
			return
		self.play()
			
	def load(self, uri):
		debug('load', uri)
		tags = self.lib[uri]._asdict()
		self.player.set_property('uri', uri)
		rgtags = 'replaygain-reference-level','replaygain-track-gain','replaygain-track-peak'
		self.taginject.props.tags = ','.join(['%s=%s' % (k,tags[k.replace('-','_')]) for k in rgtags])
		
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
				elif msg.type & gst.MESSAGE_ERROR:
					raise Error(*msg.parse_error())
				elif not normalize and msg.type & gst.MESSAGE_ASYNC_DONE:
					break
				elif msg.type & gst.MESSAGE_TAG:
					taglist = msg.parse_tag()
					for k in taglist.keys():
						tags[k.replace('-','_')] = taglist[k]
			tags['duration'] = self.playbin.query_duration(gst.FORMAT_TIME, None)[0]
		finally:
			self.playbin.set_state('null')
			print tags
			return tags
