import os
import re
import json
import time
from datetime import datetime, timezone, timedelta
import requests

# ==========================================
# 1. 核心配置与渠道
# ==========================================
API_KEY = os.getenv("twitterapi_io_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")

FEISHU_TEST_URL = os.getenv("FEISHU_WEBHOOK_URL")
FEISHU_MAIN_URL = os.getenv("FEISHU_WEBHOOK_URL_1")
JIJYUN_URL = os.getenv("JIJYUN_WEBHOOK_URL")
TEST_MODE = os.getenv("TEST_MODE_ENV", "false").lower() == "true"

BASE_URL = "https://api.twitterapi.io"
NOW_UTC = datetime.now(timezone.utc)
SINCE_24H = NOW_UTC - timedelta(days=1)
SINCE_TS = int(SINCE_24H.timestamp())
SINCE_DATE_STR = SINCE_24H.strftime("%Y-%m-%d")

AI_KEYWORDS = ["ai", "llm", "agent", "model", "gpt", "release", "inference", "open-source", "agi", "claude", "openai"]

def normalize(name):
    return name.replace("@", "").strip().lower()

# ==========================================
# 2. 动态读取名单
# ==========================================
def load_dynamic_targets():
    accounts = set()
    for filename in ["whales.txt", "experts.txt"]:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                for line in f:
                    u = normalize(line)
                    if u and not u.startswith("#"): accounts.add(u)
    return accounts

TARGET_SET = load_dynamic_targets()

# ==========================================
# 3. 核心清洗与打分
# ==========================================
def unify_schema(t):
    author_obj = t.get("author", {})
    author_handle = normalize(author_obj.get("userName", "unknown"))
    created_at = t.get("createdAt", "")
    try:
        created_ts = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
    except: created_ts = 0

    return {
        "id": str(t.get("id", "None")),
        "text": t.get("text", ""),
        "author": author_handle,
        "created_ts": created_ts,
        "likes": int(t.get("likeCount", 0)),
        "replies": int(t.get("replyCount", 0)),
        "quotes": int(t.get("quoteCount", 0)),
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
        if t["author"] in TARGET_SET: score += 50
        if any(kw in text_lower for kw in AI_KEYWORDS): score += 30
        
        # 降噪：过滤纯长度 & 严惩群聊
        clean_text = re.sub(r'https?://\S+|@\w+', '', text_lower).strip()
        if len(clean_text) < 15: score -= 50
        if t["text"].count('@') > 5: score -= 100
            
        t["score"] = max(0, score)
        if t["score"] > 0 or t["likes"] > 15: unique_tweets[t_id] = t
            
    scored_list = sorted(unique_tweets.values(), key=lambda x: x["score"], reverse=True)
    author_counts = {}
    final_capped = []
    for t in scored_list:
        if author_counts.get(t["author"], 0) < 3: # 防止单人刷屏
            final_capped.append(t)
            author_counts[t["author"]] = author_counts.get(t["author"], 0) + 1
            
    return final_capped[:75] # 扩大漏斗，总共保留 Top 75

# ==========================================
# 4. Grok 分析与推送分发模块
# ==========================================
def analyze_with_grok(feed_text):
    print("\n🧠 正在呼叫 Grok (xAI) 进行深度研报分析...")
    if not XAI_API_KEY:
        return "❌ 无法生成分析报告：未找到 XAI_API_KEY 环境变量。"

    system_prompt = """你是一个专注硅谷前沿AI科技的一级市场VC合伙人。
请根据提供的推特动态（分为具有深度评论的Tier 1和提供宏观背景的Tier 2），写一份不超过800字的情报分析报告。
要求：
1. 一针见血，少说废话，不要复述推文。
2. 重点提炼“圈内新共识”、“底层技术分歧”和“早期投资信号”。
3. 语气专业、犀利。使用Markdown格式排版。"""

    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"以下是过去24小时的高价值推特情报：\n\n{feed_text}"}
        ],
        "temperature": 0.4
    }

    try:
        resp = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ Grok API 调用失败: {e}")
        return f"❌ Grok 生成报告失败。\n抓取的原始数据已保存。\n错误信息: {e}"

