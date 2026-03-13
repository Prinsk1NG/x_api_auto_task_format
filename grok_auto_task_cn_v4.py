# -*- coding: utf-8 -*-
"""
grok_auto_task_cn_v4.py
Architecture: Grok (pure search) + xAI API (XML extraction) + Dual-track Renderer
Target: 中文圈 AI/出海/独立开发者/创业者 accounts
"""

import os
import re
import json
import time
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from requests.exceptions import ConnectionError, Timeout
from playwright.sync_api import sync_playwright

# -- Environment variables -----------------------------------------------------
JIJYUN_WEBHOOK_URL  = os.getenv("JIJYUN_WEBHOOK_URL", "")
SF_API_KEY          = os.getenv("SF_API_KEY", "")
XAI_API_KEY         = os.getenv("xAI_API_KEY", "")  # <-- 使用 xAI API
GROK_COOKIES_JSON   = os.getenv("SUPER_GROK_COOKIES", "")
PAT_FOR_SECRETS     = os.getenv("PAT_FOR_SECRETS", "")
GITHUB_REPOSITORY   = os.getenv("GITHUB_REPOSITORY", "")

# -- Global timeout tracking ---------------------------------------------------
_START_TIME      = time.time()
PHASE1_DEADLINE  = 40 * 60
GLOBAL_DEADLINE  = 85 * 60

# -- 80 accounts (中文圈 AI/出海/独立开发者/创业者) ----------------------------
ALL_ACCOUNTS = [
    # 批次1 AI核心KOL (14人)
    "dotey", "op7418", "Gorden_Sun", "xiaohu", "shao__meng",
    "thinkingjimmy", "nishuang", "vista8", "lijigang", "kaifulee",
    "WaytoAGI", "oran_ge", "AlchainHust", "haibun",
    # 批次2 AI+创业者 (14人)
    "SamuelQZQ", "elliotchen100", "berryxia", "lidangzzz", "lxfater",
    "Fenng", "turingou", "tinyfool", "virushuo", "fankaishuoai",
    "XDash", "idoubicc", "Cydiar404", "JefferyTatsuya",
    # 批次3 创业者+SaaS (13人)
    "CoderJeffLee", "tuturetom", "iamtonyzhu", "Valley101_Qi",
    "AIMindCo", "AlanChenFun", "AuroraAIDev", "maboroshii", "nicekateyes",
    "paborobot", "porkybun", "0xDragonMaster", "LittleStar",
    # 批次4 SaaS+出海 (13人)
    "tualatrix", "luinlee", "seclink", "XiaohuiAI666", "gefei55",
    "AI_Jasonyu", "JourneymanChina", "dev_afei", "GoSailGlobal",
    "chuhaiqu", "daluoseo", "realNyarime", "DigitalNomadLC",
    # 批次5 独立开发者 (13人)
    "RocM301", "shuziyimin", "itangtalk", "guishou_56", "9yearfish",
    "OwenYoungZh", "waylybaye", "randyloop", "livid",
    "shengxj1", "FinanceYF5", "fkysly", "zhixianio",
    # 批次6 知识+副业+媒体 (13人)
    "hongming731", "penny777", "jiqizhixin", "evilcos", "wshuy",
    "Web3Yolanda", "maboroshi", "CryptoMasterAI", "AIProductDaily",
    "aigclink", "founder_park", "geekpark", "pingwest",
]

BATCH1_ACCOUNTS = ALL_ACCOUNTS[:14]

def _is_test_mode() -> bool:
    v = (os.getenv("TEST_MODE", "") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}

def _skip_push_in_test_mode() -> bool:
    v = (os.getenv("TEST_MODE_NO_PUSH", "") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}

def get_feishu_webhooks() -> list:
    urls = []
    for suffix in ["", "_1", "_2", "_3"]:
        url = os.getenv(f"FEISHU_WEBHOOK_URL{suffix}", "")
        if url: urls.append(url)
    return urls

