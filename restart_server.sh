#!/bin/bash

screen -S server -p 0 -X stuff '^C'

sleep 5

screen -S server -X quit

screen -dmS server

screen -S server -p 0 -X stuff "cd /root/server/socks-manger/\n"

screen -S server -p 0 -X stuff "/usr/local/bin/gunicorn --reload -w 4 -b 0.0.0.0:3000 zhongkong:app\n"
