#!/usr/bin/env python

import mcp_rpc_pb2 as rpc

import SocketServer

def HandlerFactory(MethodClass):
	class Handler(SocketServer.BaseRequestHandler):
		mc = MethodClass
		def handle(self):
			#Decode protocol buffer
			#func, args = decode(response)
			#Call Function
			mc[func](*args)
	return Handler
			

class Server(SocketServer.TCPServer):
	def __init__(self, MethodClass, host="0.0.0.0", port=8145):
		SocketServer.TCPServer.__init__(self, (host,port), HandlerFactory(MethodClass))
	
class Connection(object):
	def __init__(self, host, port):
		pass
	
	
__all__ = ['Server','Connection']