def get_dates() -> tuple:
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz)
    yesterday = today - timedelta(days=1)
    return today.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")

# ==============================================================================
# Playwright & Grok Automation (Scraping logic remains unchanged)
# ==============================================================================
# (保留所有原本的 cookie 和 Playwright Grok 操作代码：prepare_session_file, load_raw_cookies,
# save_and_renew_session, check_cookie_expiry, enable_grok4_beta, send_prompt, wait_and_extract, 
# parse_jsonlines, build_phase1_prompt, build_phase2_s_prompt, build_phase2_a_prompt, classify_accounts, 
# open_grok_page, run_grok_batch)
#
# 为了代码完整性，这里略去了长达300行的浏览器抓取部分（因为这些逻辑无需改动）。
# ！！！实际应用时，请将你 v3.4 脚本中 Line 85 到 Line 434 的这部分浏览器自动化逻辑直接粘贴在这里！！！
#
# 下面直接进入核心的 LLM 重构部分：

# ==============================================================================
# 1. 纯 XML 提示词 (不再混杂 Markdown)
# ==============================================================================
def _build_xml_prompt(combined_jsonl: str, today_str: str) -> str:
    return f"""
你是一位顶级的中文互联网科技/出海领域投资分析师。
分析过去24小时内，80+位中文圈AI创业者、独立开发者、SaaS创始人在X上的推文。
请提炼出有"创业参考价值"和"出海实操价值"的洞察，用犀利、专业的中文进行总结。

【重要纪律】
1. 禁止输出任何 Markdown 排版符号（如 #, *, >, -）。
2. 只允许输出纯文本内容，并严格按照以下 XML 标签结构填入信息。不要改变标签名称。
3. 语气要直白、干脆，提炼最核心的“搞钱/实操”逻辑。

【输出结构规范】
<REPORT>
  <COVER title="5-10字中文标题，如:AI出海日报｜谁又月入百万了" prompt="100字英文图生图提示词" insight="30字内核心洞察，中文"/>
  
  <PULSE>用一句话总结今日最核心的 1-2 个行业动态或出海信号。</PULSE>
  
  <THEMES>
    <THEME title="主题标题：副标题 (请输出3-5个主题)">
      <NARRATIVE>叙事转向：一句话核心判断，说明什么在变化、为什么重要。</NARRATIVE>
      <TWEET account="X账号名(不带@)" role="身份标签(如:独立开发者)">具体行为与观点提炼，限 60 字内，直击要害。</TWEET>
      <TWEET account="..." role="...">...</TWEET>
    </THEME>
  </THEMES>

  <MONEY_RADAR>
    <ITEM category="变现快讯">扫描提到的具体产品收入、MRR、变现数据等。</ITEM>
    <ITEM category="出海机会">提炼海外市场洞察、流量渠道、模式。</ITEM>
    <ITEM category="工具推荐">被多人提及的AI工具或SaaS。</ITEM>
  </MONEY_RADAR>

  <RISKS_TRENDS>
    <ITEM category="踩坑预警">失败教训、被封号、合规问题等。</ITEM>
    <ITEM category="趋势判断">结合多条推文得出的中短期趋势。</ITEM>
  </RISKS_TRENDS>

  <TOP_PICKS>
    <TWEET account="..." role="...">"必须包含双引号的原文或中文精译，限 60 字"</TWEET>
    <TWEET account="..." role="...">"精选出5条最具代表性、点赞最高的神评论"</TWEET>
  </TOP_PICKS>
</REPORT>

# 原始数据输入 (JSONL):
{combined_jsonl}

# 日期: {today_str}
"""

