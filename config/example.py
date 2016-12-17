from .base import *

import os

if 'PUSHBULLET_API_KEY' in os.environ:
    PUSHBULLET_API_KEY = os.environ['PUSHBULLET_API_KEY']
if 'DISCORD_CHANNEL_ID' in os.environ and 'DISCORD_TOKEN' in os.environ:
    DISCORD_CHANNEL_ID = os.environ['DISCORD_CHANNEL_ID']
    DISCORD_TOKEN = os.environ['DISCORD_TOKEN']

