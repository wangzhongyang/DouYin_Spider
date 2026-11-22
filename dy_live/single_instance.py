"""单实例保护：同一个直播间监听只允许跑一个进程。

用文件锁（进程存活期间一直持有），而不是「检查到进程存在就退出」——
后者在同时启动两个进程时会双双通过检查，仍然重复。文件锁由内核保证原子性。

锁文件里写着 PID，重复启动时可以直接告诉用户是哪个进程占着。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_LOCK = Path(__file__).resolve().parent.parent / '.dy_live.lock'


def acquire_single_instance(path: str | Path = DEFAULT_LOCK):
    """拿不到锁就打印原因并退出（exit code 2）。返回的文件对象要一直持有。"""
    lock_path = Path(path)
    handle = open(lock_path, 'a+', encoding='utf-8')

    try:
        if sys.platform == 'win32':
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.seek(0)
        holder = handle.read().strip()
        handle.close()
        print(
            f'已有直播间监听在运行（PID {holder or "未知"}），本次启动已取消。\n'
            f'如果确认没有在跑，删掉 {lock_path} 再试。',
            file=sys.stderr,
        )
        sys.exit(2)

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle
