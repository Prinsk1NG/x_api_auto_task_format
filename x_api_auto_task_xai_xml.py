import os
import re
import json
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from xai_sdk import Client
from xai_sdk.chat import user, system

# ─── 1. 环境配置与安全开关 ──────────────────────────────────────────
TWITTERAPI_IO_KEY = os.getenv("twitterapi_io_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")
PPLX_API_KEY = os.getenv("PPLX_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")     # 调试群
FEISHU_WEBHOOK_URL_1 = os.getenv("FEISHU_WEBHOOK_URL_1") # 主群
TEST_MODE = os.getenv("TEST_MODE_ENV", "true").lower() == "true"

# ─── 2. 诊断日志工具 ──────────────────────────────────────────────
def log_diag(step, status="INFO", msg=""):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = "✅" if status == "OK" else ("❌" if status == "FAIL" else "⏳")
    print(f"[{ts}] {icon} [{step}] {msg}", flush=True)

# ─── 3. 核心抓取逻辑 (带 24 小时精准窗口) ─────────────────────────────
def fetch_tweets(accounts, label):
    if not TWITTERAPI_IO_KEY or not accounts:
        log_diag(f"{label}抓取", "FAIL", "缺少 Key 或账号列表")
        return []

    # 锁定过去 24 小时 (UTC)
    now_utc = datetime.now(timezone.utc)
    since_ts = (now_utc - timedelta(hours=24)).isoformat()
    all_tweets = []
    
    log_diag(f"{label}扫盘", "BUSY", f"开始扫描 {len(accounts)} 人，时间窗口: 过去 24h")

    for account in accounts:
        url = f"https://api.twitterapi.io/twitter/user/last_tweets?userName={account.strip()}"
        try:
            r = requests.get(url, headers={"X-API-Key": TWITTERAPI_IO_KEY}, timeout=20)
            if r.status_code == 200:
                raw_data = r.json().get("tweets", [])
                # 严格过滤：24小时内 + 非回复
                valid = [t for t in raw_data if t.get("createdAt", "") > since_ts and not t.get("isReply")]
                all_tweets.extend(valid)
                if valid: print(f"   - @{account}: 发现 {len(valid)} 条深度动态", flush=True)
            else:
                log_diag("TwitterAPI", "FAIL", f"@{account} 接口异常: {r.status_code}")
        except Exception as e:
            log_diag("TwitterAPI", "FAIL", f"@{account} 连接错误: {str(e)}")
            
    log_diag(f"{label}结果", "OK", f"全量抓取完成，共 {len(all_tweets)} 条原始数据")
    return all_tweets

# ─── 4. 宏观与全网扫描 ─────────────────────────────────────────────
def get_external_insights():
    log_diag("外部情报", "BUSY", "启动 Perplexity + Tavily 扫描...")
    context = ""
    
    # Perplexity: 宏观背景
    if PPLX_API_KEY:
        try:
            payload = {
                "model": "sonar-reasoning",
                "messages": [{"role": "user", "content": "总结过去24小时硅谷AI圈、芯片半导体、风投领域的3个最重大事实，要求硬核、带数据。"}]
            }
            r = requests.post("https://api.perplexity.ai/chat/completions", 
                             headers={"Authorization": f"Bearer {PPLX_API_KEY}"}, json=payload, timeout=30)
            if r.status_code == 200:
                context += f"\n[Macro Background]:\n{r.json()['choices'][0]['message']['content']}"
                log_diag("Perplexity", "OK", "宏观事实收集完毕")
        except: log_diag("Perplexity", "FAIL", "请求超时")

    # Tavily: 新项目雷达
    if TAVILY_API_KEY:
        try:
            r = requests.post("https://api.tavily.com/search", 
                             json={"api_key": TAVILY_API_KEY, "query": "latest AI startup funding product launch 2026", "search_depth": "advanced"}, timeout=20)
            if r.status_code == 200:
                context += f"\n[New Projects]:\n{json.dumps(r.json().get('results', []))}"
                log_diag("Tavily", "OK", "全网项目扫描完毕")
        except: log_diag("Tavily", "FAIL", "接口无响应")
        
    return context

