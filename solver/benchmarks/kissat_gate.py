#!/usr/bin/env python3
"""Benchmark-only two-slot gate; exec preserves the native caller's child PID."""
import errno
import fcntl
import os
from pathlib import Path
import sys
import time


def main():
    real=Path(os.environ.get('REAL_KISSAT') or (Path(sys.argv[0]).absolute().parent/'kissat-real'))
    if not real.is_absolute() or not real.is_file() or not os.access(real,os.X_OK):raise RuntimeError('REAL_KISSAT absolute executable required')
    if real.resolve()==Path(__file__).resolve():raise RuntimeError('real Kissat points to wrapper')
    args=sys.argv[1:]
    if args==['--version']:os.execv(str(real),[str(real),*args])
    if int(os.environ.get('KISSAT_GATE_SLOTS','2'))!=2:raise RuntimeError('controlled benchmark requires two slots')
    directory=Path(os.environ.get('KISSAT_GATE_DIR') or (Path(sys.argv[0]).absolute().parent/'.kissat-gate'))
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    if directory.stat().st_uid!=os.getuid() or directory.stat().st_mode&0o077:raise RuntimeError('private user-owned mode0700 gate directory required')
    handles=[];locked=None
    try:
        flags=os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0)
        handles=[os.open(directory/f'slot{i}.lock',flags,0o600) for i in range(2)]
        while locked is None:
            for i in range(2):
                fd=handles[(os.getpid()+i)%2]
                try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);locked=fd;break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES,errno.EAGAIN):raise
            if locked is None:time.sleep(.003)
        for fd in handles:
            if fd!=locked:os.close(fd)
        handles=[locked]
        # flock survives exec on this open file description. Keep this PID so Rust
        # Child.kill(SIGKILL) kills the real solver and releases the lock atomically.
        os.set_inheritable(locked,True)
        os.execv(str(real),[str(real),*args])
    finally:
        for fd in handles:os.close(fd)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('kissat benchmark gate:',str(exc),file=sys.stderr)
        raise SystemExit(2)
