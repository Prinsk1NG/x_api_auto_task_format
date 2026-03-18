# -*- coding: utf-8 -*-
"""
x_api_auto_task_xai_xml.py  v13.3 (出海搞钱精修版: 多微信通道推送)
Architecture: TwitterAPI.io -> PPLX -> xAI SDK (Grok-4.20-Multi-Agent) -> Clean UI
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

# ── 环境变量 ──────────────────────────────
SF_API_KEY          = os.getenv("SF_API_KEY", "")
XAI_API_KEY         = os.getenv("XAI_API_KEY", "")    
IMGBB_API_KEY       = os.getenv("IMGBB_API_KEY", "") 

# 🚨 核心双引擎密钥
TWITTERAPI_IO_KEY   = os.getenv("twitterapi_io_KEY", "")
PPLX_API_KEY        = os.getenv("PPLX_API_KEY", "")

def D(b64_str):
    return base64.b64decode(b64_str).decode("utf-8")

URL_SF_IMAGE   = D("aHR0cHM6Ly9hcGkuc2lsaWNvbmZsb3cuY24vdjEvaW1hZ2VzL2dlbmVyYXRpb25z")
URL_IMGBB      = D("aHR0cHM6Ly9hcGkuaW1nYmIuY29tLzEvdXBsb2Fk")

# ── 巨鲸池 (15人)：流量巨大、容易霸屏的大V与媒体
WHALE_ACCOUNTS = [
    "kaifulee", "Fenng", "lidangzzz", "livid", "tualatrix", 
    "nishuang", "tinyfool", "evilcos", "jiqizhixin", "geekpark",
    "sspai_com", "ruanyf", "foxshuo", "pongba", "Svwang1"
]

# ── 专家池 (90+人)：涵盖各大核心领域的高质量信源
EXPERT_ACCOUNTS = list(set([
    "dotey", "op7418", "Gorden_Sun", "xiaohu", "shao__meng", "thinkingjimmy", "goocarlos", 
    "Tumeng05", "AxtonLiu", "haibun", "vista8", "lijigang", "WaytoAGI", "xicilion", 
    "oran_ge", "AlchainHust", "SamuelQZQ", "elliotchen100", "Hayami_kiraa", "berryxia",
    "MANISH1027512", "joshesye", "zstmfhy", "bozhou_ai", "CuiMao", "RookieRicardoR", "wlzh",
    "lxfater", "nateleex", "yan5xu", "santiagoyoungus", "Cydiar404", "JefferyTatsuya", 
    "seclink", "turingou", "virushuo", "fankaishuoai", "XDash", "idoubicc", "CoderJeffLee", 
    "tuturetom", "iamtonyzhu", "hongjun60", "Valley101_Qian", "binghe", "yyyole", "0xkakarot888", "rionaifantasy", "Wujizhuzhu",
    "indie_maker_fox", "HongyuanCao", "nextify2024", "readyfor2025", "weijunext", "yihui_indie", 
    "JinsFavorites", "xiongchun007", "Junyu", "luoleiorg", "Plidezus", "jesselaunz", "lewangx", 
    "luinlee", "yupi996", "servasyy_ai", "XiaohuiAI666", "dingyi", "yanhua1010",
    "gefei55", "lyc_zh", "AI_Jasonyu", "JourneymanChina", "dev_afei", "luobogooooo", 
    "GoSailGlobal", "chuhaiqu", "daluoseo", "hezhiyan7", "imaxichuhai", "canghe", "Nicole_yang88",
    "austinit", "guishou_56", "9yearfish", "benshandebiao", "hwwaanng", "OwenYoungZh", 
    "waylybaye", "randyloop", "shengxj1", "FinanceYF5", "liuyi0922", "fkysly", "zhixianio", "Pluvio9yte",
    "tangjinzhou", "IndieDevHailey", "nopinduoduo",
    "abskoop", "stark_nico99", "hongming731", "penny777", "quarktalksss", "Khazix0918", "steipete", "AI_jacksaku",
    "kasong2048", "cellinlab", "wshuyi", "Francis_YAO_", "realNyarime", "DigitalNomadLC", 
    "RocM301", "EvaCmore", "shuziyimin", "itangtalk", "knowledgefxg", "cj3214567667", "MindfulReturn", "Tz_2022", "EvanWritesX", "yaohui12138",
    "Astronaut_1216", "ityouknows", "expatlevi", "ll777547099", "PandaTalk8", "catmangox", "indiehackercase"
]))

if TEST_MODE:
    WHALE_ACCOUNTS = WHALE_ACCOUNTS[:2]
    EXPERT_ACCOUNTS = EXPERT_ACCOUNTS[:5]

def get_feishu_webhooks() -> list:
    urls = []
    for suffix in ["", "_1", "_2", "_3"]:
        url = os.getenv(f"FEISHU_WEBHOOK_URL{suffix}", "")
        if url: urls.append(url)
    return urls

# 🚨 微信推送多通道路由配置
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

def get_safe_yesterday() -> str:
    try:
        time_resp = requests.get("http://worldtimeapi.org/api/timezone/Asia/Shanghai", timeout=5).json()
        real_today = datetime.fromisoformat(time_resp["datetime"])
        return (real_today - timedelta(days=2)).strftime("%Y-%m-%d")
    except:
        return (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

def parse_twitter_date(date_str):
    try:
        if " " in date_str:
            parts = date_str.split()
            if len(parts) >= 3:
                m_map = {"Jan":"01", "Feb":"02", "Mar":"03", "Apr":"04", "May":"05", "Jun":"06", 
                         "Jul":"07", "Aug":"08", "Sep":"09", "Oct":"10", "Nov":"11", "Dec":"12"}
                mm = m_map.get(parts[1], "01")
                dd = parts[2].zfill(2)
                return f"{mm}{dd}"
    except: pass
    return datetime.now(timezone.utc).strftime("%m%d")

def safe_int(val):
    try:
        if isinstance(val, (int, float)): return int(val)
        v = str(val).lower().replace(',', '')
        if 'k' in v: return int(float(re.search(r'[\d\.]+', v).group()) * 1000)
        if 'm' in v: return int(float(re.search(r'[\d\.]+', v).group()) * 1000000)
        num = re.search(r'\d+', v)
        return int(num.group()) if num else 0
    except:
        return 0

# ==============================================================================
# 🚀 外部情报检索：Perplexity (客观查数机器人)
# ==============================================================================
def fetch_macro_with_perplexity() -> str:
    if not PPLX_API_KEY: return ""
    print("\n🕵️ [宏观新闻官] 呼叫 Perplexity 获取全网硬核数据...", flush=True)
    try:
        prompt = """你是顶级科技与商业分析师。请检索过去 24 小时内全球科技、AI 或商业领域的【硬核客观数据】。
        🚨 最高指令：不要宽泛的行业趋势，只抓取以下两类具体事实，必须带具体媒体或官方来源：
        1. 💰 具体的重磅融资、并购案、或亮眼的公司财报/收入数据。
        2. 🎁 刚刚发布或突然爆火的科技产品、开源项目、或重要硬件（带具体名字和功能）。
        绝对禁止将 "Perplexity" 作为信息来源。"""
        
        headers = {"Authorization": f"Bearer {PPLX_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "sonar-pro", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
        resp = requests.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()["choices"][0]["message"]["content"]
            print(f"  ✅ Perplexity 客观数据收集完毕 ({len(data)} 字)", flush=True)
            return data
    except Exception as e: print(f"  ❌ Perplexity 抛出异常: {e}", flush=True)
    return ""

# ==============================================================================
# 🚀 第一阶段：TwitterAPI.io 原生抓取引擎
# ==============================================================================
def parse_tweets_recursive(data) -> list:
    all_tweets = []
    def recurse(obj):
        if isinstance(obj, dict):
            text = obj.get("full_text") or obj.get("text")
            if not text and obj.get("legacy"): text = obj["legacy"].get("full_text") or obj["legacy"].get("text")
            if text and isinstance(text, str):
                sn = None
                try: sn = obj.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {}).get("screen_name")
                except: pass
                if not sn: sn = obj.get("screen_name")
                if not sn:
                    u = obj.get("user") or obj.get("author") or obj.get("user_info") or {}
                    sn = u.get("screen_name") or u.get("userName") or u.get("username")
                if not sn and obj.get("legacy"): sn = obj["legacy"].get("screen_name")

                t_id = obj.get("rest_id") or obj.get("id_str") or obj.get("id") or obj.get("tweet_id")
                if not t_id and obj.get("legacy"): t_id = obj["legacy"].get("id_str")
                
                fav = obj.get("favorite_count") or obj.get("favorites") or obj.get("likes") or obj.get("like_count") or 0
                if not fav and obj.get("legacy"): fav = obj["legacy"].get("favorite_count", 0)
                
                rep = obj.get("reply_count") or obj.get("replies") or 0
                if not rep and obj.get("legacy"): rep = obj["legacy"].get("reply_count", 0)
                
                created_at = obj.get("created_at")
                if not created_at and obj.get("legacy"): created_at = obj["legacy"].get("created_at", "")
                
                reply_to = obj.get("in_reply_to_screen_name") or obj.get("reply_to") or obj.get("is_reply")
                if not reply_to and obj.get("legacy"): reply_to = obj["legacy"].get("in_reply_to_screen_name")
                
                if str(t_id) and sn:
                    all_tweets.append({
                        "tweet_id": str(t_id), "screen_name": sn, "text": text,
                        "favorites": safe_int(fav), "replies": safe_int(rep), 
                        "created_at": created_at, "reply_to": reply_to,
                    })
            for v in obj.values(): recurse(v)
        elif isinstance(obj, list):
            for item in obj: recurse(item)
    recurse(data)
    seen, unique = set(), []
    for t in all_tweets:
        if t["tweet_id"] not in seen:
            seen.add(t["tweet_id"])
            unique.append(t)
    return unique

def fetch_tweets_twitterapi_io(accounts: list, label: str) -> list:
    if not TWITTERAPI_IO_KEY: 
        print(f"⚠️ 未配置 twitterapi_io_KEY，跳过{label}抓取", flush=True)
        return []
    
    yesterday = get_safe_yesterday()
    all_tweets = []
    print(f"\n⏳ [{label}扫盘] 启动 TwitterAPI.io 点对点扫描，共 {len(accounts)} 人...", flush=True)
    headers = {"X-API-Key": TWITTERAPI_IO_KEY}
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    
    chunk_size = 5
    chunks = [accounts[i:i + chunk_size] for i in range(0, len(accounts), chunk_size)]
    
    for i, chunk in enumerate(chunks, 1):
        print(f"  🔎 挖掘第 {i}/{len(chunks)} 批动态...", flush=True)
        query_str = " OR ".join([f"from:{acc}" for acc in chunk])
        query = f"({query_str}) since:{yesterday} -filter:retweets"
        params = {"query": query, "queryType": "Latest"}
        
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=25)
            if resp.status_code == 200:
                tweets = parse_tweets_recursive(resp.json())
                for t in tweets: t["t"] = parse_twitter_date(t.get("created_at", ""))
                all_tweets.extend(tweets)
                print(f"    ✅ 成功提取 {len(tweets)} 条。")
            else:
                print(f"    ⚠️ HTTP {resp.status_code}")
        except Exception:
            pass
        time.sleep(1) 
        
    return all_tweets

def fetch_global_hot_tweets_twitterapi() -> list:
    if not TWITTERAPI_IO_KEY: return []
    yesterday = get_safe_yesterday()
    all_tweets = []
    
    print(f"\n📡 [全网探测] 扫描全球 X.com 高赞中文神仙打架与突发热点...", flush=True)
    
    queries = [
        f'lang:zh since:{yesterday} min_faves:300 -filter:retweets',
        f'(AI OR 科技 OR 创业 OR 商业 OR 搞钱 OR 独立开发 OR 马斯克 OR 开源) lang:zh since:{yesterday} min_faves:100 -filter:retweets'
    ]
    
    headers = {"X-API-Key": TWITTERAPI_IO_KEY}
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    
    for idx, q in enumerate(queries, 1):
        params = {"query": q, "queryType": "Top"}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=25)
            if resp.status_code == 200:
                tweets = parse_tweets_recursive(resp.json())
                for t in tweets: t["t"] = parse_twitter_date(t.get("created_at", ""))
                all_tweets.extend(tweets)
                print(f"    ✅ 探测策略 {idx} 成功，捕获 {len(tweets)} 条全网中文大V情报。")
        except: pass
        time.sleep(1)
        
    return all_tweets

# ==============================================================================
# 🚀 第二阶段：纯 XML 提示词与大模型调用 (Grok-4.20-Multi-Agent)
# ==============================================================================
def _build_xml_prompt(combined_jsonl: str, today_str: str, macro_info: str) -> str:
    return f"""
