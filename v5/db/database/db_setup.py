import json
import random
import re
import string

from v5.core.utils import get_db_path
from v5.db.database.db_client import db_client

"""
US:PHONE_LENGTH = 电话长度
US:CA:LENGTH = ca州所有电话的长度
US:CA:0 = (847) 316
US:CA:1 = (847) 317
US:STATE

CA:PHONE_LENGTH
CA:0

"""
# with open(r"C:\Users\Administrator\Desktop\TechFusion\tools\json\UserName.json",'r',encoding="utf-8") as f:
#     data = json.loads(f.read())
# from diskcache import Cache
# yyy = Cache(r"C:\Users\Administrator\Desktop\SynthBox\v2\db\database\username")
# # for country,datas in data.items():
# #     if country == "uk":
# #         country="US"
# #     for key,value in datas.items():
# #         if key == "fc":
# #             yyy[f"{country.upper()}:FIRSTNAME:LENGTH"] =  value+1
# #         elif key == "lc":
# #             yyy[f"{country.upper()}:LASTNAME:LENGTH"] =  value+1
# #         elif key == "firstname":
# #             for i in range(len(value)):
# #                 yyy[f"{country.upper()}:FIRSTNAME:{i}"] =  value[str(i)]
# #         elif key == "lastname":
# #             for i in range(len(value)):
# #                 yyy[f"{country.upper()}:LASTNAME:{i}"] =  value[str(i)]
#
# us_first_name_length = yyy[f"KR:FIRSTNAME:LENGTH"]
# us_last_name_length = yyy[f"KR:LASTNAME:LENGTH"]
# for _ in range(10000):
#     firstname = yyy[f"KR:FIRSTNAME:{random.randint(0,us_first_name_length-1)}"]
#     lastname = yyy[f"KR:LASTNAME:{random.randint(0,us_last_name_length-1)}"]
#     print(firstname,lastname)
