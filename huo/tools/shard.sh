#!/bin/sh
# make shard | shard-attach | shard-stop | shard-status (P0.09). Mini only.
# The ModernUO console lives in a tmux session named "shard", started from ~/src/ModernUO/Distribution.
set -eu
cd "$(dirname "$0")/../.."
SESSION=shard
PORT=2593
DIST="$HOME/src/ModernUO/Distribution"

role=$(sed -n 's/^HOST_ROLE=//p' .env 2>/dev/null | head -n 1 | tr -d "\"' ")
if [ "$role" != "mini" ]; then
  echo "shard: HOST_ROLE is '${role:-unset}', not mini; the shard runs only on the Mini"
  exit 1
fi

has_session() { tmux has-session -t "$SESSION" 2>/dev/null; }
listening() { nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1; }

case "${1:-}" in
  start)
    if has_session; then
      echo "shard: tmux session '$SESSION' already exists (make shard-status, make shard-attach)"
      exit 0
    fi
    if [ ! -x "$DIST/ModernUO" ]; then
      echo "shard: $DIST/ModernUO not found (build it in P0.08)"
      exit 1
    fi
    tmux new-session -d -s "$SESSION" -c "$DIST"
    tmux send-keys -t "$SESSION" ./ModernUO Enter
    echo "shard: starting in tmux session '$SESSION'; run make shard-status in about 30 s"
    ;;
  attach)
    if ! has_session; then
      echo "shard: no tmux session '$SESSION' (make shard)"
      exit 1
    fi
    exec tmux attach -t "$SESSION"
    ;;
  stop)
    if ! has_session; then
      echo "shard: not running"
      exit 0
    fi
    tmux send-keys -t "$SESSION" save Enter
    echo "shard: save sent, waiting 10 s"
    sleep 10
    tmux send-keys -t "$SESSION" shutdown Enter
    i=0
    while listening && [ "$i" -lt 30 ]; do
      sleep 1
      i=$((i + 1))
    done
    if listening; then
      echo "shard: still listening 30 s after shutdown; look with make shard-attach"
      exit 1
    fi
    tmux kill-session -t "$SESSION"
    echo "shard: stopped"
    ;;
  status)
    s=no
    l=no
    if has_session; then s=yes; fi
    if listening; then l=yes; fi
    echo "shard: tmux session $s, port $PORT listening $l"
    if [ "$s" = yes ] && [ "$l" = yes ]; then exit 0; fi
    exit 1
    ;;
  *)
    echo "usage: sh huo/tools/shard.sh start|attach|stop|status"
    exit 2
    ;;
esac
