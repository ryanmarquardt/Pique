#!/usr/bin/env python

import base64
import hashlib
import hmac
import pickle
import random
import socket
import SocketServer
import time
import traceback
import xml.dom
import xml.dom.minidom

impl = xml.dom.getDOMImplementation()

from common import *

class BaseEncoder(object):
	def __init__(self, *args, **kwargs): pass
	def encode(self, data): return data
	def decode(self, data): return data

try:
	import zlib
except ImportError:
	zlib = None
else:
	class ZlibEncoder(BaseEncoder):
		def __init__(self, level=9): self.level = level
		def encode(self, data): return zlib.compress(data, self.level)
		def decode(self, data): return zlib.decompress(data)

try:
	import bz2
except ImportError:
	bz2 = None
else:
	class BZ2Encoder(BaseEncoder):
		def __init__(self, level=9): self.level = level
		def encode(self, data): return bz2.compress(data, self.level)
		def decode(self, data): return bz2.decompress(data)

class func_def(object):
	def __init__(self, name, *args, **kwargs):
		self.name, self.args, self.kwargs = str(name), list(args), dict(kwargs)
	def __eq__(a, b):
		return (a.name,a.args,a.kwargs) == (b.name,b.args,b.kwargs)
	def __str__(self):
		items = map(repr,self.args) + map(lambda i:'%s=%r'%i, self.kwargs.items())
		return '%s(%s)' % (self.name, ', '.join(items))
	def __repr__(self):
		items = map(repr,self.args) + map(lambda i:'%s=%r'%i, self.kwargs.items())
		return 'func_def(%r, %s)' % (self.name, ', '.join(items))

class Base64Encoder(BaseEncoder):
	def encode(self, data): return base64.b64encode(data)
	def decode(self, data): return base64.b64decode(data)
		
class AuthenticationError(Exception): pass
		
class HMacEncoder(BaseEncoder):
	def __init__(self, user='', key='', passmap=None, hash='sha1'):
		self.user = user
		self.key = key or passmap and passmap.get(user,None)
		self.passmap = passmap
		self.hash = hash
	def _data(self, doc):
		return ''.join(c.toxml() for c in doc.documentElement.childNodes)
	def _hash(self, key, data):
		return hmac.new(key, data, getattr(hashlib, self.hash)).hexdigest()
	def encode(self, doc):
		data = self._data(doc)
		if self.user and self.key:
			print 'Authenticating with user=%s and password=%s' % (self.user,self.key)
			doc.documentElement.setAttribute('hmac', self._hash(self.key, data))
			doc.documentElement.setAttribute('hash', self.hash)
			doc.documentElement.setAttribute('user', self.user)
		return doc
	def decode(self, doc):
		if doc.documentElement.hasAttribute('hmac'):
			e = doc.documentElement.getAttribute('hmac')
			user = doc.documentElement.getAttribute('user')
			hash = doc.documentElement.getAttribute('hash')
			key = self.passmap[user]
			print 'Verifying with user=%s and password=%s' % (user, key)
			if e != self._hash(key, self._data(doc)):
				raise AuthenticationError('Unable to authenticate message')
		return doc
		
class XMLToText(BaseEncoder):
	def encode(self, doc): return doc.toxml()
	def decode(self, data): return xml.dom.minidom.parseString(data)
		
class XMLEncoder(BaseEncoder):
	#iter -> xmldoc
	def format(self, obj): return pickle.dumps(obj)
	def unformat(self, data): return pickle.loads(str(data))
	def encode(self, (rootname, handle, typ, payload)):
		doc = impl.createDocument(None, rootname, None)
		node = doc.createElement(typ)
		node.setAttribute('handle', handle)
		fnode = doc.createTextNode(self.format(payload))
		node.appendChild(fnode)
		doc.documentElement.appendChild(node)
		return doc
	def decode(self, doc):
		node = doc.documentElement.firstChild
		return (str(node.getAttribute('handle')), node.nodeName,
		  self.unformat(node.firstChild.data))
		
class EncoderChain(object):
	def __init__(self, *encoders):
		self.encoders, self.decoders = [], []
		for e in encoders:
			self.add(e)
		
	def add(self, enc):
		if isinstance(enc, type): enc = enc()
		self.encoders.append(enc.encode)
		self.decoders.insert(0, enc.decode)
		
	def encode(self, data):
		for f in self.encoders:
			data = f(data)
		return data
		
	def decode(self, data):
		for f in self.decoders:
			data = f(data)
		return data