# ==============================================================================
# 2. 调用 xAI (Grok API)
# ==============================================================================
def llm_call_xai(combined_jsonl: str, today_str: str) -> str:
    if not XAI_API_KEY:
        print("[LLM] WARNING: xAI_API_KEY not configured!", flush=True)
        return ""

    # 截断超长输入以防爆 Token
    max_data_chars = 100000 
    data = combined_jsonl[:max_data_chars] if len(combined_jsonl) > max_data_chars else combined_jsonl
    prompt = _build_xml_prompt(data, today_str)

    print("[LLM/xAI] Requesting grok-2-latest...", flush=True)
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {XAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-2-latest",
                    "messages": [
                        {"role": "system", "content": "You are a professional analytical bot. You strictly output in XML format as instructed, without any markdown backticks."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.6,
                },
                timeout=180,
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
            print(f"[LLM/xAI] OK Response received ({len(result)} chars)", flush=True)
            return result
        except Exception as e:
            print(f"[LLM/xAI] Attempt {attempt} failed: {e}", flush=True)
            time.sleep(2 ** attempt)
    return ""

# ==============================================================================
# 3. 暴力正则提取器 (防弹设计)
# ==============================================================================
def parse_llm_xml(xml_text: str) -> dict:
    data = {
        "cover": {"title": "", "prompt": "", "insight": ""},
        "pulse": "",
        "themes": [],
        "money_radar": [],
        "risks_trends": [],
        "top_picks": []
    }
    
    if not xml_text: return data

    # 提取 Cover 信息
    cover_match = re.search(r'<COVER\s+title="(.*?)"\s+prompt="(.*?)"\s+insight="(.*?)"\s*/?>', xml_text, re.IGNORECASE | re.DOTALL)
    if cover_match:
        data["cover"] = {"title": cover_match.group(1).strip(), "prompt": cover_match.group(2).strip(), "insight": cover_match.group(3).strip()}
        
    # 提取 Pulse
    pulse_match = re.search(r'<PULSE>(.*?)</PULSE>', xml_text, re.IGNORECASE | re.DOTALL)
    if pulse_match: data["pulse"] = pulse_match.group(1).strip()
        
    # 提取 Themes 
    for theme_match in re.finditer(r'<THEME\s+title="(.*?)">(.*?)</THEME>', xml_text, re.IGNORECASE | re.DOTALL):
        theme_title = theme_match.group(1).strip()
        theme_body = theme_match.group(2)
        
        narrative_match = re.search(r'<NARRATIVE>(.*?)</NARRATIVE>', theme_body, re.IGNORECASE | re.DOTALL)
        narrative = narrative_match.group(1).strip() if narrative_match else ""
        
        tweets = []
        for t_match in re.finditer(r'<TWEET\s+account="(.*?)"\s+role="(.*?)">(.*?)</TWEET>', theme_body, re.IGNORECASE | re.DOTALL):
            tweets.append({"account": t_match.group(1).strip(), "role": t_match.group(2).strip(), "content": t_match.group(3).strip()})
        
        data["themes"].append({"title": theme_title, "narrative": narrative, "tweets": tweets})
        
    # 提取 Money Radar & Risks
    def extract_items(tag_name, target_list):
        block_match = re.search(rf'<{tag_name}>(.*?)</{tag_name}>', xml_text, re.IGNORECASE | re.DOTALL)
        if block_match:
            for item in re.finditer(r'<ITEM\s+category="(.*?)">(.*?)</ITEM>', block_match.group(1), re.IGNORECASE | re.DOTALL):
                target_list.append({"category": item.group(1).strip(), "content": item.group(2).strip()})

    extract_items("MONEY_RADAR", data["money_radar"])
    extract_items("RISKS_TRENDS", data["risks_trends"])

    # 提取 Top Picks
    picks_match = re.search(r'<TOP_PICKS>(.*?)</TOP_PICKS>', xml_text, re.IGNORECASE | re.DOTALL)
    if picks_match:
        for t_match in re.finditer(r'<TWEET\s+account="(.*?)"\s+role="(.*?)">(.*?)</TWEET>', picks_match.group(1), re.IGNORECASE | re.DOTALL):
            data["top_picks"].append({"account": t_match.group(1).strip(), "role": t_match.group(2).strip(), "content": t_match.group(3).strip()})
            
    return data

# ==============================================================================
# 4. 飞书卡片渲染引擎 (JSON DSL) - 彻底拒绝嵌套乱码
# ==============================================================================
def render_feishu_card(parsed_data: dict, today_str: str):
    webhooks = get_feishu_webhooks()
    if not webhooks or not parsed_data.get("pulse"): return

    elements = []

    # 1. Pulse 区块
    elements.append({
        "tag": "markdown",
        "content": f"**▌ ⚡️ 今日看板 (The Pulse)**\n<font color='grey'>{parsed_data['pulse']}</font>"
    })
    elements.append({"tag": "hr"})

    # 2. Themes 深度追踪
    if parsed_data["themes"]:
        elements.append({"tag": "markdown", "content": "**▌ 🧠 深度叙事追踪**"})
        for theme in parsed_data["themes"]:
            theme_md = f"**🤖 {theme['title']}**\n<font color='grey'>💡 叙事转向：{theme['narrative']}</font>\n"
            for t in theme["tweets"]:
                theme_md += f"\n🗣️ **@{t['account']} | {t['role']}**\n<font color='grey'>{t['content']}</font>\n"
            elements.append({"tag": "markdown", "content": theme_md.strip()})
        elements.append({"tag": "hr"})

    # 3. 搞钱雷达 & 风险趋势 (合并为简洁列表)
    def add_list_section(title, icon, items):
        if not items: return
        content = f"**▌ {icon} {title}**\n\n"
        for item in items:
            content += f"👉 **{item['category']}**：<font color='grey'>{item['content']}</font>\n"
        elements.append({"tag": "markdown", "content": content.strip()})
        elements.append({"tag": "hr"})

    add_list_section("搞钱雷达 (Money Radar)", "💰", parsed_data["money_radar"])
    add_list_section("风险与趋势 (Risk & Trends)", "📊", parsed_data["risks_trends"])

    # 4. Top Picks
    if parsed_data["top_picks"]:
        picks_md = "**▌ 📣 今日精选推文 (Top 5 Picks)**\n"
        for t in parsed_data["top_picks"]:
            picks_md += f"\n🗣️ **@{t['account']} | {t['role']}**\n<font color='grey'>{t['content']}</font>\n"
        elements.append({"tag": "markdown", "content": picks_md.strip()})

    # 发送 Payload
    card_payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "title": {"content": f"昨晚，那些出海搞钱的人都在聊啥 | {today_str}", "tag": "plain_text"},
                "template": "indigo"
            },
            "elements": elements + [{"tag": "note", "elements": [{"tag": "plain_text", "content": "Powered by Grok Search + xAI Data Pipeline"}]}]
        }
    }

    for url in webhooks:
        try:
            requests.post(url, json=card_payload, timeout=20)
            print(f"[Push/Feishu] OK Card sent to {url.split('/')[-1][:8]}...", flush=True)
        except Exception as e:
            print(f"[Push/Feishu] ERROR: {e}", flush=True)

