import xmlrpclib

class client(xmlrpclib.ServerProxy, object):
	def __init__(self, host='localhost', port=8145, **kargs):
		xmlrpclib.ServerProxy.__init__(self,'http://%s:%i' % (host, port),allow_none=True,**kargs)
