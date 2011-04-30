#!/usr/bin/env python

import base64
import hashlib
import random
import socket
import SocketServer
import time
import traceback
import xml.dom
import xml.dom.minidom

try:
	import zlib
except ImportError:
	zlib = None
try:
	import bz2
except ImportError:
	bz2 = None

impl = xml.dom.getDOMImplementation()

type_map = {
	bool:'bool', int:'int', long:'long', float:'float',
	complex:'complex',
	str:'str', unicode:'unicode', bytearray:'bytearray',
	list:'list', tuple:'tuple',
	dict:'dict', set:'set', frozenset:'frozenset',
	'bool':bool, 'int':int, 'long':long, 'float':float,
	'complex':complex,
	'str':str, 'unicode':unicode, 'bytearray':bytearray,
	'list':list, 'tuple':tuple,
	'dict':dict, 'set':set, 'frozenset':frozenset,
}

def get_type(obj):
	for t in obj.__class__.mro():
		if t in type_map:
			break
	return type_map[t]
	
def type_from_name(name):
	return type_map[name]
	
class func_def(object):
	def __init__(self, name, *args, **kwargs):
		self.name = str(name)
		self.args = list(args)
		self.kwargs = dict(kwargs)
		
	def __eq__(self, x):
		return (self.name,self.args,self.kwargs) == (x.name,x.args,x.kwargs)
		
	def __str__(self):
		items = map(repr,self.args) + map(lambda i:'%s=%r'%i, self.kwargs.items())
		return '%s(%s)' % (self.name, (', '.join(items)))
	__repr__ = __str__

def build_xmlobjtree(doc, obj):
	if obj is None: return doc.createElement('null')
	elif obj is True: return doc.createElement('true')
	elif obj is False: return doc.createElement('false')
	t = get_type(obj)
	node = doc.createElement(t)
	if t in ('list','tuple','set','frozenset'):
		for e in obj:
			node.appendChild(build_xmlobjtree(doc, e))
	elif t == 'dict':
		for k,v in obj.iteritems():
			item = doc.createElement('item')
			item.appendChild(build_xmlobjtree(doc, k))
			item.appendChild(build_xmlobjtree(doc, v))
			node.appendChild(item)
	else:
		node.appendChild(doc.createTextNode(unicode(obj)))
	return node
	
def eval_xmlobjtree(node):
	t = node.nodeName
	if t == 'null': return None
	elif t == 'true': return True
	elif t == 'false': return False
	t = type_from_name(t)
	if t in (list,tuple,set,frozenset):
		return t(eval_xmlobjtree(n) for n in node.childNodes if n.nodeType == n.ELEMENT_NODE)
	elif t == dict:
		return dict((eval_xmlobjtree(getFirstChildElement(n)),eval_xmlobjtree(getNextSiblingElement(getFirstChildElement(n)))) for n in node.childNodes if n.nodeType == n.ELEMENT_NODE)
	else:
		return t(node.firstChild.data)
	
class RPC(object):
	Caps = {
		'compression': [],
	}
	if zlib:
		Caps['compression'].append('zlib')
	if bz2:
		Caps['compression'].append('bz2')
	
	def __init__(self):
		self.doc = impl.createDocument(None, self._root_name, None)
		self.set_compression(None)
		self.set_compression('bz2')
		self.set_compression('zlib')
		
	def set_compression(self, which, level=9):
		if which == 'zlib':
			self.compress = lambda x:zlib.compress(x,level)
			self.decompress = zlib.decompress
		elif which == 'bz2':
			self.compress = lambda x:bz2.compress(x,level)
			self.decompress = bz2.decompress
		else:
			self.compress = lambda x:x
			self.decompress = lambda x:x
			
	def encode(self, data):
		return base64.b64encode(data)
		
	def decode(self, data):
		return base64.b64decode(data)
			
	def pack(self):
		return self.encode(self.compress(self.doc.toxml())) + '\n'
		
	@classmethod
	def from_packed_xml(cls, msg):
		msg = msg.strip()
		self = cls()
		xmldoc = self.decompress(self.decode(msg)) if msg else ''
		if xmldoc:
			self.doc = xml.dom.minidom.parseString(xmldoc)
		return self
		
	def __len__(self):
		return len(self.doc.documentElement.childNodes)

