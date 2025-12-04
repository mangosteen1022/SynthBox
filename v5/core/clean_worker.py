
from PyQt5.QtCore import QObject, pyqtSignal
from .protocols import ManagedWorker


class CleanupWorker(QObject):
    # 定义一个信号，在所有任务完成后发射
    finished = pyqtSignal()

    def __init__(self, workers_to_clean: dict[str, ManagedWorker]):
        super().__init__()
        self.workers = workers_to_clean

    def run(self):
        """
        执行所有清理任务。这个方法将在一个单独的线程中被调用。
        """
        print("清理线程启动，开始停止所有任务...")

        for key, managed_worker in list(self.workers.items()):
            worker_instance = managed_worker.get('worker')
            if worker_instance:
                print(f"正在停止任务: {key}...")
                try:
                    # 调用协议中定义的 stop 方法
                    worker_instance.stop()
                except Exception as e:
                    print(f"停止任务 {key} 时发生错误: {e}")

        print("所有清理任务已完成。")
        # 发射完成信号
        self.finished.emit()