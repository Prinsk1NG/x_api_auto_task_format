# -*- coding: utf-8 -*-
"""
x_api_auto_task_xai_xml.py  v14.1 (全链路监控 + 万能日期解析版)
Architecture: TwitterAPI.io -> PPLX/Tavily -> xAI SDK (Reasoning) + Memory Bank
"""

import os
import re
import json
import time
import base64
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from requests.exceptions import ConnectionError, Timeout

# 🚨 引入官方 xAI SDK
from xai_sdk import Client
from xai_sdk.chat import user, system

TEST_MODE = os.getenv("TEST_MODE_ENV", "false").lower() == "true"

# ── 环境变量配置 ──────────────────────────────
SF_API_KEY          = os.getenv("SF_API_KEY", "")
XAI_API_KEY         = os.getenv("XAI_API_KEY", "")    
IMGBB_API_KEY       = os.getenv("IMGBB_API_KEY", "") 

PPLX_API_KEY        = os.getenv("PPLX_API_KEY", "")
TWITTERAPI_IO_KEY   = os.getenv("twitterapi_io_KEY", "")

TAVILY_KEYS = []
for suffix in ["", "_2", "_3", "_4", "_5"]:
    tk = os.getenv(f"TAVILY_API_KEY{suffix}")
    if tk and tk.strip(): TAVILY_KEYS.append(tk.strip())

def get_random_tavily_key():
    if not TAVILY_KEYS: return ""
    return random.choice(TAVILY_KEYS)

def D(b64_str):
    return base64.b64decode(b64_str).decode("utf-8")

URL_SF_IMAGE   = D("aHR0cHM6Ly9hcGkuc2lsaWNvbmZsb3cuY24vdjEvaW1hZ2VzL2dlbmVyYXRpb25z")
URL_IMGBB      = D("aHR0cHM6Ly9hcGkuaW1nYmIuY29tLzEvdXBsb2Fk")

# ── 基础配置与时间窗 ──────────────────────────────
BASE_URL = "https://api.twitterapi.io"
NOW_UTC = datetime.now(timezone.utc)
SINCE_24H = NOW_UTC - timedelta(days=1)
SINCE_TS = int(SINCE_24H.timestamp())
SINCE_DATE_STR = SINCE_24H.strftime("%Y-%m-%d")

# 🚨 动态读取外部名单系统
def load_account_list(filename):
    if not os.path.exists(filename): return []
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip().replace("@", "").lower() for line in f if line.strip() and not line.strip().startswith("#")]

WHALE_ACCOUNTS = load_account_list("whales.txt")
EXPERT_ACCOUNTS = load_account_list("experts.txt")

if TEST_MODE:
    WHALE_ACCOUNTS = WHALE_ACCOUNTS[:2]
    EXPERT_ACCOUNTS = EXPERT_ACCOUNTS[:4]

TARGET_SET = set(WHALE_ACCOUNTS + EXPERT_ACCOUNTS)

# ── 渠道分发逻辑 ──────────────────────────────
def get_feishu_webhooks() -> list:
    urls = []
    if TEST_MODE:
        url = os.getenv("FEISHU_WEBHOOK_URL", "")
        if url: urls.append(url)
    else:
        for suffix in ["", "_1", "_2", "_3"]:
            url = os.getenv(f"FEISHU_WEBHOOK_URL{suffix}", "")
            if url: urls.append(url)
    return urls

def get_wechat_webhooks() -> list:
    urls = []
    for key in ["JIJYUN_WEBHOOK_URL", "OriSG_WEBHOOK_URL", "OriCN_WEBHOOK_URL"]:
        url = os.getenv(key, "")
        if url: urls.append(url)
    return urls

def get_dates() -> tuple:
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz)
    yesterday = today - timedelta(days=1)
    return today.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")


# ==============================================================================
# 🎯 V14.1 万能数据清洗与打分引擎
# ==============================================================================
AI_KEYWORDS = ["ai", "llm", "agent", "model", "gpt", "release", "inference", "open-source", "agi", "claude", "openai"]

def unify_schema(t):
    author_obj = t.get("author", {})
    if isinstance(author_obj, str):
        author_handle = author_obj
    else:
        author_handle = author_obj.get("userName", "unknown")
    author_handle = author_handle.replace("@", "").strip().lower()

    # 🚨 极其关键的万能日期解析机制
    created_at = t.get("createdAt", t.get("created_at", ""))
    created_ts = 0
    if created_at:
        try:
            # 格式 1: ISO 标准 (2023-10-10T20:19:24.000Z)
            created_ts = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
        except Exception:
            try:
                # 格式 2: Twitter 原生格式 (Thu Apr 06 15:28:43 +0000 2023)
                created_ts = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").timestamp()
            except Exception:
                print(f"⚠️ [日期解析失败] 碰到未知时间格式，该推文可能会被丢弃: {created_at}", flush=True)

    return {
        "id": str(t.get("id", t.get("tweet_id", "None"))),
        "text": t.get("text", t.get("full_text", "")),
        "author": author_handle,
        "created_ts": created_ts,
        "likes": int(t.get("likeCount", t.get("favorite_count", 0))),
        "replies": int(t.get("replyCount", t.get("reply_count", 0))),
        "quotes": int(t.get("quoteCount", t.get("quote_count", 0))),
        "deep_replies": []
    }

def score_and_filter(tweets):
    unique_tweets = {}
    for t in tweets:
        t_id = t["id"]
        if not t_id or t_id == "None": continue
        if t_id in unique_tweets: continue
            
        score = t["likes"] * 1.0 + t["replies"] * 2.0 + t["quotes"] * 3.0
        text_lower = t["text"].lower()
        if t["author"] in WHALE_ACCOUNTS: score += 500
        elif t["author"] in EXPERT_ACCOUNTS: score += 50
        
        if any(kw in text_lower for kw in AI_KEYWORDS)