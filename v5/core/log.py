import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logging(
        app_name: str = "SynthBox",
        log_level: int = logging.INFO,
        log_to_console: bool = False,
        log_to_file: bool = True
):
    """
    配置一个全局的、可轮转的、输出到文件和控制台的日志系统。

    :param app_name: 您的应用名称，将作为日志记录器的名字和日志文件名。
    :param log_level: 日志级别，例如 logging.DEBUG, logging.INFO。
    :param log_to_console: 是否将日志输出到控制台。
    :param log_to_file: 是否将日志输出到文件。
    """

    # 1. 获取我们应用的根日志记录器
    # 使用 getLogger(app_name) 可以创建独立的日志空间，避免干扰其他库的日志
    logger = logging.getLogger(app_name)
    logger.setLevel(log_level)

    # 2. 清理已有的 handlers，防止因重复调用此函数而导致日志重复打印
    if logger.hasHandlers():
        logger.handlers.clear()

    # 3. 定义统一的日志格式
    # 包含时间、线程名、日志记录器名、日志级别和消息
    log_format = logging.Formatter(
        "%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 4. 配置控制台输出
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

    # 5. 配置文件输出，并按天自动轮转
    if log_to_file:
        # 创建一个 logs 文件夹来存放日志
        if not os.path.exists("logs"):
            os.makedirs("logs")

        log_filename = os.path.join("logs", f"{app_name}.log")

        try:
            # 使用 TimedRotatingFileHandler 实现日志按天分割
            # when='midnight' 表示每天午夜进行轮转
            # backupCount=7 表示保留最近7天的日志文件
            # encoding='utf-8' 确保正确处理中文字符
            file_handler = TimedRotatingFileHandler(
                log_filename, when='midnight', interval=1, backupCount=7, encoding='utf-8'
            )
            file_handler.setFormatter(log_format)
            logger.addHandler(file_handler)
        except Exception as e:
            # 如果因为权限等问题无法创建文件，在控制台打印错误
            print(f"错误：无法配置日志文件处理器: {e}")

    # 返回logger实例，方便直接使用
    return logger