import hmac
import hashlib
import time
import ntplib
from datetime import datetime, timezone

from v5.core.utils import get_network_time_ntp

SECRET_KEY = b"A$(*#&^(BNaw(SYF(*A&g)we(*R#@^*(HFef*(&#@@*R(Y*!@#$%"


def create_short_license_key(days_valid: int) -> str:
    """
    使用HMAC创建一个简短的、包含过期时间的许可证密钥。
    Args:
        days_valid (int): 许可证的有效天数。
    Returns:
        str: 一个32个字符的许可证密钥。
    """
    expiration_timestamp = int(time.time()) + (days_valid * 24 * 60 * 60)
    ts_hex = format(expiration_timestamp, "08x")
    signer = hmac.new(SECRET_KEY, ts_hex.encode("utf-8"), hashlib.sha256)
    signature_part = signer.hexdigest()[:24]
    key = f"{ts_hex}{signature_part}"
    formatted_key = f"{key[0:8]}-{key[8:16]}-{key[16:24]}-{key[24:32]}"
    expiration_dt = datetime.fromtimestamp(expiration_timestamp, tz=timezone.utc)
    print(f"过期时间 (UTC): {expiration_dt.isoformat()}")

    return formatted_key.upper()


def validate_short_license_key(key: str) -> dict | None:
    """
    在您的客户端应用中验证这个简短的许可证密钥。
    这个函数需要 SECRET_KEY 硬编码在您的应用中。

    Args:
        key (str): 用户输入的许可证密钥。

    Returns:
        dict: 如果密钥有效且未过期，则返回包含过期时间信息的字典。
              否则返回 None。
    """
    cleaned_key = key.replace("-", "").lower()
    if len(cleaned_key) != 32:
        return {"msg": "验证失败: 密钥长度不正确。"}

    ts_hex = cleaned_key[:8]
    signature_part_from_key = cleaned_key[8:]

    signer = hmac.new(SECRET_KEY, ts_hex.encode("utf-8"), hashlib.sha256)
    expected_signature_part = signer.hexdigest()[:24]

    # 4. 比较签名是否一致 (使用 hmac.compare_digest 防止时序攻击)
    if not hmac.compare_digest(signature_part_from_key, expected_signature_part):
        return {"msg": "验证失败: 密钥无效或被篡改。"}

    # 5. 签名验证通过，现在检查时间戳是否过期
    try:
        expiration_timestamp = int(ts_hex, 16)
        current_timestamp = get_network_time_ntp()
        if not current_timestamp:
            return {"msg": "无法验证时间，请检查您的网络连接或防火墙设置。"}
        if current_timestamp > expiration_timestamp:
            exp_dt = datetime.fromtimestamp(expiration_timestamp, tz=timezone.utc)
            return {"msg": f"验证失败: 许可证已于 {exp_dt.isoformat()} 过期。"}

        # 验证成功！
        expiration_datetime = datetime.fromtimestamp(expiration_timestamp, tz=timezone.utc)
        return {
            "expiration_iso": expiration_datetime.isoformat(),
            "expiration_timestamp": expiration_timestamp,
            "msg": "许可证有效",
        }

    except ValueError:
        return {"msg": "验证失败: 密钥格式错误。"}


if __name__ == "__main__":
    license_key = create_short_license_key(days_valid=30)
    print(f"生成的32位许可证: {license_key}")

    print("\n" + "=" * 50 + "\n")

    print("--- 模拟客户端验证 ---")
    user_input_key = license_key  # 模拟用户输入了正确的key
    # user_input_key = "67C792F5-1A2B3C4D-5E6F7A8B-9C0D1E2F" # 模拟一个错误的key

    validation_result = validate_short_license_key(user_input_key)
    if validation_result:
        print("验证成功！")
        print(f"许可证信息: {validation_result}")
    else:
        print("验证失败。")
