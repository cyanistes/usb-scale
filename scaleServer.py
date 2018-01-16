#! /usr/bin/env python

# This will run as a production ready server if something like eventlet is installed

import argparse
import json
import os
import threading
import time
import sys

from gevent import ssl
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource

from readscale import set_scale


clients = 0

scale = None


class WeightApp(WebSocketApplication):
    def setup_scale(self):
        global scale
        try:
            scale = set_scale()
        except ValueError:
            scale = None
            sys.stdout.write("\rPlease ensure that scale is connected and not in use by another process")
            sys.stdout.flush()

    def on_open(self):
        print "Connected!"
        global clients
        if clients:
            clients += 1
            return
        clients += 1
        self.send_weight()

    def on_message(self, message, *args, **kwargs):
        if message:
            print message

    def on_close(self, reason):
        print 'Disconnected'
        global clients
        clients -= 1
        if reason:
            print reason

    def send_weight(self, reschedule=0.2):
        """
        broadcast the weight on the scale to listeners
        :param weight: dictionary with
        :param reschedule: time delay to reschedule the function
        :return: None
        """
        global scale
        fakeweight = {
            'lbs': 'Please connect scale',
            'ozs': 'Please connect scale',
            'grams': 'Please connect scale',
        }
        if not scale:
            self.setup_scale()
        if scale:
            try:
                scale.update()
                weight = {
                    'lbs': scale.pounds,
                    'ozs': scale.ounces,
                    'grams': scale.grams,

                }
            except IOError:
                self.setup_scale()
                weight = fakeweight
        else:
            weight = fakeweight
        if clients:
            self.ws.send(json.dumps(weight))
        if reschedule and clients:
            threading.Timer(reschedule, self.send_weight).start()


def static_wsgi_app(environ, start_response):
    """
    Serve a test page
    :param environ:
    :param start_response:
    :return:
    """
    start_response("200 OK", [('Content-Type]', 'text/html')])
    with open("templates/index.html", 'r') as f:
        retval = [bytes(line) for line in f.readlines()]
    return retval


def parse_args():
    """
    Parse cmd line arguments
    :return: arguments
    """
    parser = argparse.ArgumentParser(description='Serve USB scale weights over WebSockets')
    parser.add_argument('-k', '--key', help='Server private key for SSL')
    parser.add_argument('-c', '--cert', help='Server certificate for SSL')
    parser.add_argument('-p', '--port', default=8000, help='Port for http server')
    parser.add_argument('-b', '--bind', default='localhost', help='Bind address')
    return parser.parse_args()


def validate_file(_file):
    """
    Check to see if a file exists
    :param _file: path to file
    :return: True for file exists, Raises RuntimeError if doesn't exist
    """
    if not os.path.isfile(_file):
        raise RuntimeError("The file provided does not exist! {}".format(_file))
    return True


if __name__ == '__main__':
    args = parse_args()
    server_args = []
    server_kwargs = dict()
    try:
        scale = set_scale()
    except ValueError:
        print "ERROR: Unable to connect to the scale!!"
        scale = None
    if not args.cert and not args.key:
        pass
    elif validate_file(args.cert) and validate_file(args.key):
        server_kwargs.update({'keyfile': args.key,
                              'certfile': args.cert})
    server_args.append((args.bind, args.port))
    server_args.append(
        Resource([
            ('/', static_wsgi_app),
            ('/data', WeightApp)
        ])
    )
    WebSocketServer(*server_args, **server_kwargs).serve_forever()
