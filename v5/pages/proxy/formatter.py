import time
import uuid
import random
import string
from collections.abc import Iterable
from itertools import zip_longest

def py_join(separator: str, *values) -> str:
    """
    将多个值用分隔符连接成字符串。
    如果某个值是列表或元组，会将其展开。
    """
    final_values = []
    for v in values:
        if isinstance(v, (list, tuple)):
            final_values.extend(map(str, v))
        else:
            final_values.append(str(v))
    return separator.join(final_values)


def py_zip_join(inner_separator: str, *iterables) -> list:
    """
    将多个可迭代对象按元素配对，然后用内部连接符连接。
    返回一个由连接后的字符串组成的列表。
    """
    valid_iterables = [it for it in iterables if isinstance(it, Iterable) and not isinstance(it, str)]
    zipped = zip_longest(*valid_iterables, fillvalue='')
    return [inner_separator.join(map(str, items)) for items in zipped]


def get_date_cn():
    """获取中文格式的日期时间"""
    return time.strftime("%Y年%m月%d日 %H:%M:%S")


def get_datetime():
    """获取 YYYY-MM-DD HH:MM:SS 格式的日期时间"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def get_date():
    """获取 YYYY-MM-DD 格式的日期"""
    return time.strftime("%Y-%m-%d")


def get_time():
    """获取 HH:MM:SS 格式的时间"""
    return time.strftime("%H:%M:%S")


def get_timestamp_s():
    """获取秒级时间戳"""
    return str(int(time.time()))


def get_timestamp_ms():
    """获取毫秒级时间戳"""
    return str(int(time.time() * 1000))


def get_uuid():
    """生成一个UUID"""
    return str(uuid.uuid4())


def get_rand_int():
    """生成一个0-99999之间的随机整数"""
    return str(random.randint(0, 99999))


def get_rand_str(length: int):
    """
    生成指定长度的随机字符串（字母和数字）。
    为了更灵活，我们将 rand_str_8 和 rand_str_16 合并成一个函数。
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def get_rand_hex(length: int):
    """生成指定长度的随机十六进制字符串"""
    return ''.join(random.choices('0123456789abcdef', k=length))



def formatter(script_string: str, packet_data: any):
    """
    使用 exec() 执行一段复杂的Python脚本字符串来处理传入的数据。

    【安全警告】: 此函数使用 exec()，功能强大但存在安全风险。
    请确保 `script_string` 的来源100%可信（例如，由您自己或团队成员编写）。
    绝不要执行来自不可信用户或外部来源的脚本。

    :param script_string: 一个包含任意Python代码的字符串。脚本应将最终结果赋给名为 'result' 的变量。
    :param packet_data: 抓包获取的数据，将在脚本中作为 'data' 变量使用。
    :return: 脚本执行后，'result'变量的值。
    """
    # --- 搭建执行环境 ---
    script_context = {
        "__builtins__": {
            'str': str, 'int': int, 'len': len, 'zip': zip, 'list': list,
            'tuple': tuple, 'dict': dict, 'set': set, 'max': max, 'min': min,
            'sum': sum, 'range': range, 'isinstance': isinstance, 'print': print
        },
        # 暴露我们所有的“内置函数”
        'join': py_join,
        'zip_join': py_zip_join,
        'date_cn': get_date_cn,
        'datetime': get_datetime,
        'date': get_date,
        'time': get_time,
        'timestamp_s': get_timestamp_s,
        'timestamp_ms': get_timestamp_ms,
        'uuid': get_uuid,
        'rand_int': get_rand_int,
        'rand_str': get_rand_str,
        'rand_hex': get_rand_hex,
        # 为了方便，将原始的13个函数名也映射进来
        'rand_str_8': lambda: get_rand_str(8),
        'rand_str_16': lambda: get_rand_str(16),
        'rand_hex_16': lambda: get_rand_hex(16),

        # 暴露传入的数据
        "data": packet_data,

        # 预留一个用于接收结果的变量
        "result": None
    }

    try:
        # 使用 exec 执行整个脚本
        exec(script_string, script_context)
        # 从上下文字典中取出结果
        final_output = script_context.get('result', '')
        return str(final_output)

    except Exception as e:
        # 捕获并报告脚本中的任何错误
        return f"[EXECUTION ERROR: {type(e).__name__}: {e}]"



if __name__ == '__main__':
    # 模拟一次抓包获取的数据
    sample_packet_data = {
        "request_id": get_uuid(),
        "url": "https://api.example.com/v1/users",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "MyApp/1.0"
        },
        "body": [
            {"id": 101, "name": "Alice", "tags": ["vip", "active"]},
            {"id": 102, "name": "Bob", "tags": ["inactive"]},
            {"id": 103, "name": "Charlie", "tags": ["vip", "new"]}
        ]
    }

    print("--- 示例数据 ---")
    import json

    print(json.dumps(sample_packet_data, indent=2))
    print("-" * 50)

    # --- 示例脚本1：简单的信息提取和格式化 ---
    script1 = """
# 提取请求ID和所有用户名
req_id = data['request_id']
names = [user['name'] for user in data['body']]
# 使用内置的 'join' 函数格式化输出
result = f"Request {req_id} processed users: {join(', ', names)}"
"""

    output1 = formatter(script1, sample_packet_data)
    print("【示例1: 提取用户名】")
    print(f"脚本:\n{script1}")
    print(f"输出:\n{output1}\n" + "-" * 50)

    # --- 示例脚本2：使用 'zip_join' 和其他内置函数 ---
    script2 = """
# 假设我们想为每个用户生成一个随机密码和报告时间
names = [user['name'] for user in data['body']]
passwords = [rand_str(8) for _ in names]
report_time = date_cn()
# 使用 zip_join 组合成报告
report_lines = zip_join(' | ', ('Name', *names), ('Password', *passwords))
result = f"--- User Passwords Report ---\\nTime: {report_time}\\n" + "\\n".join(report_lines)
"""
    output2 = formatter(script2, sample_packet_data)
    print("【示例2: 生成报告】")
    print(f"脚本:\n{script2}")
    print(f"输出:\n{output2}\n" + "-" * 50)

    # --- 示例脚本3：处理纯文本数据 ---
    text_data = "item1,item2,item3\\nitemA,itemB,itemC"
    script3 = """
# 对纯文本进行处理
lines = data.split('\\n')
first_line_items = lines[0].split(',')
result = f"First item of first line is: {first_line_items[0]}"
"""
    output3 = formatter(script3, text_data)
    print("【示例3: 处理纯文本】")
    print(f"脚本:\n{script3}")
    print(f"输入: {text_data!r}")
    print(f"输出:\n{output3}\n" + "-" * 50)

    # --- 示例脚本4：演示错误处理 ---
    script4 = "result = data['non_existent_key']"
    output4 = formatter(script4, sample_packet_data)
    print("【示例4: 错误处理】")
    print(f"脚本:\n{script4}")
    print(f"输出:\n{output4}\n" + "-" * 50)