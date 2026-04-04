import os
import glob
import json
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ==========================================
# 1. 渠道配置
# ==========================================
FEISHU_MAIN_URL = os.getenv("FEISHU_WEBHOOK_URL_1") 
FEISHU_TEST_URL = os.getenv("FEISHU_WEBHOOK_URL") 
JIJYUN_URL = os.getenv("JIJYUN_WEBHOOK_URL")
TEST_MODE = os.getenv("TEST_MODE_ENV", "false").lower() == "true"

def normalize(name):
    return name.replace("@", "").strip().lower()

def push_to_channels(content):
    if not content.strip(): return
    webhook_url = FEISHU_TEST_URL if TEST_MODE else FEISHU_MAIN_URL
    if webhook_url:
        payload = {"msg_type": "post", "content": {"post": {"zh_cn": {
            "title": "⚖️ 硅谷情报局：半月度名单自动换血报告",
            "content": [[{"tag": "text", "text": content}]]
        }}}}
        requests.post(webhook_url, json=payload)
    if JIJYUN_URL:
        requests.post(JIJYUN_URL, json={"content": content})

# ==========================================
# 2. 核心换血算法
# ==========================================
def main():
    print("🔍 启动半月度名单自动洗牌程序...")
    
    # 1. 读取当前名单
    whales = set()
    experts = set()
    
    if os.path.exists("whales.txt"):
        with open("whales.txt", "r") as f:
            whales = {normalize(line) for line in f if line.strip() and not line.startswith("#")}
            
    if os.path.exists("experts.txt"):
        with open("experts.txt", "r") as f:
            experts = {normalize(line) for line in f if line.strip() and not line.startswith("#")}
            
    current_all = whales | experts
    if not experts:
        print("❌ 未找到 experts.txt，跳过维护。")
        return

    # 2. 扫描过去 15 天的记忆账本
    past_15_days = datetime.now(timezone.utc) - timedelta(days=15)
    memory_files = glob.glob("data/memory_*.json")
    
    internal_scores = defaultdict(int)  # 圈内人得分
    external_scores = defaultdict(int)  # 圈外人得分 (野生大佬)
    
    valid_files_count = 0
    for file_path in memory_files:
        try:
            # 根据文件名 memory_2026-04-03.json 提取日期
            date_str = file_path.split('_')[-1].replace('.json', '')
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
            if file_date >= past_15_days:
                valid_files_count += 1
                with open(file_path, "r", encoding="utf-8") as f:
                    daily_data = json.load(f)
                    
                for t in daily_data:
                    author = normalize(t["author"])
                    score = t.get("score", 0)
                    
                    if author in current_all:
                        internal_scores[author] += score
                    else:
                        external_scores[author] += score
                        
                    # 统计神回复里的外部野生大佬
                    for r in t.get("deep_replies", []):
                        r_author = normalize(r["author"])
                        if r_author not in current_all:
                            external_scores[r_author] += r.get("likes", 0) * 2 # 外部神回复双倍加权
        except Exception as e:
            print(f"⚠️ 跳过无法解析的文件 {file_path}: {e}")

    print(f"📊 共分析了 {valid_files_count} 天的历史数据。")

    # 3. 评选末位淘汰名单 (排除 Whales)
    expert_rank = []
    for exp in experts:
        expert_rank.append((exp, internal_scores.get(exp, 0)))
    
    # 按分数从低到高排序
    expert_rank.sort(key=lambda x: x[1])
    # 选出分数最低的 3 个人（淘汰配额）
    bottom_3 = [x for x in expert_rank[:3] if x[1] < 100] # 分数太低才淘汰
    
    # 4. 评选新贵晋升名单
    # 过滤掉偶然因素，外部账号需要有一定的累计分数
    external_rank = sorted(external_scores.items(), key=lambda x: x[1], reverse=True)
    top_3_new = [x for x in external_rank[:len(bottom_3)] if x[1] > 50]

    # 5. 执行名单换血
    dropped_names = [x[0] for x in bottom_3[:len(top_3_new)]]
    promoted_names = [x[0] for x in top_3_new]
    
    new_experts = (experts - set(dropped_names)) | set(promoted_names)
    
    # 6. 覆盖写入 experts.txt
    if dropped_names or promoted_names:
        with open("experts.txt", "w", encoding="utf-8") as f:
            f.write("# 硅谷情报局动态专家名单 (15日自动更新)\n")
            for exp in sorted(new_experts):
                f.write(f"{exp}\n")
        
        # 组装推送报告
        report = f"🔄 15日周期名单自动洗牌已完成！\n\n"
        report += "📉 【末位淘汰】\n"
        for name, score in bottom_3[:len(top_3_new)]:
            report += f"  ❌ @{name} (周期内总活跃贡献分仅 {score}，已被踢出)\n"
            
        report += "\n📈 【新贵晋升】\n"
        for name, score in top_3_new:
            report += f"  ✨ @{name} (周期内因高频产出优质外部回响被捕获，贡献分 {score}，已收编)\n"
            
        report += f"\n🎯 当前监控底座总人数已重置为: {len(whales) + len(new_experts)} 人。"
    else:
        report = "🔄 15日周期核查完毕。本周期内现有专家表现稳定，无符合淘汰与晋升标准的账号，名单保持不变。"
        
    print(report)
    push_to_channels(report)

if __name__ == "__main__":
    main()
