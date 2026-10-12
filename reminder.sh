#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
export GDK_BACKEND=x11
python3 "$DIR/reminder.py" "$@"
