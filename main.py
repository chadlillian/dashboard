import	cgi
import	webapp2
import	jinja2
import	os
import	datetime
import	json
from google.appengine.ext import ndb

from google.appengine.api import users

jinja_env	=jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

def	formatdatetime(dt):
	return	dt.strftime('%X %x')

class	data(ndb.Model):
	num		=ndb.IntegerProperty()
	date	=ndb.DateTimeProperty(auto_now_add=True)

class	compositeData(ndb.Model):
	values	=ndb.JsonProperty()
	application	=ndb.StringProperty()

class MainPage(webapp2.RequestHandler):
	def get(self):
		self.response.out.write(open('dashboard.html').read())
		#self.response.out.write(open('index.html').read())

class update(webapp2.RequestHandler):
	def	write(self):
		self.data	={}

	def	get(self):
		print self.request.get('value')
		print self.request.get('application')
		value		=float(self.request.get('value'))
		application	=self.request.get('application')

		qry			=compositeData.query(compositeData.application==application)
		timestamp	=datetime.datetime.now()
		timestampf	=timestamp.strftime('%X %x')
		tdelta		=datetime.timedelta(0,3600)
		
		if qry.count()==0:
			tempc		=compositeData()
			tempc.populate(application=application)
			tempc.populate(values=[{'date':timestampf,'value':value}])
			tempc.put()
		else:
			entity				=qry.fetch(1)[0]
			key					=entity.key
			vals				=[q for q in entity.values if datetime.datetime.strptime(q['date'],'%X %x')>timestamp-tdelta]
			vals.append({'date':timestampf,'value':value})

			entity				=key.get()
			entity.values		=vals
			entity.put()

class	watch(webapp2.RequestHandler):
	def	get(self):
		qry	=compositeData.query(compositeData.application=='X')
		d	=qry.fetch(1)[0].values

		self.response.out.write(json.dumps(d))

class	reset(webapp2.RequestHandler):
	def	get(self):
		qry	=compositeData.query(compositeData.application=='X').fetch(1)[0].key.delete()
		

app = webapp2.WSGIApplication(	[('/', MainPage),
                              	('/update', update),
                              	('/watch', watch),
                              	('/reset', reset),
								],
								debug=True)

