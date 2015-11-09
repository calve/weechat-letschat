# -*- coding:utf-8 -*-
import pickle
import json
import time
import urllib
try:
    import weechat as w
except:
    pass

SCRIPT_NAME = "weechat-letschat"
SCRIPT_AUTHOR = "calve <calvinh34@gmail.com>"
SCRIPT_VERSION = "0.0.1"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Extends weechat for interacting with a letschat instance"

rooms_by_id = {}
users_by_id = {}
_domain = "pcmt6"  # Should be set by configuration
_token = "NTYyNzkzODgwNTEwOGUxYTAwNzJiNmIyOjhlNzJhMTY2NDYzZWJjNjVlYzZiZjBkYTc1NDQ2MDA0YTYwZmVjNGI1ODRkNGU0NA=="
last_id = None


def dbg(message, fout=False, main_buffer=False):
    """
    send debug output to the slack-debug buffer and optionally write to a file.
    """
    message = "DEBUG: {}".format(message)
    w.prnt("", message)


def async_http_get_request(domain, token, request):
    url = 'url:http://{token}:nopass@{domain}/{request}'.format(
        domain=domain,
        request=request,
        token=token,
    )
    context = pickle.dumps({"request": request, "token": token})
    params = {'useragent': 'weechat-letschat 0.0'}
    #dbg("URL: {} context: {} params: {}".format(url, context, params))
    w.hook_process_hashtable(url, params, 20000, "url_processor_cb", context)


def async_http_post_request(domain, token, request, post_data=None):
    url = 'http://{token}:nopass@{domain}/{request}'.format(
        domain=domain,
        request=request,
        token=token,
    )
    context = pickle.dumps({"request": request, "token": token, "post_data": post_data})
    params = {'useragent': 'weechat-letschat 0.0'}
    command = 'curl -X POST {url} -H "Content-Type: application/json" --data \'{post_data}\''.format(url=url, post_data=json.dumps(post_data))
    w.hook_process_hashtable(command, params, 20000, "url_processor_cb", context)

# Callbacks
def url_processor_cb(data, command, return_code, out, err):
    """
    Called back when an http request is completed
    """
    data = pickle.loads(data)
    dbg("url_processor_cb data : {}".format(data))
    dbg("out : {}".format(out))
    out = out.decode('UTF-8')
    if return_code == 0:
        try:
            returned_json = json.loads(out)
        except ValueError as e:
            dbg(e)
        server = servers.find_by_key('token', data['token'])
        if data['request'] == 'account':
            # We may now update account informations
            server.nick = returned_json['username']
            server.name = returned_json['username']
            server.identifier = returned_json['id']
            server.build()
        elif data['request'] == 'rooms':
            for room in returned_json:
                server.add_room(room)
        elif 'messages' in data['request']:
            if type(returned_json) is list:
                # Process a list of GETted messages
                for message in returned_json:
                    server.add_message(message)
            else:
                # Process a POSTed message
                server.add_message(returned_json)
        elif data['request'] == 'users':
            for user in returned_json:
                users.append({user['id']: user['displayName']})
                users_by_id[user['id']] = user['displayName']

    return w.WEECHAT_RC_OK


def buffer_input_cb(b, buffer, data):
    """
    Called when user want to send a message
    """
    room = rooms.find_by_key("pointer", str(buffer))
    room.send_message(data)
    return w.WEECHAT_RC_ERROR


def update_messages_room_cb(room, remaining):
    global last_id
    dbg("fetching message since {}".format(last_id))
    async_http_get_request(_domain, server.token, "/rooms/{room}/messages?since_id={since}".format(last_id))
    return w.WEECHAT_RC_OK

class SearchList(list):
    """
    A normal python list with some syntactic sugar for searchability
    """
    def __init__(self):
        self.hashtable = {}
        super(SearchList, self).__init__(self)

    def find(self, name):
        dbg(self.hashtable.keys())
        if name in self.hashtable.keys():
            return self.hashtable[name]
        #this is a fallback to __eq__ if the item isn't in the hashtable already
        if self.count(name) > 0:
            self.update_hashtable()
            return self[self.index(name)]

    def find_by_key(self, key, name):
        for item in self:
            if hasattr(item, key) and getattr(item, key) == name:
                return item

    def append(self, item, aliases=[]):
        super(SearchList, self).append(item)
        self.update_hashtable()

    def update_hashtable(self):
        for child in self:
            if hasattr(child, "get_aliases"):
                for alias in child.get_aliases():
                    if alias is not None:
                        self.hashtable[alias] = child

    def find_by_class(self, class_name):
        items = []
        for child in self:
            if child.__class__ == class_name:
                items.append(child)
        return items

    def find_by_class_deep(self, class_name, attribute):
        items = []
        for child in self:
            if child.__class__ == self.__class__:
                items += child.find_by_class_deep(class_name, attribute)
            else:
                items += (eval('child.' + attribute).find_by_class(class_name))
        return items