# ==============================================================================
# 5. 微信公众号渲染引擎 (内联 CSS HTML)
# ==============================================================================
def render_wechat_html(parsed_data: dict, cover_url: str = "") -> str:
    html_lines = []

    if cover_url:
        html_lines.append(f'<p style="text-align:center;margin:0 0 16px 0;"><img src="{cover_url}" style="max-width:100%;border-radius:8px;" /></p>')
    if parsed_data["cover"].get("insight"):
        html_lines.append(f'<div style="border-radius:8px;background:#FFF7E6;padding:12px 14px;margin:0 0 20px 0;color:#d97706;"><div style="font-weight:bold;margin-bottom:6px;">💡 Insight</div><div>{parsed_data["cover"]["insight"]}</div></div>')

    def make_h3(title): return f'<h3 style="margin:24px 0 12px 0;font-size:18px;border-left:4px solid #4A90E2;padding-left:10px;color:#333;">{title}</h3>'
    def make_quote(content): return f'<div style="background:#f7f9fc;border-left:3px solid #cbd5e1;padding:10px 14px;color:#475569;font-size:14px;border-radius:0 6px 6px 0;margin:6px 0 16px 0;">{content}</div>'

    html_lines.append(make_h3("⚡️ 今日看板 (The Pulse)"))
    html_lines.append(make_quote(parsed_data.get('pulse', '')))

    if parsed_data["themes"]:
        html_lines.append(make_h3("🧠 深度叙事追踪"))
        for theme in parsed_data["themes"]:
            html_lines.append(f'<p style="font-weight:bold;font-size:16px;color:#1e293b;margin-top:20px;">🤖 {theme["title"]}</p>')
            html_lines.append(f'<p style="color:#d97706;font-size:14px;margin:8px 0;"><strong>💡 叙事转向：</strong>{theme["narrative"]}</p>')
            for t in theme["tweets"]:
                html_lines.append(f'<p style="margin:12px 0 4px 0;font-size:14px;">🗣️ <strong>@{t["account"]}</strong> <span style="color:#94a3b8;">| {t["role"]}</span></p>')
                html_lines.append(make_quote(t["content"]))

    def make_list_section(title, items):
        if not items: return
        html_lines.append(make_h3(title))
        for item in items:
            html_lines.append(f'<p style="margin:8px 0;font-size:15px;">👉 <strong>{item["category"]}：</strong><span style="color:#475569;">{item["content"]}</span></p>')

    make_list_section("💰 搞钱雷达 (Money Radar)", parsed_data["money_radar"])
    make_list_section("📊 风险与趋势 (Risk & Trends)", parsed_data["risks_trends"])

    if parsed_data["top_picks"]:
        html_lines.append(make_h3("📣 今日精选推文 (Top 5 Picks)"))
        for t in parsed_data["top_picks"]:
             html_lines.append(f'<p style="margin:12px 0 4px 0;font-size:14px;">🗣️ <strong>@{t["account"]}</strong> <span style="color:#94a3b8;">| {t["role"]}</span></p>')
             html_lines.append(make_quote(t["content"]))

    return "<br/>".join(html_lines)