def push_to_channels(content):
    if not content.strip(): return
    webhook_url = FEISHU_TEST_URL if TEST_MODE else FEISHU_MAIN_URL
    if webhook_url:
        print(f"📡 正在推送分析报告至飞书 ({'测试模式' if TEST_MODE else '正式模式'})...")
        payload = {"msg_type": "post", "content": {"post": {"zh_cn": {
            "title": "🤖 硅谷 AI 叙事动态 (Grok 提炼版)",
            "content": [[{"tag": "text", "text": content}]]
        }}}}
        requests.post(webhook_url, json=payload)
    if JIJYUN_URL:
        print("📡 正在推送分析报告至微信通道...")
        requests.post(JIJYUN_URL, json={"content": content[:2000]})

# ==========================================
# 5. 主程序
# ==========================================
def main():
    if not API_KEY or not TARGET_SET:
        print("❌ 错误: 未配置 API KEY 或本地名单为空"); return

    print(f"🚀 开始抓取 {len(TARGET_SET)} 位核心节点的最新动态...")
    all_raw = []
    acc_list = list(TARGET_SET)
    for i in range(0, len(acc_list), 15):
        chunk = acc_list[i:i+15]
        # 原创抓取
        q1 = "(" + " OR ".join([f"from:{a}" for a in chunk]) + f") since:{SINCE_DATE_STR} -filter:retweets"
        d1 = requests.get(f"{BASE_URL}/twitter/tweet/advanced_search", headers={"X-API-Key": API_KEY}, params={"query": q1, "queryType": "Latest"}).json()
        if d1 and d1.get("tweets"):
            for t in d1["tweets"]:
                ct = unify_schema(t)
                if ct["created_ts"] >= SINCE_TS: all_raw.append(ct)
                
        # 外部高赞回响抓取
        q2 = "(" + " OR ".join([f"@{a}" for a in chunk]) + f") since:{SINCE_DATE_STR} min_faves:15 -filter:replies"
        d2 = requests.get(f"{BASE_URL}/twitter/tweet/advanced_search", headers={"X-API-Key": API_KEY}, params={"query": q2, "queryType": "Top"}).json()
        if d2 and d2.get("tweets"):
            for t in d2["tweets"]:
                ct = unify_schema(t)
                if ct["created_ts"] >= SINCE_TS: all_raw.append(ct)
        time.sleep(1)

    top_feed = score_and_filter(all_raw)
    
    # 🎯 分层架构：Tier 1 (Top 15 带评论) vs Tier 2 (Next 60 纯文本)
    tier_1 = top_feed[:15]
    tier_2 = top_feed[15:75]

    report_text = f"=== X AI Sector Watch ({SINCE_DATE_STR}) ===\n\n"
    
    report_text += "【Tier 1: 核心冲突与深度回响 (Top 15)】\n"
    for t in tier_1:
        # 对 Top 15 钻取深度评论
        d3 = requests.get(f"{BASE_URL}/twitter/tweet/replies", headers={"X-API-Key": API_KEY}, params={"tweetId": t["id"]}).json()
        if d3 and d3.get("tweets"):
            replies = sorted([unify_schema(r) for r in d3["tweets"]], key=lambda x: x["likes"], reverse=True)
            t["deep_replies"] = replies[:3]
        
        report_text += f"[评分:{t['score']}] @{t['author']}: {t['text'].replace(chr(10), ' ')}\n"
        for r in t["deep_replies"]:
            if r["text"].strip():
                report_text += f"   └─ [高赞回响 @{r['author']}]: {r['text'].replace(chr(10), ' ')}\n"
        report_text += "\n"

    report_text += "【Tier 2: 大盘风向标 (背景噪音)】\n"
    for t in tier_2:
        report_text += f"@{t['author']}: {t['text'].replace(chr(10), ' ')}\n"

    # 💾 落地保存为记忆账本与原始素材
    os.makedirs("data", exist_ok=True)
    with open("clean_feed_for_llm.txt", "w", encoding="utf-8") as f: 
        f.write(report_text)
        
    daily_snapshot_name = f"data/memory_{SINCE_DATE_STR}.json"
    with open(daily_snapshot_name, "w", encoding="utf-8") as f:
        json.dump(top_feed, f, ensure_ascii=False, indent=2)

    # 🧠 送给 Grok 分析并获取最终研报
    final_report = analyze_with_grok(report_text)
    
    # 📡 推送大模型生成的专业研报
    push_to_channels(final_report)
    print("✅ 任务完美收官！")

if __name__ == "__main__": main()
