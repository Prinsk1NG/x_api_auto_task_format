import os
import re
import json
import time
from datetime import datetime, timezone, timedelta
import requests

# ==========================================
# 1. 核心配置与 106 人大名单
# ==========================================
API_KEY = "new1_94023baadd1942f6badf5b8ef7e12c0d"
BASE_URL = "https://api.twitterapi.io"

# 严格的 24 小时时间窗 (UTC)
NOW_UTC = datetime.now(timezone.utc)
SINCE_24H = NOW_UTC - timedelta(days=1)
SINCE_TS = int(SINCE_24H.timestamp())
SINCE_DATE_STR = SINCE_24H.strftime("%Y-%m-%d")

AI_KEYWORDS = ["ai", "llm", "agent", "model", "gpt", "release", "inference", "open-source", "agi", "claude", "openai"]

TARGET_ACCOUNTS = [
    "elonmusk", "sama", "gregbrockman", "pmarca", "lexfridman",
    "karpathy", "demishassabis", "darioamodei", "OpenAI", "AnthropicAI", 
    "GoogleDeepMind", "xAI", "AIatMeta", "GoogleAI", "MSFTResearch", 
    "IlyaSutskever", "GaryMarcus", "rowancheung", "clmcleod", "bindureddy", 
    "dotey", "oran_ge", "vista8", "imxiaohu", "Sxsyer", 
    "K_O_D_A_D_A", "tualatrix", "linyunqiu", "garywong", "web3buidl", 
    "AI_Era", "AIGC_News", "jiangjiang", "hw_star", "mranti", 
    "nishuang", "a16z", "ycombinator", "lightspeedvp", "sequoia", 
    "foundersfund", "eladgil", "bchesky", "chamath", "paulg", 
    "TheInformation", "TechCrunch", "verge", "WIRED", "Scobleizer", 
    "bentossell", "HuggingFace", "MistralAI", "Perplexity_AI", "GroqInc", 
    "Cohere", "TogetherCompute", "runwayml", "Midjourney", "StabilityAI", 
    "Scale_AI", "CerebrasSystems", "tenstorrent", "weights_biases", "langchainai", 
    "llama_index", "supabase", "vllm_project", "huggingface_hub", "nvidia", 
    "AMD", "Intel", "SKhynix", "tsmc", "magicleap", 
    "NathieVR", "PalmerLuckey", "ID_AA_Carmack", "boz", "rabovitz", 
    "htcvive", "XREAL_Global", "RayBan", "MetaQuestVR", "PatrickMoorhead", 
    "jeffdean", "chrmanning", "hardmaru", "goodfellow_ian", "feifeili", 
    "_akhaliq", "promptengineer", "AI_News_Tech", "siliconvalley", "aithread", 
    "aibreakdown", "aiexplained", "aipubcast", "hubermanlab", "swyx",
    "Dylan522p", "lilianweng", "JohnSchulman2", "nottombrown", "simonw", "soumithchintala"
]

def normalize(name):
    return name.replace("@", "").strip().lower()

TARGET_SET = {normalize(acc) for acc in TARGET_ACCOUNTS}

# ==========================================
# 2. 核心清洗函数 (基于你的探针结果)
# ==========================================
def unify_schema(t):
    """
    针对 twitterapi.io 真实返回的字段名进行提取
    顶层字段: ['id', 'text', 'likeCount', 'replyCount', 'createdAt', 'author'...]
    """
    author_obj = t.get("author", {})
    author_handle = normalize(author_obj.get("userName", "unknown"))
    
    # 提取时间并转为 timestamp
    created_at = t.get("createdAt", "")
    try:
        # 兼容 ISO 格式 "2026-04-03T20:00:00.000Z"
        created_ts = datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp()
    except:
        created_ts = 0

    return {
        "id": str(t.get("id", "None")),
        "text": t.get("text", ""),
        "author": author_handle,
        "created_ts": created_ts,
        "likes": int(t.get("likeCount", 0)),
        "replies": int(t.get("replyCount", 0)),
        "quotes": int(t.get("quoteCount", 0)),
        "is_reply": bool(t.get("isReply")),
        "deep_replies": []
    }

