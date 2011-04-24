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

def get_type(obj):
	for t in int,long,bool,float,complex,str,unicode,bytearray,list,tuple,dict,set:
		if isinstance(obj,t):
			break
	return {
		bool:'bool', int:'int', long:'long', float:'float',
		complex:'complex',
		str:'str', unicode:'unicode', bytearray:'bytearray',
		list:'list', tuple:'tuple',
		dict:'dict', set:'set', frozenset:'frozenset',
	}[t]
	
def type_from_name(name):
	return {
		'bool':bool, 'int':int, 'long':long, 'float':float,
		'complex':complex,
		'str':str, 'unicode':unicode, 'bytearray':bytearray,
		'list':list, 'tuple':tuple,
		'dict':dict, 'set':set, 'frozenset':frozenset,
	}[name]
	
class func_def(object):
	def __init__(self, name, *args, **kwargs):
		self.name = str(name)
		self.args = list(args)
		self.kwargs = dict(kwargs)
		
	def __eq__(self, x):
		return self.name == x.name and self.args == x.args and self.kwargs == x.kwargs
		
	def __str__(self):
		return '%s(%s)' % (self.name, (', '.join(map(repr,self.args) + ['%s=%r' % i for i in self.kwargs.items()])))
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
			
	def pack(self, msg):
		return self.encode(self.compress(msg)) + '\n'
		
	def unpack(self, msg):
		return self.decompress(self.decode(msg[:-1])) if len(msg) >= 2 else ''
	
	@staticmethod
	def serialize(func):
		doc = impl.createDocument(None, 'request', None)
		node = doc.createElement('call')
		iden = '%08x' % random.getrandbits(32)
		iden += time.strftime('%Y%m%d%H%M%S',time.gmtime())
		iden += repr(func)
		node.setAttribute('function', func.name)
		node.setAttribute('handle', hashlib.md5(iden).hexdigest())
		for arg in func.args:
			a = doc.createElement('arg')
			a.appendChild(build_xmlobjtree(doc, arg))
			node.appendChild(a)
		for key in func.kwargs:
			a = doc.createElement('kwarg')
			a.appendChild(build_xmlobjtree(doc, key))
			a.appendChild(build_xmlobjtree(doc, func.kwargs[key]))
			node.appendChild(a)
		doc.documentElement.appendChild(node)
		return doc.toxml()
		
	@staticmethod
	def deserialize(xmldoc):
		#print xmldoc
		doc = xml.dom.minidom.parseString(xmldoc)
		#for node in top.childNodes:
		node = getFirstChildElement(doc.documentElement)
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
		return handle, func
		
	@staticmethod
	def respond(handle, typ, payload):
		doc = impl.createDocument(None, 'response', None)
		node = doc.createElement(typ)
		node.setAttribute('handle', handle)
		node.appendChild(build_xmlobjtree(doc, payload))
		doc.documentElement.appendChild(node)
		return doc.toxml()
		
	@staticmethod
	def interpret_response(xmldoc):
		doc = xml.dom.minidom.parseString(xmldoc)
		node = getFirstChildElement(doc.documentElement)
		handle = str(node.getAttribute('handle'))
		resp = node.nodeName
		payload = eval_xmlobjtree(getFirstChildElement(node))
		if resp == 'return':
			return payload
		elif resp == 'error':
			raise Exception(payload)

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
			
class RPCClient(RPC):
	def __init__(self, host, port):
		RPC.__init__(self)
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.connect((host, port))
		#negotiate capabilities
		self.wfile = self.sock.makefile('wb')
		self.rfile = self.sock.makefile('rb')
	
	def call(self, f, *args, **kwargs):
		func = func_def(f, *args, **kwargs)
		request = self.serialize(func)
		self.wfile.write(self.pack(request))
		self.wfile.flush()
		response = self.unpack(self.rfile.readline())
		return self.interpret_response(response)

class RPCRequestHandler(SocketServer.StreamRequestHandler):
	def setup(self):
		SocketServer.StreamRequestHandler.setup(self)
		self.functions = self.server.functions
		self.pack = self.server.pack
		self.unpack = self.server.unpack
		
	def debug(self, text):
		print 'Client %s:%s -' % self.client_address, text
		
	def handle(self):
		self.debug('Connected')
		while True:
			request = self.unpack(self.rfile.readline())
			if not request:
				break
			try:
				handle, func = RPC.deserialize(request)
				self.debug('Called ' + str(func))
				typ = 'return'
				f = self.functions[func.name]
				ret = f(*func.args, **func.kwargs)
			except BaseException, e:
				ret = traceback.format_exc(e)
				typ = 'error'
				self.debug('Error\n' + ret)
			else:
				self.debug('Returning ' + repr(ret))
			resp = RPC.respond(handle, typ, ret)
			self.wfile.write(self.pack(resp))
			self.wfile.flush()
		self.debug('Disconnected')
		
class RPCServer(SocketServer.TCPServer, RPC):
	allow_reuse_address = True
	def __init__(self, address, handler=None):
		SocketServer.TCPServer.__init__(self, address, handler or RPCRequestHandler)
		RPC.__init__(self)
		self.functions = {}
	
	def register(self, name, func):
		self.functions[name] = func

if __name__=='__main__':
	import StringIO
	import sys

	HOST, PORT = "localhost", 9999
	if len(sys.argv) == 1:
		def a(b, c, genre=None):
			return 789, b, c, genre
		server = RPCServer((HOST, PORT))
		server.register('a', a)
		try:
			server.serve_forever()
		except KeyboardInterrupt:
			pass
	elif sys.argv[1] == 'client':
		client = RPCClient(HOST, PORT)
		print repr(client.call('a', 123, '456', genre='jazz'))
		print repr(client.call('a', '456', 'apple', genre='classical'))
	elif sys.argv[1] == 'unittest':
		test = [{0:u'0'}, 1,'2<int/>',(3.0,{True:5, '6':complex(1,2.5), False:None})]
		print repr(test)
		
		doc = impl.createDocument(None, 'test', None)
		doc.documentElement.appendChild(build_xmlobjtree(doc, test))
		print doc.toxml()
		
		rpc = RPC()
		sent = rpc.pack(doc.toxml())
		print repr(sent)
		rcvd = rpc.unpack(sent)
		print len(repr(test)), '/', len(rcvd), '/', len(sent)
		
		doc = xml.dom.minidom.parseString(rcvd)
		result = eval_xmlobjtree(doc.documentElement.firstChild)
		print repr(result)

		exit(test != result)