class LetschatServer():
    """
    Root object used to represent connection and state of the connection to a slack group.
    """
    def __init__(self, token):
        self.token = token
        self.nick = None
        self.name = None
        self.domain = None
        self.login_data = None
        self.buffer = None
        self.ws = None
        self.ws_hook = None
        self.users = SearchList()
        self.bots = SearchList()
        self.rooms = SearchList()
        self.connecting = False
        self.connected = False
        self.communication_counter = 0
        self.message_buffer = {}
        self.ping_hook = None

        self.identifier = None
        dbg("init server {} with token {}".format(self, self.token))

    def connect(self):
        async_http_get_request(_domain, self.token, "account")

    def build(self):
        """Retrieve the channels and users list"""
        async_http_get_request(_domain, self.token, "rooms")
        async_http_get_request(_domain, self.token, "users")
        #w.hook_timer(1000, 0, 0, "update_messages_cb", "")

    def add_room(self, room):
        name = room['name']
        ident = room['id']
        room = Room(self, name, ident)
        self.rooms.append(room)

    def add_message(self, message):
        room = rooms.find_by_key('identifier', message['room'])
        room.add_message(message)

    def create_buffer(self):
        channel_buffer = w.buffer_search("", "{}.{}".format(self.server.domain, self.name))
        if channel_buffer:
            self.channel_buffer = channel_buffer
        else:
            self.channel_buffer = w.buffer_new("{}.{}".format(self.server.domain, self.name), "buffer_input_cb", self.name, "", "")
            if self.type == "im":
                w.buffer_set(self.channel_buffer, "localvar_set_type", 'private')
            else:
                w.buffer_set(self.channel_buffer, "localvar_set_type", 'channel')
            w.buffer_set(self.channel_buffer, "short_name", 'loading..')


class Room():
    """Represent a single Room"""
    def __init__(self, server, name, identifier, members=[]):
        self.server = server
        self.name = name
        self.identifier = identifier
        self.members = set(members)
        self.pointer = w.buffer_new(name, "buffer_input_cb", "", "buffer_close_cb", "")
        rooms.append(self)
        async_http_get_request(_domain, server.token, "rooms/{}/messages?reverse=false".format(identifier))
        rooms_by_id[identifier] = name
        rooms.update_hashtable()
        dbg("Creating room {}".format(self))

    def __str__(self):
        return "{} ({})".format(self.name, self.pointer)

    def __repr__(self):
        return self.name

    def send_message(self, message):
        data = {
            "room": self.identifier,
            "text": message
        }
        dbg(data)
        async_http_post_request(_domain, _token, "messages", data)

    def add_message(self, message):
        text = message['text'].encode('UTF-8', 'replace')
        name = users_by_id[message['owner']].encode('UTF-8')
        # Format username with text
        data = "{}\t{}".format(name, text)
        room_buffer = w.buffer_search("", self.name)
        w.prnt_date_tags(room_buffer, int(time.time()), "", data)
        self.last_id = message['id']
        dbg("last_id : {}".format(self.last_id))

if __name__ == "__main__":
    if w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE,
                  SCRIPT_DESC, "script_unloaded", ""):

        WEECHAT_HOME = w.info_get("weechat_dir", "")
        CACHE_NAME = "slack.cache"
        STOP_TALKING_TO_SLACK = False

        if not w.config_get_plugin('letschat_api_token'):
            w.config_set_plugin('letschat_api_token', "INSERT VALID KEY HERE!")

        letschat_api_token = w.config_get_plugin("slack_api_token")
        letschat_api_token = _token
        letschat_api_serveur = _domain

        servers = SearchList()
        for token in letschat_api_token.split(','):
            server = LetschatServer(token)
            servers.append(server)
            server.connect()
            dbg(servers)
        channels = SearchList()
        rooms = SearchList()
        users = SearchList()
