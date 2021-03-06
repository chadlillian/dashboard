#!/usr/bin/env python

import webapp2
import os
import logging
import json
import random
import datetime
import time

from datetime import datetime
from datetime import timedelta
from google.appengine.api import channel
from google.appengine.ext.webapp import template
from google.appengine.api import memcache
from google.appengine.ext import ndb


class Connection(ndb.Model):
    channel_id = ndb.StringProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)

class Scene(ndb.Model):
    name = ndb.StringProperty()
    next_id = ndb.IntegerProperty(default=0, indexed=False)
    connections = ndb.StructuredProperty(Connection, repeated=True)


class UserMessage(webapp2.RequestHandler):
    def post(self):
        channel_id = self.request.get('channel_id');
        clientSeq = self.request.get('clientSeq');
        timestamp = self.request.get('timestamp');
        msg = self.request.get('msg');
        logging.info('Received MESSAGE [%s %s]' % (channel_id, clientSeq))
        sequence = memcache.incr("sequence", initial_value=0)
        if sequence is None:
            sequence = 0
        scene_k = ndb.Key('Scene', 'scene1')
        scene = scene_k.get()
        # echo message back to all users
        message = json.dumps({
                    'type' : 'echo',
                    'sequence' : sequence,
                    'timestamp' : timestamp,
                    'clientSeq' : int(clientSeq),
                    'channel_id' : channel_id,
                    'msg' : msg,
                    'server_time' : int(time.time() * 1000)
                });
        tStart = datetime.now()
        channel.send_message(channel_id, message)
        tTotal = datetime.now() - tStart
        logging.info('   responded to sender [%s] (%dms)' % (channel_id, tTotal.microseconds/1000))

        if len(scene.connections)>1:
            logging.info('   broadcasting to %i clients' % (len(scene.connections)-1))
            for c in scene.connections:
                if c.channel_id != channel_id:
                    tStart = datetime.now()
                    channel.send_message(c.channel_id, message)
                    tTotal = datetime.now() - tStart
                    logging.info('     broadcast to [%s] (%dms)' % (c.channel_id, tTotal.microseconds/1000))


def send_client_list(connections):
    clients = []
    for c in connections:
        clients.append(c.channel_id)
    message = json.dumps({
        'type' : 'client_list',
        'clients' : clients
    })
    for c in connections:
        channel.send_message(c.channel_id, message)
        logging.info('     sending client_list to [%s]' % (c.channel_id))


class UserDisconnected(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('from')
        logging.info('Received DISCONNECT from %s' % client_id)
        scene_k = ndb.Key('Scene', 'scene1')
        scene = scene_k.get()
        if scene is not None:
            for c in scene.connections:
                if c.channel_id == client_id:
                    logging.info('   removing client %s' % client_id)
                    scene.connections.remove(c)
                    scene.put()
                    # inform other clients
                    send_client_list(scene.connections)
                    return


class UserConnected(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('from')
        logging.info('Received CONNECT from %s' % client_id)
        # inform other clients about the new addition
        # inform this client about the other clients
        scene_k = ndb.Key('Scene', 'scene1')
        scene = scene_k.get()
        send_client_list(scene.connections)


def remove_expired_connections(connections):
    removed = False
    for c in connections:
        time_diff = datetime.now() - c.timestamp
        max_time = timedelta(hours=2)
        if time_diff >= max_time:
            logging.info('Removing expired connection [%s] timedelta=%s' % (c.channel_id, str(c.timestamp)))
            connections.remove(c)
            removed = True
    return removed


class MainHandler(webapp2.RequestHandler):
    def get(self):
        scene_k = ndb.Key('Scene', 'scene1')
        scene = scene_k.get()
        if scene is None:
            logging.info('MainHandler creating Scene')
            scene = Scene(name='Scene 1', id='scene1')

        # take this opportunity to cull expired channels
        removed = remove_expired_connections(scene.connections)
        if removed:
            send_client_list(scene.connections)

        channel_id = str(scene.next_id)
        scene.next_id += 1
        scene.connections.append( Connection(channel_id=channel_id) )
        token = channel.create_channel(channel_id)
        scene.put()
        logging.info('MainHandler channel_id=%s' % channel_id)
        path = os.path.join(os.path.dirname(__file__), "main.html")
        template_values =   {'token' : token,
                             'channel_id' : channel_id
                            }
        self.response.out.write(template.render(path, template_values))


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/message', UserMessage),
    ('/_ah/channel/connected/', UserConnected),
    ('/_ah/channel/disconnected/', UserDisconnected)
    ],debug=True)