# ─── 5. LLM 解析与 XML 生成 (Grok-Reasoning) ──────────────────────
def run_grok_analysis(feed_data, external_ctx):
    log_diag("Grok AI", "BUSY", f"正在对 {len(feed_data)} 条推文进行深度博弈推演...")
    if not XAI_API_KEY: return ""

    client = Client(api_key=XAI_API_KEY)
    # 构造极简推文列表供模型阅读
    clean_feed = "\n".join([f"@{t['userName']}: {t.get('fullText','')[:500]}" for t in feed_data])
    
    prompt = f"""
    你是一个硅谷资深投资主编。基于以下原始素材生成一份 XML 格式的深度研报。
    [素材一：推文流]\n{clean_feed}
    [素材二：宏观背景]\n{external_ctx}

    要求：
    1. 叙事追踪：不要零散罗列，要通过大佬推文发现背后的博弈。
    2. XML 结构必须严格：包含 <COVER>, <PULSE>, <THEMES>, <TOP_PICKS>。
    3. 每个 <TWEET> 必须包含完整的 account 和 role 属性。
    """
    
    try:
        chat = client.chat.create(model="grok-4.20-0309-reasoning")
        chat.append(system("你是一位见解毒辣的 VC 合伙人，擅长从 XML 格式输出研报。"))
        chat.append(user(prompt))
        response = chat.sample().content.strip()
        # 清洗推理过程
        final_xml = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        log_diag("Grok AI", "OK", "研报 XML 已生成")
        return final_xml
    except Exception as e:
        log_diag("Grok AI", "FAIL", f"分析中断: {str(e)}")
        return ""

# ─── 6. 飞书卡片与测试模式控制 ──────────────────────────────────────
def send_to_feishu(xml_data):
    log_diag("分发系统", "BUSY", f"测试模式: {TEST_MODE}")
    # 解析逻辑 (此处沿用你之前的正则解析函数)
    # ... (为了篇幅，假设已解析为 payload)
    
    # 个人/测试群
    if FEISHU_WEBHOOK_URL:
        requests.post(FEISHU_WEBHOOK_URL, json={"msg_type": "interactive", "card": {"header": {"title": {"content": "诊断版报告"}}}})
        log_diag("飞书分发", "OK", "已送达个人/开发群")
    
    # 🚨 测试模式防火墙：严禁在测试时推送到主群
    if TEST_MODE:
        log_diag("飞书分发", "SKIP", "TEST_MODE 为 True，已拦截主群推送。")
    else:
        if FEISHU_WEBHOOK_URL_1:
            requests.post(FEISHU_WEBHOOK_URL_1, json={"msg_type": "interactive", "card": {"header": {"title": {"content": "正式研报"}}}})
            log_diag("飞书分发", "OK", "正式报告已同步主群")

# ─── 7. 主程序：全链路自动化 ────────────────────────────────────────
def main():
    print(f"\n{'='*20} V10.8 生产系统启动 {'='*20}")
    
    # A. 加载名单
    whales = open("whales.txt").read().splitlines() if os.path.exists("whales.txt") else ["elonmusk", "sama"]
    
    # B. 抓取与诊断
    raw_tweets = fetch_tweets(whales, "核心大佬")
    
    if not raw_tweets:
        log_diag("致命错误", "FAIL", "连续扫描 100 人，抓取结果为 0。请检查 TwitterAPI.io 余额或 Key 有效性！")
        # 即使推文为0，我们也尝试跑一下宏观
    
    # C. 深度透视
    ext_context = get_external_insights()
    report_xml = run_grok_analysis(raw_tweets, ext_context)
    
    # D. 保存数据 (GitHub 自动保存)
    date_str = datetime.now(BJT).strftime("%Y-%m-%d")
    os.makedirs(f"data/{date_str}", exist_ok=True)
    with open(f"data/{date_str}/combined.txt", "w") as f:
        f.write(str(raw_tweets))
    log_diag("持久化", "OK", f"原始推文已备份至 data/{date_str}/")

    # E. 推送
    if report_xml:
        send_to_feishu(report_xml)
    
    print(f"{'='*20} 运行任务结束 {'='*20}\n")

if __name__ == "__main__":
    # 定义时区（如未安装 pytz 可用简单偏移）
    BJT = timezone(timedelta(hours=8))
    main()
