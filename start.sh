#!/bin/sh
node /opt/bgutil-provider/server/build/main.js &
sleep 2
gunicorn --bind 0.0.0.0:10000 --timeout 120 server:app