def score_and_filter(tweets):
    print("\n🧠 [Processing] 执行去重、打分与单人限流...")
    unique_tweets = {}
    
    for t in tweets:
        t_id = t["id"]
        if not t_id or t_id == "None": continue
        if t_id in unique_tweets: continue
            
        score = t["likes"] * 1.0 + t["replies"] * 2.0 + t["quotes"] * 3.0
        text_lower = t["text"].lower()
        
        # 权重加成
        if t["author"] in TARGET_SET: score += 50
        if any(kw in text_lower for kw in AI_KEYWORDS): score += 30
        
        # --- 🚨 强化版惩罚机制 (解决群聊噪音) ---
        # 1. 过滤掉 @ 符号和 URL 后的纯文本长度
        clean_text = re.sub(r'https?://\S+', '', text_lower)
        clean_text = re.sub(r'@\w+', '', clean_text).strip()
        
        if len(clean_text) < 15: score -= 50
        
        # 2. 如果推文里 @ 的人数超过 5 个，极大概率是垃圾群聊，重罚
        if t["text"].count('@') > 5: score -= 100
            
        t["score"] = max(0, score)
        
        # 仅保留正分或点赞极高的
        if t["score"] > 0 or t["likes"] > 15:
            unique_tweets[t_id] = t
            
    # 单人限流与最终排序
    scored_list = sorted(unique_tweets.values(), key=lambda x: x["score"], reverse=True)
    
    author_counts = {}
    final_capped = []
    for t in scored_list:
        if author_counts.get(t["author"], 0) < 3:
            final_capped.append(t)
            author_counts[t["author"]] = author_counts.get(t["author"], 0) + 1
            
    return final_capped[:20]

# ==========================================
# 3. 网络请求模块 (保持 Stage 1, 2, 3 逻辑)
# ==========================================
def safe_request(endpoint, params):
    url = f"{BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, headers={"X-API-Key": API_KEY}, params=params, timeout=20)
        if resp.status_code == 200: return resp.json()
        print(f"  [API Error] {resp.status_code}")
    except Exception as e:
        print(f"  [Network Error] {e}")
    return None

def fetch_pipeline():
    all_raw = []
    
    # Stage 1: 原创
    print("\n🚀 [Stage 1] 分组搜索原创...")
    acc_list = list(TARGET_SET)
    for i in range(0, len(acc_list), 15):
        chunk = acc_list[i:i+15]
        query = "(" + " OR ".join([f"from:{a}" for a in chunk]) + f") since:{SINCE_DATE_STR} -filter:retweets"
        data = safe_request("/twitter/tweet/advanced_search", {"query": query, "queryType": "Latest"})
        if data and "tweets" in data:
            for t in data["tweets"]:
                ct = unify_schema(t)
                if ct["created_ts"] >= SINCE_TS: all_raw.append(ct)
        time.sleep(1)

    # Stage 2: 回响
    print("\n📡 [Stage 2] 搜索高赞提及...")
    for i in range(0, len(acc_list), 15):
        chunk = acc_list[i:i+15]
        query = "(" + " OR ".join([f"@{a}" for a in chunk]) + f") since:{SINCE_DATE_STR} min_faves:15 -filter:replies"
        data = safe_request("/twitter/tweet/advanced_search", {"query": query, "queryType": "Top"})
        if data and "tweets" in data:
            for t in data["tweets"]:
                ct = unify_schema(t)
                if ct["created_ts"] >= SINCE_TS: all_raw.append(ct)
        time.sleep(1)

    # 打分过滤
    top_feed = score_and_filter(all_raw)

    # Stage 3: 钻取评论
    print("\n⛏️ [Stage 3] 钻取前 10 条话题的深度评论...")
    for t in top_feed[:10]:
        data = safe_request("/twitter/tweet/replies", {"tweetId": t["id"]})
        if data and "tweets" in data:
            replies = [unify_schema(r) for r in data["tweets"]]
            replies.sort(key=lambda x: x["likes"], reverse=True)
            t["deep_replies"] = replies[:3]
        time.sleep(1)
        
    return top_feed

def main():
    final_data = fetch_pipeline()
    
    # 导出文件
    print("\n💾 导出 clean_feed_for_llm.txt...")
    with open("clean_feed_for_llm.txt", "w", encoding="utf-8") as f:
        for t in final_data:
            f.write(f"【{t['score']}分】 @{t['author']}: {t['text'].replace(chr(10), ' ')}\n")
            f.write(f"   ❤️ {t['likes']} | 💬 {t['replies']}\n")
            for r in t["deep_replies"]:
                if r["text"].strip():
                    f.write(f"   └─ [回响 @{r['author']} ❤️ {r['likes']}]: {r['text'].replace(chr(10), ' ')}\n")
            f.write("\n")
    print("✅ 任务完成！")

if __name__ == "__main__":
    main()