class RPC(EncoderChain):
	Caps = {
		'compression': {None: BaseEncoder},
	}
	if zlib: Caps['compression']['zlib'] = ZlibEncoder
	if bz2:  Caps['compression']['bz2'] = BZ2Encoder
	
	def __init__(self, compression='zlib', user='', password='', passmap=None, 
		  digest='sha1'):
		EncoderChain.__init__(self)
		self.add(XMLEncoder)
		self.add(HMacEncoder(user, password, passmap, digest))
		self.add(XMLToText)
		comp = self.Caps['compression'].get(compression)
		self.add(comp(level=9))
		self.add(Base64Encoder)
			
	def encode(self, *args):
		return EncoderChain.encode(self, args) + '\n'
		
	def decode(self, msg):
		return EncoderChain.decode(self, msg.strip())
		
	def make_request(self, func):
		handle = hashlib.md5('%08x' % random.getrandbits(32) + \
		  time.strftime('%Y%m%d%H%M%S',time.gmtime()) #+ repr(func)
		  ).hexdigest()
		return self.encode('request', handle, 'call', func)
		  
	def get_request(self, data):
		handle, typ, payload = self.decode(data)
		if typ == 'call':
			return handle, payload
		else:
			raise ValueError('Unknown request type: %r' % typ)
			
	def make_response(self, handle, typ, payload):
		return self.encode('response', handle, typ, payload)
		
	def get_response(self, data):
		handle, typ, payload = self.decode(data)
		if typ == 'return':
			return handle, payload
		elif typ == 'error':
			return handle, Exception(payload)
		else:
			raise ValueError('Unknown response type: %r' % typ)

class Client(object):
	def __init__(self, username='', password=''):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		#negotiate capabilities
		self.wfile = self.sock.makefile('wb')
		self.rfile = self.sock.makefile('rb')
		self.rpc = RPC(user=username, password=password)
		self.username = username
		self.password = password
		
	def connect(self, (host, port)):
		self.sock.connect((host, port))
		
	def close(self):
		self.sock.close()
	
	def __call__(self, f, *args, **kwargs):
		func = func_def(f, *args, **kwargs)
		request = self.rpc.make_request(func)
		self.wfile.write(request)
		self.wfile.flush()
		line = self.rfile.readline()
		if line:
			return self.rpc.get_response(line)
		else:
			raise EOFError
	call_quick = __call__

class RequestHandler(SocketServer.StreamRequestHandler):
	def debug(self, text):
		print 'Client %s:%s -' % self.client_address, text
		
	def setup(self):
		SocketServer.StreamRequestHandler.setup(self)
		self.rpc = RPC(passmap=self.server.passmap)
		
	def handle(self):
		self.debug('Connected')
		while True:
			line = self.rfile.readline().strip()
			if not line:
				break
			handle, func = self.rpc.get_request(line)
			ret,(t,v,tb) = capture(self.server.on_call,
			  (func.name, func.args, func.kwargs))
			if t:
				self.wfile.write(self.rpc.make_response(handle,
				  'error', ''.join(traceback.format_exception(t,v,tb))))
			else:
				self.wfile.write(self.rpc.make_response(handle,
				  'return', ret))
			self.wfile.flush()
		self.debug('Disconnected')
		
class Server(SocketServer.TCPServer):
	allow_reuse_address = True
	def __init__(self, address, passwords=None, handler=None):
		SocketServer.TCPServer.__init__(self, address, handler or RequestHandler)
		self.passmap = passwords or {}

class ThreadingServer(SocketServer.ThreadingMixIn, Server): pass

if __name__=='__main__':
	import StringIO
	import sys

	HOST, PORT = "localhost", 9999
	if len(sys.argv) == 1:
		def a(b, c, genre=None):
			return 789, b, c, genre
		server = Server((HOST, PORT), {'print':sys.stdout.write})
		server.register('a', a)
		try:
			server.serve_forever()
		except KeyboardInterrupt:
			pass
	elif sys.argv[1] == 'client':
		client = Client()
		client.connect((HOST, PORT))
		print repr(client.call_quick('a', 123, '456', genre='jazz'))
		print repr(client.call_quick('a', '456', 'apple', genre='classical'))
	elif sys.argv[1] == 'unittest':
		tests = [
			func_def('testa', [{0:u'0'}, 1,'2<int/>',(3.0,{True:5, '6':complex(1,2.5), False:None})]),
			func_def('testb', ['a', 'b', 'c'], key='123'),
		]
		responses = [
			('return', (909,'909')),
			('error', TypeError()),
		]
		user = ''
		user = 'admin'
		password = 'testpa55w0rd'
		
		passmap = {user: password}
		print repr(tests)
		
		request = Request(user=user, password=password)
		for test in tests:
			request.append(test)
		sent = request.encode()
		print 'SEND:', repr(sent)
		
		rcvd = Request(passmap=passmap).decode(sent)
		response = Response()
		results = []
		print '  Received request:'
		for i,(handle, result) in enumerate(rcvd):
			results.append(result)
			print i, repr(result)
			response.append(handle, *responses[i])
		print
		assert tests == results
		
		sent = response.encode()
		print repr(sent)
		rcvd = Response().decode(sent)
		print '  Received response:'
		for i,(handle, payload) in enumerate(rcvd):
			if responses[i][0] == 'return':
				assert responses[i][1] == payload
				print i, payload
			elif responses[i][0] == 'error':
				assert `responses[i][1]` == `payload.args[0]`
				print i, 'Error:', `payload.args[0]`
			else:
				raise ValueError('Unknown response type: %r' % responses[i][0])