class Request(RPC):
	_root_name = 'request'
	def __iter__(self):
		for node in self.doc.documentElement.childNodes:
			handle = str(node.getAttribute('handle'))
			func = func_def(node.getAttribute('function'))
			for child in node.childNodes:
				if child.nodeType == node.ELEMENT_NODE:
					grandchild = getFirstChildElement(child)
					if child.nodeName == 'arg':
						func.args.append(eval_xmlobjtree(grandchild))
					if child.nodeName == 'kwarg':
						key = eval_xmlobjtree(grandchild)
						func.kwargs[key] = eval_xmlobjtree(getNextSiblingElement(grandchild))
			yield (handle, func)
		
	def append(self, func):
		node = self.doc.createElement('call')
		iden = '%08x' % random.getrandbits(32)
		iden += time.strftime('%Y%m%d%H%M%S',time.gmtime())
		iden += repr(func)
		node.setAttribute('function', func.name)
		node.setAttribute('handle', hashlib.md5(iden).hexdigest())
		for arg in func.args:
			a = self.doc.createElement('arg')
			a.appendChild(build_xmlobjtree(self.doc, arg))
			node.appendChild(a)
		for key in func.kwargs:
			a = self.doc.createElement('kwarg')
			a.appendChild(build_xmlobjtree(self.doc, key))
			a.appendChild(build_xmlobjtree(self.doc, func.kwargs[key]))
			node.appendChild(a)
		self.doc.documentElement.appendChild(node)
	
class Response(RPC):
	_root_name = 'reponse'
	def append(self, handle, typ, payload):
		node = self.doc.createElement(typ)
		node.setAttribute('handle', handle)
		node.appendChild(build_xmlobjtree(self.doc, payload))
		self.doc.documentElement.appendChild(node)
		
	def __iter__(self):
		for node in self.doc.documentElement.childNodes:
			handle = str(node.getAttribute('handle'))
			resp = node.nodeName
			payload = eval_xmlobjtree(getFirstChildElement(node))
			if resp == 'return':
				yield handle, payload
			elif resp == 'error':
				yield handle, Exception(payload)

def getFirstChildElement(node):
	node = node.firstChild
	while node.nodeType != node.ELEMENT_NODE:
		node = node.nextSibling
	return node
	
def getNextSiblingElement(node):
	node = node.nextSibling
	while node.nodeType != node.ELEMENT_NODE:
		node = node.nextSibling
	return node
			
class Client(object):
	def __init__(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		#negotiate capabilities
		self.wfile = self.sock.makefile('wb')
		self.rfile = self.sock.makefile('rb')
		
	def connect(self, (host, port)):
		self.sock.connect((host, port))
		
	def close(self):
		self.sock.close()
	
	def call_quick(self, f, *args, **kwargs):
		func = func_def(f, *args, **kwargs)
		request = Request()
		request.append(func)
		for handle, payload in self.call(request):
			return handle, payload
		
	def call(self, request):
		self.wfile.write(request.pack())
		self.wfile.flush()
		line = self.rfile.readline()
		if line:
			return iter(Response.from_packed_xml(line))
		else:
			raise EOFError

class RequestHandler(SocketServer.StreamRequestHandler):
	def debug(self, text):
		print 'Client %s:%s -' % self.client_address, text
		
	def handle(self):
		self.debug('Connected')
		while True:
			request = Request.from_packed_xml(self.rfile.readline())
			if not request:
				break
			resp = Response()
			for handle, func in request:
				try:
					self.debug('Called ' + str(func))
					typ = 'return'
					ret = self.server.on_call(func.name, *func.args, **func.kwargs)
				except BaseException, e:
					ret = traceback.format_exc(e)
					typ = 'error'
					self.debug('Error\n' + ret)
				else:
					self.debug('Returning ' + repr(ret))
				resp.append(handle, typ, ret)
			self.wfile.write(resp.pack())
			self.wfile.flush()
		self.debug('Disconnected')
		
class Server(SocketServer.TCPServer):
	allow_reuse_address = True
	def __init__(self, address, handler=None):
		SocketServer.TCPServer.__init__(self, address, handler or RequestHandler)

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
		test = func_def('test', [{0:u'0'}, 1,'2<int/>',(3.0,{True:5, '6':complex(1,2.5), False:None})])
		print repr(test)
		
		request = Request()
		request.append(test)
		print request.doc.toxml()
		
		sent = request.pack()
		print repr(sent)
		rcvd = request.from_packed_xml(sent)
		print len(request.encode(request.compress(repr(test)))), '/', len(rcvd.doc.toxml()), '/', len(sent)
		
		for handle, result in rcvd:
			break
		print repr(result)
		exit(test != result)
