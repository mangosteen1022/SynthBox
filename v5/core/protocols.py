from typing import Protocol, TypedDict, NotRequired


class Stoppable(Protocol):
    """
    定义了一个“可停止”对象的协议。
    任何实现了 stop() 方法和 isRunning() 方法的类，都满足此协议。
    """
    def stop(self) -> None:
        pass

    def start(self):
        pass


class ManagedWorker(TypedDict):
    worker: Stoppable|None
    config: dict
    status: NotRequired[str]
    del_flag: NotRequired[bool]