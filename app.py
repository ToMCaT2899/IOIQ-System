# 主入口程序，主要是加载程序、加载和管理路由、配置访问控制以及服务器启动配置等

# v0.1版本：用于验证tornado框架的最小示例，主要是验证路由、程序加载、服务器启动
import tornado.web
import tornado.ioloop
from tornado.httpserver import HTTPServer

class IndexHandler(tornado.web.RequestHandler):
	def get(self):
		self.write("<h1>欢迎访问</h1><a href='/login.php'>跳转</a>")	
	def post(self):
		pass

class LoginHandler(tornado.web.RequestHandler):
	def get(self):
		self.write("<h1>欢迎访问登录</h1><a href='/'>跳转</a>")	
	def post(self):
		pass

#web应用
def app():
	return tornado.web.Application(
		[
			("/",IndexHandler),
			("/index.html",IndexHandler),
			("/login.php",LoginHandler)
		],
		debug="True"
		)


if __name__ == "__main__":
	app = app()
	server = HTTPServer(app)
	server.listen(10086)
	print("Server Started:http://localhost:10086/",flush=True)
	tornado.ioloop.IOLoop.current().start()