你是一个专业的 X（Twitter）话题分析师和出海搞钱圈主编。
目前你搭载了强大的 Multi-Agent 聚类分析能力。请基于下面过去 24 小时的账号更新，自动进行主题聚类。

【核心指令】
1. 挑选出 3~5 个最有趣、最硬核或最有讨论价值的话题作为 <THEMES>。
2. 🚨【吃瓜姿势】：在 <GOSSIP> 中直接写点评内容，绝不要带“吃瓜姿势”等任何前缀！必须严格限制在 30 字以内！
3. 🚨【四选二视角】：对于每个深度追踪的话题，你必须根据内容的真实情况，在“潜在机会、踩坑预警、核心共识、重大分歧”这四个视角中，【任选 1 到 2 个】最契合的角度来写。如果没有突出的观点，千万不要硬编，直接省略该标签。
4. 🚨【拒绝宽泛】：在生成 <MARKET_RADAR> 时，如果说到赛道（比如机器人），必须明确指出具体是哪个细分赛道（如人形机器人、服务型机器人）或哪几家具体公司。绝对不允许写“某某赛道获支持”这种让人摸不到头脑的废话！

【输出结构规范】(必须且只能输出严格的 XML)
<REPORT>
  <COVER title="15-20字极具吸引力的公众号网感爆款标题" prompt="100字英文图生图提示词"/>
  <PULSE>用一句话总结今日最核心的 1-2 个全网科技/出海商业动态信号。</PULSE>
  
  <THEMES>
    <THEME type="new" emoji="🔥">
      <TITLE>话题名称：简短描述</TITLE>
      <NARRATIVE>一句话说明：到底发生了什么、什么在变化</NARRATIVE>
      <TWEET account="X账号名" role="中文身份标签">以中文为主精练大佬的实战言论或爆料</TWEET>
      
      <GOSSIP>直接写专家点评内容，绝不要加任何前缀！必须限制在30字以内！</GOSSIP>
      
      <OPPORTUNITY>潜在机会：具体的红利、赛道方向或搞钱思路</OPPORTUNITY>
      <RISK>踩坑预警：可能面临的失败教训、封号、合规等风险</RISK>
      <CONSENSUS>核心共识：大家一致认同的核心判断</CONSENSUS>
      <DIVERGENCE>重大分歧：争议点或未解之谜</DIVERGENCE>
    </THEME>
  </THEMES>

  <MARKET_RADAR>
    <ITEM category="硬核快讯">重磅融资、财报等客观事实，必须有明确的主体和数字。</ITEM>
    <ITEM category="行业风向">巨头具体动作、极其明确的细分市场洞察。</ITEM>
  </MARKET_RADAR>

  <MONEY_TIPS>
    <ITEM category="搞副业经验">提取大佬分享的副业思路、变现过程或经验。</ITEM>
    <ITEM category="出海实操">海外银行卡、电话卡、网络收费避坑等出海运营经验。</ITEM>
    <ITEM category="实用小工具">被推荐的效率神器、新开源项目或好用的出海工具。</ITEM>
  </MONEY_TIPS>

  <TOP_PICKS>
    <TWEET account="..." role="...">【严禁纯英文】价值最大、最有趣或点赞极高的原味金句（中文精译）</TWEET>
    <TWEET account="..." role="...">...</TWEET>
    <TWEET account="..." role="...">...</TWEET>
    <TWEET account="..." role="...">...</TWEET>
    <TWEET account="..." role="...">...</TWEET>
  </TOP_PICKS>