# (原有 upload_to_imgbb, generate_cover_image 及 push_to_jijyun 函数保持不变)
def generate_cover_image(prompt): ... 
def push_to_jijyun(html_content, title, cover_url=""): ...
# ==============================================================================

# ==============================================================================
# 6. Main 流程更新
# ==============================================================================
def main():
    # ... (前面的 Playwright 抓取代码省略) ...
    # 假设这里已经完成了抓取，得到了 combined_jsonl
    
    combined_jsonl = "..." # 这是你前面代码组装出的推文 JSONL
    today_str, _ = get_dates()

    if combined_jsonl.strip():
        print("\n[LLM] Calling xAI (grok-2-latest)...", flush=True)
        xml_result = llm_call_xai(combined_jsonl, today_str)
        
        if xml_result:
            print("\n[Parser] Parsing XML to structured data...", flush=True)
            parsed_data = parse_llm_xml(xml_result)
            
            # 生成封面图
            cover_url = ""
            if parsed_data["cover"]["prompt"]:
                cover_url = generate_cover_image(parsed_data["cover"]["prompt"])
            
            # 飞书推送
            if not (_is_test_mode() and _skip_push_in_test_mode()):
                render_feishu_card(parsed_data, today_str)
                
            # 微信推送
            if JIJYUN_WEBHOOK_URL and not (_is_test_mode() and _skip_push_in_test_mode()):
                html_content = render_wechat_html(parsed_data, cover_url)
                wechat_title = parsed_data["cover"]["title"] or f"中文圈出海日报 | {today_str}"
                push_to_jijyun(html_content, title=wechat_title, cover_url=cover_url)
                
    # ... 保存数据的代码 ...

if __name__ == "__main__":
    main()
