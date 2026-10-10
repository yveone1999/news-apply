"""以新会话（os.setsid）运行命令，使其在父 shell / 会话被清理后继续常驻。

用法: python scripts/detach.py <日志文件> <命令> [参数...]
stdin 重定向到 /dev/null，stdout/stderr 追加到日志文件。
PID 保持不变（exec 替换进程），可直接用 $! 记录。
"""
import os
import sys


def main() -> None:
    log_path, cmd, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    try:
        os.setsid()
    except OSError:
        pass  # 已是会话组长时忽略，不影响运行
    log = open(log_path, "ab")
    os.dup2(log.fileno(), 1)
    os.dup2(log.fileno(), 2)
    devnull = open(os.devnull, "rb")
    os.dup2(devnull.fileno(), 0)
    os.execvp(cmd, [cmd, *args])


if __name__ == "__main__":
    main()