</REPORT>

# 外部客观数据背景 (Perplexity):
{macro_info if macro_info else "未获取到宏观数据"}

# X平台一手原始数据输入 (绝对主干 JSONL):
{combined_jsonl}

# 日期: {today_str}
"""

def llm_call_xai(combined_jsonl: str, today_str: str, macro_info: str) -> str:
    api_key = XAI_API_KEY.strip()
    if not api_key: return ""

    max_data_chars = 100000 
    data = combined_jsonl[:max_data_chars] if len(combined_jsonl) > max_data_chars else combined_jsonl
    prompt = _build_xml_prompt(data, today_str, macro_info)
    
    model_name = "grok-4.20-multi-agent-beta-0309" 

    print(f"\n[LLM/xAI] Requesting {model_name} via Official xai-sdk...", flush=True)
    client = Client(api_key=api_key)
    
    for attempt in range(1, 4):
        try:
            chat = client.chat.create(model=model_name)
            chat.append(system("You are a professional X (Twitter) topic analyst. You strictly output in XML format as instructed. Do not ignore the translation rules."))
            chat.append(user(prompt))
            result = chat.sample().content.strip()
            
            result = re.sub(r'^`{3}(?:xml|jsonl|json)?\n', '', result, flags=re.MULTILINE)
            result = re.sub(r'^`{3}\n?', '', result, flags=re.MULTILINE)
            
            print(f"[LLM/xAI] OK Response received ({len(result)} chars)", flush=True)
            return result
        except Exception as e:
            print(f"[LLM/xAI] Attempt {attempt} failed: {e}", flush=True)
            time.sleep(2 ** attempt)
    return ""

def parse_llm_xml(xml_text: str) -> dict:
    data = {"cover": {"title": "", "prompt": ""}, "pulse": "", "themes": [], "market_radar": [], "money_tips": [], "top_picks": []}
    if not xml_text: return data

    cover_match = re.search(r'<COVER\s+title=[\'"“”](.*?)[\'"“”]\s+prompt=[\'"“”](.*?)[\'"“”]\s*/?>', xml_text, re.IGNORECASE | re.DOTALL)
    if not cover_match:
        cover_match = re.search(r'<COVER\s+title="(.*?)"\s+prompt="(.*?)"\s*/?>', xml_text, re.IGNORECASE | re.DOTALL)
    if cover_match: 
        data["cover"] = {"title": cover_match.group(1).strip(), "prompt": cover_match.group(2).strip()}
        
    pulse_match = re.search(r'<PULSE>(.*?)</PULSE>', xml_text, re.IGNORECASE | re.DOTALL)
    if pulse_match: data["pulse"] = pulse_match.group(1).strip()
        
    for theme_match in re.finditer(r'<THEME([^>]*)>(.*?)</THEME>', xml_text, re.IGNORECASE | re.DOTALL):
        attrs = theme_match.group(1)
        theme_body = theme_match.group(2)
        
        emoji_m = re.search(r'emoji\s*=\s*[\'"“”](.*?)[\'"“”]', attrs, re.IGNORECASE)
        emoji = emoji_m.group(1).strip() if emoji_m else "🔥"
        
        t_tag = re.search(r'<TITLE>(.*?)</TITLE>', theme_body, re.IGNORECASE | re.DOTALL)
        theme_title = t_tag.group(1).strip() if t_tag else "未命名主题"
            
        narrative_match = re.search(r'<NARRATIVE>(.*?)</NARRATIVE>', theme_body, re.IGNORECASE | re.DOTALL)
        narrative = narrative_match.group(1).strip() if narrative_match else ""
        
        tweets = []
        for t_match in re.finditer(r'<TWEET\s+account=[\'"“”](.*?)[\'"“”]\s+role=[\'"“”](.*?)[\'"“”]>(.*?)</TWEET>', theme_body, re.IGNORECASE | re.DOTALL):
            tweets.append({"account": t_match.group(1).strip(), "role": t_match.group(2).strip(), "content": t_match.group(3).strip()})
        if not tweets:
            for t_match in re.finditer(r'<TWEET\s+account="(.*?)"\s+role="(.*?)">(.*?)</TWEET>', theme_body, re.IGNORECASE | re.DOTALL):
                tweets.append({"account": t_match.group(1).strip(), "role": t_match.group(2).strip(), "content": t_match.group(3).strip()})
        
        # 🚨 暴力清洗“🍉吃瓜：”等前缀，防止重叠
        gossip_match = re.search(r'<GOSSIP>(.*?)</GOSSIP>', theme_body, re.IGNORECASE | re.DOTALL)
        gossip = gossip_match.group(1).strip() if gossip_match else ""
        gossip = re.sub(r'^(🍉\s*)?(吃瓜姿势|吃瓜|专家点评|点评|🔥)[:：]?\s*', '', gossip).strip()

        opp_match = re.search(r'<OPPORTUNITY>(.*?)</OPPORTUNITY>', theme_body, re.IGNORECASE | re.DOTALL)
        opportunity = opp_match.group(1).strip() if opp_match else ""
        
        risk_match = re.search(r'<RISK>(.*?)</RISK>', theme_body, re.IGNORECASE | re.DOTALL)
        risk = risk_match.group(1).strip() if risk_match else ""

        cons_match = re.search(r'<CONSENSUS>(.*?)</CONSENSUS>', theme_body, re.IGNORECASE | re.DOTALL)
        consensus = cons_match.group(1).strip() if cons_match else ""

        div_match = re.search(r'<DIVERGENCE>(.*?)</DIVERGENCE>', theme_body, re.IGNORECASE | re.DOTALL)
        divergence = div_match.group(1).strip() if div_match else ""
        
        data["themes"].append({
            "type": "new", "emoji": emoji, "title": theme_title, "narrative": narrative, "tweets": tweets,
            "gossip": gossip, "opportunity": opportunity, "risk": risk, "consensus": consensus, "divergence": divergence
        })
        
    def extract_items(tag_name, target_list):
        block_match = re.search(rf'<{tag_name}>(.*?)</{tag_name}>', xml_text, re.IGNORECASE | re.DOTALL)
        if block_match:
            for item in re.finditer(r'<ITEM\s+category=[\'"“”](.*?)[\'"“”]>(.*?)</ITEM>', block_match.group(1), re.IGNORECASE | re.DOTALL):
                target_list.append({"category": item.group(1).strip(), "content": item.group(2).strip()})

    extract_items("MARKET_RADAR", data["market_radar"])
    extract_items("MONEY_TIPS", data["money_tips"])

    picks_match = re.search(r'<TOP_PICKS>(.*?)</TOP_PICKS>', xml_text, re.IGNORECASE | re.DOTALL)
    if picks_match:
        picks_content = picks_match.group(1)
        for t_match in re.finditer(r'<TWEET\s+account=[\'"“”](.*?)[\'"“”]\s+role=[\'"“”](.*?)[\'"“”]>(.*?)</TWEET>', picks_content, re.IGNORECASE | re.DOTALL):
            data["top_picks"].append({"account": t_match.group(1).strip(), "role": t_match.group(2).strip(), "content": t_match.group(3).strip()})
        if not data["top_picks"]:
            for t_match in re.finditer(r'<TWEET[^>]*account="(.*?)"[^>]*role="(.*?)"[^>]*>(.*?)</TWEET>', picks_content, re.IGNORECASE | re.DOTALL):
                data["top_picks"].append({"account": t_match.group(1).strip(), "role": t_match.group(2).strip(), "content": t_match.group(3).strip()})
            
    return data

# ==============================================================================
# 🚀 第三阶段：结构化渲染引擎 & 账号复盘数据库
# ==============================================================================
def render_feishu_card(parsed_data: dict, today_str: str):
    webhooks = get_feishu_webhooks()
    if not webhooks or not parsed_data.get("pulse"): return

    elements = []
    elements.append({"tag": "markdown", "content": f"**▌ ⚡️ 今日看板 (The Pulse)**\n<font color='grey'>{parsed_data['pulse']}</font>"})
    elements.append({"tag": "hr"})

    if parsed_data["themes"]:
        elements.append({"tag": "markdown", "content": "**▌ 🧠 深度叙事追踪**"})
        for idx, theme in enumerate(parsed_data["themes"]):
            theme_md = f"**{theme['emoji']} {theme['title']}**\n"
            theme_md += f"<font color='grey'>💡 核心判断：{theme['narrative']}</font>\n"
            
            for t in theme["tweets"]:
                theme_md += f"🗣️ **@{t['account']} | {t['role']}**\n<font color='grey'>“{t['content']}”</font>\n"
            
            if theme.get("gossip"): theme_md += f"<font color='red'>**🍉 吃瓜姿势：**</font> {theme['gossip']}\n"
            if theme.get("opportunity"): theme_md += f"<font color='green'>**🎯 潜在机会：**</font> {theme['opportunity']}\n"
            if theme.get("risk"): theme_md += f"<font color='red'>**⚠️ 踩坑预警：**</font> {theme['risk']}\n"
            if theme.get("consensus"): theme_md += f"<font color='blue'>**🤝 核心共识：**</font> {theme['consensus']}\n"
            if theme.get("divergence"): theme_md += f"<font color='orange'>**⚔️ 重大分歧：**</font> {theme['divergence']}\n"
            
            elements.append({"tag": "markdown", "content": theme_md.strip()})
            if idx < len(parsed_data["themes"]) - 1: elements.append({"tag": "hr"})
        elements.append({"tag": "hr"})

    def add_list_section(title, icon, items):
        if not items: return
        content = f"**▌ {icon} {title}**\n\n"
        for item in items:
            content += f"👉 **{item['category']}**：<font color='grey'>{item['content']}</font>\n"
        elements.append({"tag": "markdown", "content": content.strip()})
        elements.append({"tag": "hr"})

    add_list_section("市场雷达 (Market Radar)", "📈", parsed_data["market_radar"])
    add_list_section("搞钱锦囊 (Money Tips)", "💎", parsed_data["money_tips"])

    if parsed_data["top_picks"]:
        picks_md = "**▌ 📣 今日精选推文 (Top 5 Picks)**\n"
        for t in parsed_data["top_picks"]:
            picks_md += f"\n🗣️ **@{t['account']} | {t['role']}**\n<font color='grey'>\"{t['content']}\"</font>\n"
        elements.append({"tag": "markdown", "content": picks_md.strip()})

    card_payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {"title": {"content": f"出海搞钱的中国人在聊啥 | {today_str}", "tag": "plain_text"}, "template": "blue"},
            "elements": elements + [{"tag": "note", "elements": [{"tag": "plain_text", "content": "Powered by TwitterAPI.io + xAI Multi-Agent"}]}]
        }
    }

    for url in webhooks:
        try:
            requests.post(url, json=card_payload, timeout=20)
            print(f"[Push/Feishu] OK Card sent...", flush=True)
        except Exception as e: print(f"[Push/Feishu] ERROR: {e}", flush=True)

def render_wechat_html(parsed_data: dict, today_str: str, cover_url: str = "") -> str:
    html_lines = []
    if cover_url: html_lines.append(f'<p style="text-align:center;margin:0 0 16px 0;"><img src="{cover_url}" style="max-width:100%;border-radius:8px;" /></p>')
    
    # 🚨 固定的顶部标头：去除冗余的 Insight 描述，只保留清爽的单行日期标题
    header_text = f"💡 出海搞钱的中国人在聊啥 | {today_str}"
    html_lines.append(f'<div style="border-radius:8px;background:#FFF7E6;padding:12px 14px;margin:0 0 20px 0;color:#d97706;"><div style="font-weight:bold;text-align:center;font-size:16px;">{header_text}</div></div>')

    def make_h3(title): return f'<h3 style="margin:24px 0 12px 0;font-size:18px;border-left:4px solid #4A90E2;padding-left:10px;color:#2c3e50;font-weight:bold;">{title}</h3>'
    def make_quote(content): return f'<div style="background:#f8f9fa;border-left:4px solid #8c98a4;padding:10px 14px;color:#555;font-size:15px;border-radius:0 4px 4px 0;margin:6px 0 10px 0;line-height:1.6;">{content}</div>'

    html_lines.append(make_h3("⚡️ 今日看板 (The Pulse)"))
    html_lines.append(make_quote(parsed_data.get('pulse', '')))

    if parsed_data["themes"]:
        html_lines.append(make_h3("🧠 深度叙事追踪"))
        for idx, theme in enumerate(parsed_data["themes"]):
            if idx > 0:
                html_lines.append('<hr style="border:none;border-top:1px solid #cbd5e1;margin:32px 0 24px 0;"/>')

            html_lines.append(f'<p style="font-weight:bold;font-size:16px;color:#1e293b;margin:16px 0 8px 0;">{theme["emoji"]} {theme["title"]}</p>')
            html_lines.append(f'<div style="background:#f8fafc; padding:10px 12px; border-radius:6px; margin:0 0 8px 0; font-size:14px; color:#334155;"><strong>💡 核心判断：</strong>{theme["narrative"]}</div>')
                
            for t in theme["tweets"]:
                html_lines.append(f'<p style="margin:8px 0 2px 0;font-size:14px;font-weight:bold;color:#2c3e50;">🗣️ @{t["account"]} <span style="color:#94a3b8;font-weight:normal;">| {t["role"]}</span></p>')
                html_lines.append(make_quote(f'"{t["content"]}"'))
            
            if theme.get("gossip"): html_lines.append(f'<p style="margin:6px 0; font-size:15px; line-height:1.6; background:#fef2f2; padding: 8px 12px; border-radius: 4px;"><strong style="color:#b91c1c;">🍉 吃瓜姿势：</strong>{theme["gossip"]}</p>')
            if theme.get("opportunity"): html_lines.append(f'<p style="margin:6px 0; font-size:15px; line-height:1.6; background:#f0fdf4; padding: 8px 12px; border-radius: 4px;"><strong style="color:#16a34a;">🎯 潜在机会：</strong>{theme["opportunity"]}</p>')
            if theme.get("risk"): html_lines.append(f'<p style="margin:6px 0; font-size:15px; line-height:1.6; background:#fef2f2; padding: 8px 12px; border-radius: 4px;"><strong style="color:#dc2626;">⚠️ 踩坑预警：</strong>{theme["risk"]}</p>')
            if theme.get("consensus"): html_lines.append(f'<p style="margin:6px 0; font-size:15px; line-height:1.6; background:#eff6ff; padding: 8px 12px; border-radius: 4px;"><strong style="color:#2563eb;">🤝 核心共识：</strong>{theme["consensus"]}</p>')
            if theme.get("divergence"): html_lines.append(f'<p style="margin:6px 0; font-size:15px; line-height:1.6; background:#fff7ed; padding: 8px 12px; border-radius: 4px;"><strong style="color:#ea580c;">⚔️ 重大分歧：</strong>{theme["divergence"]}</p>')

    def make_list_section(title, items):
        if not items: return
        html_lines.append(make_h3(title))
        for item in items: 
            html_lines.append(f'<p style="margin:10px 0;font-size:15px;line-height:1.6;">👉 <strong style="color:#2c3e50;">{item["category"]}：</strong><span style="color:#333;">{item["content"]}</span></p>')

    make_list_section("📈 市场雷达 (Market Radar)", parsed_data["market_radar"])
    make_list_section("💎 搞钱锦囊 (Money Tips)", parsed_data["money_tips"])

    if parsed_data["top_picks"]:
        html_lines.append(make_h3("📣 今日精选推文 (Top 5 Picks)"))
        for t in parsed_data["top_picks"]:
             html_lines.append(f'<p style="margin:12px 0 4px 0;font-size:14px;font-weight:bold;color:#2c3e50;">🗣️ @{t["account"]} <span style="color:#94a3b8;font-weight:normal;">| {t["role"]}</span></p>')
             html_lines.append(make_quote(f'"{t["content"]}"'))

    return "".join(html_lines)

# ==============================================================================
# 附加工具 (生图、图床与多路微信推送)
# ==============================================================================
def generate_cover_image(prompt):
    if not SF_API_KEY or not prompt: return ""
    try:
        resp = requests.post(URL_SF_IMAGE, headers={"Authorization": f"Bearer {SF_API_KEY}", "Content-Type": "application/json"}, json={"model": "black-forest-labs/FLUX.1-schnell", "prompt": prompt, "n": 1, "image_size": "1024x576"}, timeout=60)
        if resp.status_code == 200: return resp.json().get("images", [{}])[0].get("url") or resp.json().get("data", [{}])[0].get("url")
    except: pass
    return ""

def upload_to_imgbb_via_url(sf_url):
    if not IMGBB_API_KEY or not sf_url: return sf_url 
    try:
        img_resp = requests.get(sf_url, timeout=30)
        img_b64 = base64.b64encode(img_resp.content).decode("utf-8")
        upload_resp = requests.post(URL_IMGBB, data={"key": IMGBB_API_KEY, "image": img_b64}, timeout=45)
        if upload_resp.status_code == 200: return upload_resp.json()["data"]["url"]
    except: pass
    return sf_url

# 🚨 新增：支持将微信排版推送到多个配置好的 Webhook 通道
def push_to_wechat(html_content, title, cover_url=""):
    webhooks = get_wechat_webhooks()
    if not webhooks: return
    
    payload = {
        "title": title, 
        "author": "Prinski", 
        "html_content": html_content, 
        "cover_jpg": cover_url
    }
    
    for url in webhooks:
        try: 
            requests.post(url, json=payload, timeout=30)
            print(f"[Push/WeChat] OK Sent to {url.split('//')[-1][:15]}...", flush=True)
        except Exception as e: 
            print(f"  ⚠️ 推送微信(机语)警告: {e}", flush=True)

def save_daily_data(today_str: str, post_objects: list, report_text: str):
    data_dir = Path(f"data/{today_str}")
    data_dir.mkdir(parents=True, exist_ok=True)
    combined_txt = "\n".join(json.dumps(obj, ensure_ascii=False) for obj in post_objects)
    (data_dir / "combined.txt").write_text(combined_txt, encoding="utf-8")
    if report_text: (data_dir / "daily_report.txt").write_text(report_text, encoding="utf-8")

def update_account_stats(final_feed: list, parsed_data: dict):
    stats_file = Path("data/account_stats.json")
    stats = {}
    if stats_file.exists():
        try: stats = json.loads(stats_file.read_text(encoding="utf-8"))
        except: pass
    
    today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    used_accounts = set()
    for theme in parsed_data.get("themes", []):
        for t in theme.get("tweets", []):
            used_accounts.add(t.get("account", "").lower())
    for t in parsed_data.get("top_picks", []):
        used_accounts.add(t.get("account", "").lower())
        
    for t in final_feed:
        acc = t.get("a", "unknown").lower()
        if acc not in stats:
            stats[acc] = {"fetched_days": 0, "total_tweets": 0, "used_in_reports": 0, "last_active": ""}
        stats[acc]["total_tweets"] += 1
        stats[acc]["last_active"] = today_str
        
    for acc in used_accounts:
        acc_clean = acc.replace("@", "")
        if acc_clean in stats:
            stats[acc_clean]["used_in_reports"] += 1
            
    stats_file.parent.mkdir(parents=True, exist_ok=True)
    stats_file.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Stats] 已更新账号质量数据库 (account_stats.json)，记录 {len(used_accounts)} 位今日之星。")

def main():
    print("=" * 60, flush=True)
    mode_str = "测试模式" if TEST_MODE else "全量模式"
    print(f"出海搞钱吃瓜版 v13.3 (多端微信推送版 - {mode_str})", flush=True)
    print("=" * 60, flush=True)
    
    if not TWITTERAPI_IO_KEY:
        print("❌ 致命错误: 未配置 twitterapi_io_KEY，程序无法继续！", flush=True)
        return

    today_str, _ = get_dates()
    all_raw_tweets = []
    
    all_raw_tweets.extend(fetch_tweets_twitterapi_io(WHALE_ACCOUNTS, label="巨鲸"))
    all_raw_tweets.extend(fetch_tweets_twitterapi_io(EXPERT_ACCOUNTS, label="专家"))
    all_raw_tweets.extend(fetch_global_hot_tweets_twitterapi())
    
    if not all_raw_tweets:
        print("⚠️ 未能抓取推文，使用测试数据跳过...", flush=True)
        all_raw_tweets = [{"screen_name": "livid", "text": "刚刚部署了一个新版本的后端，速度快了三倍。", "favorites": 100, "created_at": "0101", "replies": 5}]
        
    all_posts_flat = []
    for t in all_raw_tweets:
        likes = t.get("favorites", 0)
        is_reply = bool(t.get("reply_to"))
        if not is_reply or likes >= 5: 
            all_posts_flat.append({
                "a": t.get("screen_name", "Unknown"), 
                "tweet_id": t.get("tweet_id", ""),
                "l": likes, 
                "r": t.get("replies", 0),
                "t": parse_twitter_date(t.get("created_at", "")), 
                "s": re.sub(r'https?://\S+', '', t.get("text", "")).strip()[:600], 
                "qt": t.get("quote_text", "")[:200]
            })

    all_posts_flat.sort(key=lambda x: x["l"], reverse=True)
    
    lower_whales = set(a.lower() for a in WHALE_ACCOUNTS)
    lower_experts = set(a.lower() for a in EXPERT_ACCOUNTS)
    
    whale_feed, expert_feed, global_feed = [], [], []
    account_counts = {}
    
    for t in all_posts_flat:
        if len(t.get("s", "")) <= 20: continue
        author = t.get("a", "Unknown").lower()
        if account_counts.get(author, 0) >= 3: continue
            
        account_counts[author] = account_counts.get(author, 0) + 1
        
        if author in lower_whales:
            whale_feed.append(t)
        elif author in lower_experts:
            expert_feed.append(t)
        else:
            global_feed.append(t)

    final_feed = whale_feed[:15] + expert_feed[:60] + global_feed[:25]

    combined_jsonl = "\n".join(json.dumps(obj, ensure_ascii=False) for obj in final_feed)
    print(f"\n[Data] 组装完成：{len(final_feed)} 条推文 ready for LLM.")

    macro_info = fetch_macro_with_perplexity()

    if combined_jsonl.strip() or macro_info:
        xml_result = llm_call_xai(combined_jsonl, today_str, macro_info)
        if xml_result:
            print("\n[Parser] Parsing XML to structured data...", flush=True)
            parsed_data = parse_llm_xml(xml_result)
            
            cover_url = ""
            if parsed_data["cover"]["prompt"]:
                sf_url = generate_cover_image(parsed_data["cover"]["prompt"])
                cover_url = upload_to_imgbb_via_url(sf_url) if sf_url else ""
            
            render_feishu_card(parsed_data, today_str)
                
            # 🚨 检查是否配置了微信(机语) Webhooks，如果配置了则循环发送
            wechat_hooks = get_wechat_webhooks()
            if wechat_hooks:
                html_content = render_wechat_html(parsed_data, today_str, cover_url)
                
                base_title = parsed_data["cover"]["title"] or "今日核心动态"
                wechat_title = f"{base_title} | 出海搞钱的中国人在聊啥"
                push_to_wechat(html_content, title=wechat_title, cover_url=cover_url)
                
            save_daily_data(today_str, final_feed, xml_result)
            update_account_stats(final_feed, parsed_data)
            
            print("\n🎉 V13.3 运行完毕！", flush=True)
        else:
            print("❌ LLM 处理失败，任务终止。")

if __name__ == "__main__":
    main()
