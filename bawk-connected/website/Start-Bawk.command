#!/bin/zsh
cd "${0:A:h}"
/usr/bin/python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',8765)); s.close()" 2>/dev/null
if [[ $? != 0 ]]; then
  print "Port 8765 is already in use. If Bawk is already running, open http://localhost:8765."
  read "?Press Return to close."
  exit 1
fi
(sleep 1; open http://localhost:8765) &
exec /usr/bin/python3 server.py
