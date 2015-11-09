# weechat-letschat

[lets-chat](http://sdelements.github.io/lets-chat/) integration in
[weechat](https://weechat.org/)

This plugin is eavy experimental and lack of user-friendlyness

## Installation and usage

Clone this repository :

    git clone https://github.com/calve/weechat-letschat.git

Open ``weechat-letschat.py`` and modify the following variable at the
top of the file :

    _domain = "your.letschat.com"
    _token = "your_access_token"

Expose the script in weechat

``ln -s weechat.py ~/.weechat/python/weechat-letschat.py``


In weechat, run ``/python load weechat-letschat.py`` to connect to weechat

## About

This plugin is heavily derived from
[weeslack](https://github.com/rawdigits/wee-slack). Thanks
