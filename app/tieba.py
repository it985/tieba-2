#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   tieba.py
@Time    :   2023-01-28 15:54:11
@Author  :   yikoyu
@Version :   1.0
@Desc    :   百度贴吧自动签到
"""

import asyncio
import copy
import hashlib
import logging
import os
import random
import time

import httpx

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# API接口的URL
LIKIE_URL = "http://c.tieba.baidu.com/c/f/forum/like"  # 获取用户关注贴吧的接口
TBS_URL = "http://tieba.baidu.com/dc/common/tbs"       # 获取tbs值的接口
SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"   # 贴吧签到接口

ENV = os.environ  # 获取系统环境变量

# 请求头部
HEADERS = {
    "Host": "tieba.baidu.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36",
}

# 签到数据的基本信息
SIGN_DATA = {
    "_client_type": "2",
    "_client_version": "9.7.8.0",
    "_phone_imei": "000000000000000",
    "model": "MI+5",
    "net_type": "1",
}

# 常量定义
COOKIE = "Cookie"
BDUSS = "BDUSS"
EQUAL = r"="
EMPTY_STR = r""
TBS = "tbs"
PAGE_NO = "page_no"
ONE = "1"
TIMESTAMP = "timestamp"
DATA = "data"
FID = "fid"
SIGN_KEY = "tiebaclient!!!"
UTF8 = "utf-8"
SIGN = "sign"
KW = "kw"

client = httpx.AsyncClient()  # 创建一个异步HTTP客户端实例

def get_tbs(bduss):
    """获取tbs值的函数"""
    logger.info("获取tbs开始")
    headers = copy.copy(HEADERS)  # 复制请求头
    headers.update({COOKIE: EMPTY_STR.join([BDUSS, EQUAL, bduss])})  # 更新头部信息，添加Cookie
    try:
        # 请求获取tbs值
        tbs = httpx.get(url=TBS_URL, headers=headers, timeout=5).json()[TBS]
    except Exception as e:
        logger.error("获取tbs出错 %s", e)  # 记录错误日志
        logger.info("重新获取tbs开始")
        tbs = httpx.get(url=TBS_URL, headers=headers, timeout=5).json()[TBS]  # 再次请求获取tbs值
    logger.info("获取tbs结束")
    return tbs  # 返回tbs值

def get_favorite(bduss):
    """获取用户关注的贴吧列表"""
    logger.info("获取关注的贴吧开始")
    returnData = {"forum_list": {"non-gconforum": [], "gconforum": []}}  # 初始化返回数据
    i = 1
    while True:
        data = {
            "BDUSS": bduss,
            "_client_id": "wappc_1534235498291_488",
            "from": "1008621y",
            "page_no": str(i),
            "page_size": "200",
            "timestamp": str(int(time.time())),
            "vcode_tag": "11",
            **SIGN_DATA,
        }
        data = encodeData(data)  # 对请求数据进行加密处理

        try:
            res = httpx.post(url=LIKIE_URL, data=data, timeout=5).json()  # 发送请求获取数据
        except Exception as e:
            logger.error("获取关注的贴吧出错 %s", e)  # 记录错误日志
            break  # 遇到错误时退出循环

        if "forum_list" not in res or "has_more" not in res or res["has_more"] != "1":
            break  # 如果没有更多数据，退出循环
        
        if "non-gconforum" in res["forum_list"]:
            returnData["forum_list"]["non-gconforum"].extend(res["forum_list"]["non-gconforum"])
        if "gconforum" in res["forum_list"]:
            returnData["forum_list"]["gconforum"].extend(res["forum_list"]["gconforum"])

        i += 1  # 进入下一页

    t = []
    for key in ["non-gconforum", "gconforum"]:
        for i in returnData["forum_list"][key]:
            if isinstance(i, list):
                for j in i:
                    if isinstance(j, list):
                        for k in j:
                            t.append(k)
                    else:
                        t.append(j)
            else:
                t.append(i)
                
    logger.info("获取关注的贴吧结束")
    return t  # 返回整理后的贴吧列表

def encodeData(data):
    """对请求数据进行加密处理"""
    s = EMPTY_STR
    keys = data.keys()
    for i in sorted(keys):
        s += i + EQUAL + str(data[i])  # 按照键的字典序拼接数据
    sign = hashlib.md5((s + SIGN_KEY).encode(UTF8)).hexdigest().upper()  # 生成MD5签名
    data.update({SIGN: str(sign)})  # 将签名添加到数据中
    return data

async def client_sign(bduss, tbs, fid, kw):
    """执行签到操作"""
    logger.info("开始签到贴吧：" + kw)
    data = copy.copy(SIGN_DATA)  # 复制签到数据
    data.update(
        {BDUSS: bduss, FID: fid, KW: kw, TBS: tbs, TIMESTAMP: str(int(time.time()))}
    )
    data = encodeData(data)  # 对请求数据进行加密处理
    res = await client.post(url=SIGN_URL, data=data, timeout=5)  # 发送签到请求
    return res.json()  # 返回响应的JSON数据

def main():
    """主函数"""
    if "BDUSS" not in ENV:
        logger.error("未配置 BDUSS")  # 检查环境变量中是否配置了BDUSS
        raise ValueError("BDUSS not configure")

    b = ENV["BDUSS"].split("#")  # 从环境变量中获取BDUSS，并按#分割成多个值

    loop = asyncio.new_event_loop()  # 创建新的事件循环
    asyncio.set_event_loop(loop)  # 设置事件循环

    for n, i in enumerate(b):
        logger.info("开始签到第" + str(n) + "个用户" + i)  # 记录当前正在签到的用户
        tbs = get_tbs(i)  # 获取当前用户的tbs
        favorites = get_favorite(i)  # 获取当前用户关注的贴吧
        
        # 记录关注的贴吧总数
        total_favorites = len(favorites)
        logger.info(f"用户 {i} 关注的贴吧总数: {total_favorites}")
        
        success_count = 0  # 成功签到计数器
        for j in favorites:
            await asyncio.sleep(10)  # 每签到一个贴吧后休息10秒
            result = await client_sign(i, tbs, j["id"], j["name"])  # 执行签到操作
            
            # 检查签到是否成功
            if result.get("error_code") == "0":  # 根据实际返回结果判断是否签到成功
                success_count += 1
                logger.info(f"成功签到贴吧: {j['name']}")
            else:
                logger.error(f"签到失败: {j['name']} - 错误码: {result.get('error_code')}")

        logger.info(f"完成第{n}个用户签到，成功签到 {success_count} 个贴吧，共 {total_favorites} 个关注的贴吧")

    logger.info("所有用户签到结束")  # 记录所有用户签到完成
    loop.close()  # 关闭事件循环

if __name__ == "__main__":
    main()  # 调用主函数，开始执行脚本
