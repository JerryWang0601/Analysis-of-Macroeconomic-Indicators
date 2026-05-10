#!/usr/bin/env python3
"""
宏观经济仪表盘 v2.0
多地区（美国/中国/日本/欧元区/全球市场）| 趋势图 | 指标详解
输出：dashboard_日期.html → 浏览器打开
"""
import subprocess, sys, os, json, webbrowser, time
from datetime import datetime, timedelta
from pathlib import Path

IS_WINDOWS  = sys.platform == "win32"
SCRIPT_DIR  = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / ".env_dashboard"

# ═══════════════════════════════════════════════════════════
# 0. 自动安装依赖
# ═══════════════════════════════════════════════════════════
def _pip(pkg):
    cmd = [sys.executable, "-m", "pip", "install", pkg, "-q"]
    if not IS_WINDOWS: cmd.append("--break-system-packages")
    subprocess.check_call(cmd)

for _p, _n in [("requests","requests"), ("yfinance","yfinance")]:
    try: __import__(_n)
    except ImportError: print(f"  安装 {_p}..."); _pip(_p)

import requests, yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore', message='Could not infer format')
warnings.filterwarnings('ignore', category=FutureWarning)

# ═══════════════════════════════════════════════════════════
# 1. 指标定义（名称 / 单位 / 详解 / 信号规则 / PMI参考线）
# ═══════════════════════════════════════════════════════════
IND = {
  "us_cpi":     ("CPI同比",         "%",
    "美国消费者价格指数年化涨幅，衡量通胀最主要的指标。美联储目标是2%。该数据每月由美国劳工统计局（BLS）发布，是市场最关注的经济数据之一，公布当天常引发股债大幅波动。高于预期→美元走强、美债下跌、成长股承压；低于预期→市场押注降息、风险资产上涨。",
    "🟢 <2% 通胀温和 | 🟡 2–3.5% 偏高，关注 | 🔴 >3.5% 过热，加息压力大", None),
  "us_pce":     ("核心PCE同比",     "%",
    "个人消费支出价格指数（剔除食品和能源），是美联储最偏好的通胀指标。相比CPI，PCE会根据消费者购物行为变化动态调整权重，被认为比CPI更能反映真实通胀。美联储2%的通胀目标即以此指标衡量，是利率决策最直接的参考数据。",
    "🟢 <2% 温和 | 🟡 2–3% 偏高 | 🔴 >3% 过热", None),
  "us_rate":    ("联邦基准利率",    "%",
    "美联储设定的银行间隔夜拆借利率，是全球最重要的基准利率。利率上升会传导至房贷、企业贷款等各类信贷成本，压制经济和通胀，同时推高美元、压制新兴市场和股票估值。降息则产生相反效果，刺激扩张。每次FOMC会议（每年8次）后市场反应剧烈。",
    "趋势方向最关键：上行=货币收紧 | 下行=货币宽松 | 关注FOMC点阵图（利率预测）", None),
  "us_t10":     ("10年国债收益率",  "%",
    "美国10年期国债收益率，是全球资产定价的基准锚点，代表市场对未来10年经济和通胀预期。收益率上升→股票估值承压（DCF折现率提高，成长股受损更大）、房贷利率上涨、新兴市场资金外流。若10年收益率低于2年收益率（收益率曲线倒挂），历史上几乎总是衰退的先行信号。",
    "收益率曲线倒挂（10Y<2Y）预示衰退 | 实际收益率=10Y名义-通胀预期，是黄金定价核心", None),
  "us_payroll": ("非农新增就业",    "万人",
    "每月新增非农就业人数，每月第一个周五公布，是美联储双重使命中'充分就业'目标的核心指标。超预期强劲→美联储维持高利率概率上升；大幅不及预期→降息预期升温、债券上涨。月度数据波动大，通常看3个月滚动均值评估趋势。失业率和薪资增速是配套观察指标。",
    "🟢 >20万 强劲 | 🟡 10–20万 正常 | 🔴 <10万 就业市场降温", None),
  "us_gdp":     ("GDP季度增速",     "% 折年率",
    "美国实际GDP环比折年增速，每季度发布初值/修正值/终值。正增长代表经济扩张；连续两个季度负增长=技术性衰退。折年率是将季度增速换算为年化水平（季度增速≈年化值/4）。GDP是落后指标，市场更关注其对政策走向的影响，通常与PMI等先行指标配合解读。",
    "🟢 >2% 健康增长 | 🟡 0–2% 增长放缓 | 🔴 <0% 负增长（衰退风险）", None),
  "us_indpro":  ("工业产出同比",    "%",
    "美国工业生产指数同比变化（涵盖制造业、矿业、电力公用事业），由美联储发布。这是衡量实体经济活动的核心硬数据，与制造业PMI高度相关，但更可靠（PMI是问卷调查，工业产出是实际产出量）。同比正增长说明美国工业在扩张，可能伴随就业改善；负增长则反映制造业衰退。注：原ISM PMI数据已从FRED下架，工业产出是最佳替代。",
    "🟢 >2% 健康增长 | 🟡 0–2% 增长放缓 | 🔴 <0% 工业衰退", None),
  "us_retail":  ("零售销售同比",    "%",
    "美国零售和食品服务销售总额同比变化，是衡量消费者支出最重要的硬数据。消费占美国GDP约70%，零售销售强弱直接关系经济动能。同比强劲→消费者信心高、就业稳定→经济扩张持续；同比走弱→消费者预防性储蓄→警示衰退风险。注意需对比通胀，名义增速扣除通胀后的实际增速才反映真实购买力变化。",
    "🟢 >4% 强劲 | 🟡 0–4% 平稳 | 🔴 <0% 消费萎缩", None),

  "cn_cpi":     ("中国CPI同比",     "%",
    "中国居民消费价格指数同比，由国家统计局发布。中国通胀水平长期偏低，近年甚至出现PPI持续负增长（工业通缩）、CPI接近零的局面，反映内需不足和房地产下行周期。低通胀意味着货币政策有宽松空间（降息降准），利好债市；通缩环境下企业盈利承压，A股整体估值受限。",
    "🟢 1–3% 健康区间 | 🟡 <1% 内需偏弱 | 🔴 <0% 通缩风险 | 🔴 >4% 过热", None),
  "cn_ppi":     ("中国PPI同比",     "%",
    "工业生产者出厂价格指数同比，反映工业品出厂价格变化。中国PPI自2022年下半年起持续负增长（工业通缩），背后是房地产下行、产能过剩、需求疲软三重压力。PPI转正是工业企业利润修复的关键信号，对周期股（钢铁、有色、化工、煤炭）影响直接。PPI与CPI差值（剪刀差）也反映上下游议价能力变化。",
    "🟢 >0% 工业修复 | 🟡 -3–0% 弱势 | 🔴 <-3% 深度通缩", None),
  "cn_gdp":     ("中国GDP季度同比", "%",
    "中国实际GDP季度同比增速，每季度公布。是中国经济整体景气度最综合的指标。'保5%'目标多年来是政策底线，达不到时会触发逆周期调节政策。GDP数据出炉前，市场通常已通过PMI、社融、用电量等高频指标预判，因此发布日波动有限，更多用于确认趋势。",
    "🟢 >5% 完成目标 | 🟡 4–5% 略低于目标 | 🔴 <4% 偏离目标，触发刺激", None),
  "cn_mfg_pmi": ("制造业PMI(NBS)", "点",
    "国家统计局发布的官方制造业PMI，覆盖约3000家制造业企业，偏大型国企。50为荣枯线。中国是全球最大制造业国（约占全球30%），该指标直接影响铁矿石、铜、煤炭等大宗商品价格，以及全球供应链上下游。注意：财新PMI（中小私营企业）与NBS PMI有时出现分歧，提供不同维度参考。",
    "🟢 >50 扩张 | 🔴 <50 收缩 ——— 参考线: 50", 50),
  "cn_svc_pmi": ("非制造业PMI",     "点",
    "国家统计局发布的非制造业商务活动指数，涵盖服务业和建筑业。50为荣枯线。中国服务业占GDP比重已超50%，该指标对消费板块（餐饮、旅游、零售）景气度有直接指示作用。建筑业分项与房地产、基建投资紧密相关，是观察基建发力效果的高频窗口。",
    "🟢 >52 扩张稳健 | 🟡 50–52 弱扩张 | 🔴 <50 收缩 ——— 参考线: 50", 50),
  "cn_lpr":     ("LPR 1年期",       "%",
    "贷款市场报价利率（Loan Prime Rate）1年期，是中国基准贷款利率，由18家银行基于MLF利率报价。每月20日左右公布。LPR下调=降息=货币宽松，对房贷成本（5年期LPR）和企业融资成本均有直接影响。LPR调整往往滞后于MLF调整，市场一般通过MLF变化预判LPR走向。",
    "下调=货币宽松，利好风险资产 | 上调=货币收紧（罕见）", None),
  "cn_market":  ("上证综指",        "点",
    "上海证券交易所综合股价指数（A股），反映中国大陆资本市场整体表现。受政策预期（货币政策、产业政策、监管）、房地产周期、外资北向资金流向影响较大。与美股相关性较低，具有一定分散化价值，但历史上受监管政策不确定性和退市制度影响，长期回报弱于美股。",
    "关注3000点心理关口 | 北向资金净流入/流出是重要情绪信号 | 政策底往往先于市场底", None),
  "cn_hs300":   ("沪深300",         "点",
    "沪深两市市值最大、流动性最好的300只股票组成的指数，是A股核心资产代表（白酒、银行、保险、能源等大蓝筹）。相比上证综指更聚焦优质龙头企业，是机构投资者重要业绩比较基准。沪深300期货（IF）也是A股最重要的衍生品。外资通常主要配置沪深300成分股。",
    "关注沪深300/中证500比价：反映价值股 vs 成长股相对强弱", None),
  "hk_market":  ("恒生指数",        "点",
    "香港恒生指数，成分股以中国大型企业H股（阿里、腾讯等互联网）和金融股为主，是观察中国资产国际定价的重要窗口。同时受美联储利率（港元与美元挂钩，利率被动跟随Fed）和内地经济双重影响。外资对中国资产情绪变化在港股往往比A股更敏感，AH溢价反映两市定价差异。",
    "关注AH溢价（>130%说明A股相对高估）| 恒生科技指数是科技股风向标 | 港元汇率被动跟随美元", None),

  "jp_cpi":     ("日本CPI同比",     "%",
    "日本消费者价格指数同比。日本曾经历近30年通缩与低增长（'失去的三十年'），BOJ因此长期实行超低利率甚至负利率政策。2022年后通胀持续超过2%目标，日本央行历史性地于2024年退出负利率，开启加息周期。日本通胀走势和BOJ政策对全球日元套利交易（Carry Trade）和亚洲货币影响深远。",
    "目标2% | 🟢 1–3% 健康 | ⚪ <0% 通缩（历史常态，已改变）| 持续>3%将加快加息", None),
  "jp_rate":    ("日本政策利率",    "%",
    "日本央行（BOJ）基准政策利率，曾长期处于零利率甚至-0.1%的负利率区间，是全球货币宽松极端案例。2024年开始加息意义重大：日本利率上升→日元套利交易（借低息日元买高息美元资产）平仓→日元升值→全球风险资产承压。BOJ政策转向是2024年以来全球流动性最大的结构性变化之一。",
    "关注BOJ会议声明 | 日元套利交易规模庞大，加息会引发全球资产联动波动", None),
  "jp_market":  ("日经225",         "点",
    "日本最主要的股票指数，涵盖225家大型蓝筹企业（丰田、索尼、软银等）。日元汇率是日经的关键驱动：日元贬值→出口商盈利提升（以美元计价的海外收入换算更多日元）→日经上涨；日元升值→反之。2024年日经突破1989年泡沫顶峰，创历史新高；巴菲特增持日本股票是重要催化剂。",
    "USDJPY走弱（日元升值）往往对应日经下跌 | 外资流入和企业回购推动估值重塑", None),
  "usdjpy":     ("美元/日元",       "JPY",
    "美元兑日元汇率，全球流动性和套利交易的晴雨表。日元是最经典的避险货币，全球市场恐慌时资金回流日本→日元升值（数字下降）。历史上日本财务省会在150以上区间干预汇率（出售外汇储备买入日元），防止日元过度贬值推高进口通胀。数字越大=日元越弱。",
    ">150 日元过弱，干预风险 | 140–150 中性区间 | <130 日元偏强，出口商承压", None),

  "eu_cpi":     ("欧元区CPI同比",   "%",
    "欧元区20国综合通货膨胀率（HICP指数），由Eurostat发布。2022年俄乌冲突引发能源危机，欧元区通胀一度飙升至10.6%历史峰值，ECB随后快速加息500bp。目前通胀逐步回落向2%目标，ECB已开启降息周期。欧洲经济结构性问题（能源转型、去工业化、老龄化）使复苏更为曲折。",
    "🟢 <2.5% 接近目标 | 🟡 2.5–4% 仍偏高 | 🔴 >4% 过热", None),
  "eu_rate":    ("ECB存款利率",     "%",
    "欧洲央行（ECB）存款便利利率，欧元区最核心的政策利率。ECB决策影响欧元汇率（降息→欧元走弱→欧洲出口商受益）、欧元区主权债券收益率和信贷成本。Fed与ECB的利率差值是欧元/美元汇率的核心驱动：ECB利率低于Fed→资金倾向流向美元资产→欧元承压。",
    "ECB利率<Fed利率→欧元倾向贬值 | 关注议息会议前瞻指引 | 欧洲降息早于美国是近期特征", None),
  "eu_market":  ("DAX（德国）",     "点",
    "德国DAX指数，包含40家德国最大上市公司，是欧洲最重要的股票指数。德国以出口导向型制造业（汽车、机械、化工）著称，对中国需求高度依赖（约15%出口到中国）。电动车竞争冲击、俄乌能源危机和制造业空洞化使德国GDP陷入衰退，但DAX因流动性宽松和跨国企业估值支撑反而创历史新高，与基本面出现显著背离。",
    "关注德国制造业PMI和中国经济数据 | DAX表现有时与德国经济基本面背离", None),

  "sp500":      ("标普500",         "点",
    "涵盖500家美国大型上市公司，约占全球股票市值40%，是全球最重要的股票指数基准。三大驱动因素：①企业盈利（EPS增长预期）②美联储政策（利率水平决定折现率）③市场情绪（估值扩张/收缩）。科技'七巨头'（Magnificent 7）近年占标普500市值超30%，集中度风险上升。Shiller CAPE指数是判断整体市场估值的长期参考。",
    "关注与200日均线位置 | 历史平均PE约16倍，>28倍需警惕高估 | VIX>30是历史性逆向买入信号", None),
  "vix":        ("VIX恐慌指数",     "点",
    "芝加哥期权交易所波动率指数，衡量市场对未来30天标普500波动幅度的预期，本质上是保险成本指数。极度恐慌时（VIX>40）往往是历史上最好的股票买入时机（2008年、2020年）；极度平静时（VIX<13）市场往往高度自满，隐藏风险最大。逆向投资者视VIX为情绪的反向信号。",
    "🟢 13–20 正常 | 🔴 <13 过度平静（自满，警惕）| 🟡 20–30 市场紧张 | 🔴 >30 恐慌（历史买入机会）", None),
  "dxy":        ("美元指数DXY",     "点",
    "美元兑一篮子主要货币（欧元57%、日元14%、英镑12%、加元9%等）的综合指数。美元走强的全球传导：①大宗商品（黄金、原油、铜）价格承压（以美元计价）②新兴市场资金外流和货币贬值③人民币汇率面临压力④美债对外国投资者更具吸引力。DXY是全球流动性最重要的温度计之一。",
    ">105 美元偏强，非美资产承压 | 95–105 中性区间 | <95 美元偏弱，大宗商品及新兴市场受益", None),
  "gold":       ("黄金",            "USD/盎司",
    "最经典的抗通胀和避险资产。核心定价逻辑：实际利率（名义利率−通胀预期）越低，持有黄金机会成本越低，金价越高。因此美联储降息周期、通胀高企期是黄金的历史性利好。额外驱动：地缘政治风险上升、去美元化趋势（各国央行增持黄金储备）。近年央行购金量达历史峰值，是金价突破历史高位的结构性支撑。",
    "关注实际利率（TIPS收益率）：实际利率为负时黄金配置价值最高 | 全球央行购金量是长期趋势指标", None),
  "oil":        ("原油WTI",         "USD/桶",
    "西德克萨斯中质原油现货价格，全球最主要的石油定价基准之一（另一个是布伦特原油，通常比WTI高3–5美元）。原油价格直接影响：①通胀（每涨10美元约推高CPI 0.3%）②能源股盈利③航空、化工、制造业成本。供给端受OPEC+减产决策主导，需求端与全球GDP增速高度相关，地缘政治风险（中东局势）是重要扰动变量。",
    ">90 高油价推升通胀，美联储维持高利率压力大 | 70–90 中性 | <60 需求疲软信号或供给过剩", None),
  "copper":     ("铜价",            "USD/磅",
    "铜被称为'铜博士'（Dr. Copper），因其广泛用于建筑、电力、电动车、电子制造等领域，价格变化高度预示全球经济景气周期。中国是全球铜消费最大国（约占55%），中国基建和制造业数据对铜价影响尤为显著。铜价暴跌往往是全球经济衰退的早期信号；铜价走强则暗示工业需求旺盛，与全球制造业PMI高度正相关。",
    "关注中国需求（占全球55%）和全球制造业PMI | 铜价与标普500相关性高，是经济'体温计'", None),
}

# ═══════════════════════════════════════════════════════════
# 2. 信号规则
# ═══════════════════════════════════════════════════════════
# 每条: (阈值, 颜色, 标签) — 升序，<=阈值取对应颜色
_SIG = {
  "us_cpi":     [( 2.0,"green","温和"),    (3.5,"yellow","偏高"), (999,"red","过热")],
  "us_pce":     [( 2.0,"green","温和"),    (3.0,"yellow","偏高"), (999,"red","过热")],
  "us_rate":    [( 2.0,"green","宽松"),    (4.5,"yellow","中性"), (999,"red","限制性")],
  "us_t10":     [( 3.5,"green","低位"),    (4.5,"yellow","中性"), (999,"red","高位")],
  "us_payroll": [(10.0,"red","偏弱"),      (20.0,"yellow","一般"),(999,"green","强劲")],
  "us_gdp":     [( 0.0,"red","负增长"),    (2.0,"yellow","放缓"), (999,"green","健康")],
  "us_mfg_pmi": [(50,"red","收缩"),        (999,"green","扩张")],
  "us_svc_pmi": [(50,"red","收缩"),        (999,"green","扩张")],
  "us_indpro":  [(0.0,"red","衰退"),       (2.0,"yellow","放缓"),  (999,"green","扩张")],
  "us_retail":  [(0.0,"red","萎缩"),       (4.0,"yellow","平稳"),  (999,"green","强劲")],
  "cn_cpi":     [(-0.1,"red","通缩"),      (1.0,"yellow","偏低"),(3.0,"green","健康"),(999,"red","过热")],
  "cn_ppi":     [(-3.0,"red","深度通缩"),  (0.0,"yellow","弱势"),(3.0,"green","修复"),(999,"yellow","偏高")],
  "cn_gdp":     [( 4.0,"red","偏离目标"),  (5.0,"yellow","略低"),(999,"green","达标")],
  "cn_mfg_pmi": [(50,"red","收缩"),        (999,"green","扩张")],
  "cn_svc_pmi": [(50,"red","收缩"),        (52,"yellow","弱扩张"),(999,"green","稳健扩张")],
  "cn_lpr":     [( 3.5,"green","低位"),    (4.0,"yellow","中性"), (999,"red","偏高")],
  "eu_cpi":     [( 2.5,"green","接近目标"),(4.0,"yellow","偏高"),(999,"red","过热")],
  "jp_cpi":     [( 0.0,"red","通缩"),      (3.0,"green","健康"), (999,"yellow","偏高")],
  "vix":        [(13,"yellow","过平静"),   (20,"green","正常"),  (30,"yellow","紧张"),(999,"red","恐慌")],
  "oil":        [(60,"red","偏低"),        (90,"green","中性"),  (999,"yellow","偏高")],
}

def _signal(iid, v):
    for thresh, color, label in _SIG.get(iid, []):
        if v <= thresh: return color, label
    return "neutral", "—"

# ═══════════════════════════════════════════════════════════
# 3. API Key 管理（跨平台）
# ═══════════════════════════════════════════════════════════
def _load_cfg():
    if not CONFIG_FILE.exists(): return {}
    out = {}
    for line in CONFIG_FILE.read_text("utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k,_,v = line.partition("="); out[k.strip()] = v.strip().strip('"')
    return out

def _save_cfg(k, v):
    c = _load_cfg(); c[k] = v
    CONFIG_FILE.write_text("\n".join(f'{a}="{b}"' for a,b in c.items())+"\n","utf-8")

def get_fred_key():
    key = os.environ.get("FRED_API_KEY","").strip()
    if key and "YOUR" not in key: return key
    key = _load_cfg().get("FRED_API_KEY","").strip()
    if key: os.environ["FRED_API_KEY"]=key; return key
    # CI / 非交互环境：不要 input()，直接报错退出
    if not sys.stdin.isatty() or os.environ.get("CI"):
        sys.exit("❌ 未设置 FRED_API_KEY 环境变量。CI 环境请在 Secrets 中配置。")
    print("\n  ⚠️  未找到 FRED API Key")
    print("  → https://fred.stlouisfed.org/docs/api/api_key.html 免费申请")
    key = input("  请输入 FRED API Key: ").strip()
    if not key: sys.exit("未输入，退出。")
    _save_cfg("FRED_API_KEY", key)
    if IS_WINDOWS:
        try: subprocess.run(["setx","FRED_API_KEY",key],capture_output=True)
        except: pass
    else:
        try:
            b=Path.home()/".bashrc"; old=b.read_text("utf-8") if b.exists() else ""
            if "FRED_API_KEY" not in old: b.write_text(old+f'\nexport FRED_API_KEY="{key}"\n',"utf-8")
        except: pass
    os.environ["FRED_API_KEY"]=key; print(f"  ✅ Key 已保存\n"); return key

# ═══════════════════════════════════════════════════════════
# 4. FRED 数据获取（含历史趋势）
# ═══════════════════════════════════════════════════════════
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
_FRED_LAST_TIME = [0.0]   # 用列表持久化跨调用状态
_FRED_MIN_INTERVAL = 0.25  # FRED API 限速：120次/60秒 = 0.5s/次，留余量

def _http_retry(url, params, timeout=20, retries=3):
    """带重试的HTTP GET：覆盖 SSL/Connection/Timeout 错误，以及 429/5xx 服务端错误"""
    last_err = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            # 限流 (429) 或服务端错误 (5xx) → 重试
            if r.status_code == 429 or 500 <= r.status_code < 600:
                wait = (5 if r.status_code == 429 else 2) * (i + 1)
                last_err = requests.exceptions.HTTPError(f"HTTP {r.status_code}")
                if i < retries - 1:
                    print(f"      [重试 {i+1}/{retries-1}] HTTP {r.status_code}, {wait}s 后重试...")
                    time.sleep(wait); continue
                raise last_err
            # 其他 4xx：序列ID错误等，重试无意义
            r.raise_for_status()
            return r
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_err = e
            if i < retries - 1:
                wait = 1.5 ** i
                print(f"      [重试 {i+1}/{retries-1}] {type(e).__name__}, {wait:.1f}s 后重试...")
                time.sleep(wait); continue
    raise last_err if last_err else Exception("All retries failed")

def _fred_raw(sid, limit, key):
    # 主动限速：避免触发 FRED 服务端 429
    elapsed = time.time() - _FRED_LAST_TIME[0]
    if elapsed < _FRED_MIN_INTERVAL:
        time.sleep(_FRED_MIN_INTERVAL - elapsed)
    _FRED_LAST_TIME[0] = time.time()
    try:
        r = _http_retry(FRED_URL, {
            "series_id":sid,"api_key":key,"file_type":"json",
            "sort_order":"desc","limit":limit})
        return [(o["date"], float(o["value"]))
                for o in r.json().get("observations",[]) if o["value"]!="."]
    except requests.exceptions.HTTPError as e:
        # 显示具体状态码
        code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else str(e)
        print(f"    [FRED] {sid}: HTTP {code}"); return []
    except Exception as e:
        print(f"    [FRED] {sid}: {type(e).__name__}"); return []

def fred_get(sid, key, mode="latest", n=13):
    """
    mode: latest=直取最新值+趋势, yoy=同比%, mom=环比绝对差
    n: 趋势图取最近n个点
    返回: {"value":..,"date":..,"trend_labels":[..],"trend_values":[..]}
    """
    raw = _fred_raw(sid, max(n+14, 30), key)
    if not raw: return None
    asc = list(reversed(raw))
    if mode == "latest":
        t = asc[-n:]
        return {"value":raw[0][1], "date":raw[0][0][:7],
                "trend_labels":[x[0][:7] for x in t],
                "trend_values":[round(x[1],2) for x in t]}
    if mode == "yoy":
        yoy = [(asc[i][0][:7], round((asc[i][1]/asc[i-12][1]-1)*100,2))
               for i in range(12,len(asc)) if asc[i-12][1]]
        if not yoy: return None
        t = yoy[-n:]
        return {"value":yoy[-1][1],"date":yoy[-1][0],
                "trend_labels":[x[0] for x in t],"trend_values":[x[1] for x in t]}
    if mode == "mom":
        mom = [(asc[i][0][:7], round(asc[i][1]-asc[i-1][1],2))
               for i in range(1,len(asc))]
        if not mom: return None
        t = mom[-n:]
        return {"value":mom[-1][1],"date":mom[-1][0],
                "trend_labels":[x[0] for x in t],"trend_values":[x[1] for x in t]}
    return None

def fred_get_chain(sids, key, mode="yoy", n=13):
    """按顺序尝试多个FRED序列ID，返回数据最新的那个（应对FRED序列下架/停更）"""
    best = None; best_ym = None
    for sid in sids:
        r = fred_get(sid, key, mode, n)
        if not r: continue
        try:
            d = r.get("date","")
            if len(d) >= 7:
                ym = (int(d[:4]), int(d[5:7]))
                if best_ym is None or ym > best_ym:
                    best, best_ym = r, ym
        except:
            if not best: best = r
    return best

# ═══════════════════════════════════════════════════════════
# 5. yfinance 市场数据
# ═══════════════════════════════════════════════════════════
def yf_get(ticker, retries=3):
    last_err = None
    for i in range(retries):
        try:
            h = yf.Ticker(ticker).history(period="1y", interval="1mo", auto_adjust=True)
            if h.empty:
                if i < retries-1: time.sleep(1.5**i); continue
                return None
            c = h["Close"].dropna()
            if len(c) < 2: return None
            lat, prev = float(c.iloc[-1]), float(c.iloc[-2])
            return {
                "value":      round(lat, 2),
                "date":       str(c.index[-1].date())[:7],
                "change_pct": round((lat/prev-1)*100, 2),
                "trend_labels": [str(d.date())[:7] for d in c.index],
                "trend_values": [round(float(v),2) for v in c],
            }
        except Exception as e:
            last_err = e
            if i < retries-1:
                time.sleep(1.5**i); continue
    print(f"    [yfinance] {ticker}: {type(last_err).__name__}"); return None

# ═══════════════════════════════════════════════════════════
# 6. akshare 中国数据（失败时回退到FRED）
# ═══════════════════════════════════════════════════════════
def _ak():
    try: import akshare as ak; return ak
    except ImportError:
        try: print("  安装 akshare..."); _pip("akshare"); import akshare as ak; return ak
        except: return None

def _ak_call(func, *args, **kwargs):
    """调用 akshare 函数。若发生 ProxyError（用户系统代理拦截了国内请求），
       临时清空代理环境变量重试一次。"""
    try:
        return func(*args, **kwargs)
    except (requests.exceptions.ProxyError, OSError) as e:
        msg = str(e)
        if "Proxy" in msg or "proxy" in msg or "ProxyError" in type(e).__name__:
            saved = {}
            for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy',
                      'ALL_PROXY','all_proxy']:
                if k in os.environ: saved[k] = os.environ.pop(k)
            try:
                print(f"      [代理绕过] 检测到系统代理干扰，临时禁用后重试")
                return func(*args, **kwargs)
            finally:
                os.environ.update(saved)
        raise

def _ak_find_cols(df, date_keywords, value_keywords):
    """在DataFrame中按关键词匹配日期列和值列"""
    date_col = value_col = None
    for c in df.columns:
        s = str(c)
        if any(k in s for k in date_keywords) and not date_col: date_col = c
        if any(k in s for k in value_keywords) and not value_col: value_col = c
    return date_col, value_col

import re
_CN_DATE_RE = re.compile(r'(\d{4})\D+?(\d{1,2})(?:\D+?(\d{1,2}))?')

def _parse_any_date(s):
    """兼容解析: '2024-01-15' / '2024年1月份' / '2024年12月' / '2024.1' 等多种格式"""
    if pd.isna(s): return pd.NaT
    s = str(s).strip()
    if not s: return pd.NaT
    # 先尝试标准解析（英文格式、ISO格式）
    parsed = pd.to_datetime(s, errors='coerce')
    if not pd.isna(parsed): return parsed
    # 中文格式：用正则提取 年-月-日
    m = _CN_DATE_RE.search(s)
    if m:
        try:
            y, mo = int(m.group(1)), int(m.group(2))
            d = int(m.group(3)) if m.group(3) else 1
            return pd.Timestamp(year=y, month=mo, day=min(d, 28))
        except: pass
    return pd.NaT

def _find_date_col(df):
    """智能查找日期列：列名提示 优先，否则按内容解析率挑选"""
    # 优先1：列名含日期关键词 + 内容可解析
    for c in df.columns:
        if any(k in str(c) for k in ['日期','时间','月份','date','time','Date','Time']):
            sample = df[c].dropna().astype(str).head(5)
            if len(sample) >= 2:
                ok = sum(1 for v in sample if not pd.isna(_parse_any_date(v)))
                if ok >= max(2, len(sample)//2): return c
    # 优先2：纯内容驱动
    best, best_score = None, 0
    for c in df.columns:
        try:
            sample = df[c].dropna().astype(str).head(10)
            if len(sample) == 0: continue
            score = sum(1 for v in sample if not pd.isna(_parse_any_date(v)))
            if score >= 5 and score > best_score:
                best, best_score = c, score
        except: continue
    return best

def _ak_extract(df, value_keywords=None, n=13):
    """从 akshare DataFrame 中智能提取(value, date, trend)"""
    if df is None or len(df) == 0: return None
    df = df.copy()

    date_col = _find_date_col(df)
    if not date_col: return None

    # 找数值列：优先关键词匹配，否则取第一个数值列
    val_col = None
    if value_keywords:
        val_col = next((c for c in df.columns
            if c != date_col and any(k in str(c) for k in value_keywords)), None)
    if not val_col:
        for c in df.columns:
            if c == date_col: continue
            try:
                test = df[c].dropna().astype(str).str.replace('%','',regex=False).str.replace(',','',regex=False).head(5)
                pd.to_numeric(test, errors='raise')
                val_col = c; break
            except: continue
    if not val_col: return None

    # 用增强解析器，按日期升序取最近 n+5 条
    df['_dt'] = df[date_col].apply(_parse_any_date)
    df = df.dropna(subset=['_dt']).sort_values('_dt').tail(n + 5)

    labels, values = [], []
    for _, row in df.iterrows():
        try:
            v = float(str(row[val_col]).replace('%','').replace(',',''))
            labels.append(row['_dt'].strftime('%Y-%m'))
            values.append(v)
        except: pass
    if len(values) < 2: return None
    return {
        "value": values[-1], "date": labels[-1],
        "trend_labels": labels[-n:], "trend_values": values[-n:],
    }

def _ak_index_extract(df, n=13):
    """从指数数据中提取月度收盘趋势（输入可为日线或月线，输出统一月度）"""
    if df is None or len(df) == 0: return None
    df = df.copy()

    # 找日期列
    date_col = None
    for c in df.columns:
        s = str(c).lower()
        if any(k in s for k in ['日期','date','时间']):
            date_col = c; break
    if not date_col:
        for c in df.columns:
            try:
                if pd.to_datetime(df[c].dropna().astype(str).head(5), errors='coerce').notna().sum() >= 3:
                    date_col = c; break
            except: continue
    if not date_col: return None

    # 找收盘列
    close_col = next((c for c in df.columns if any(k in str(c) for k in ['收盘','close'])), None)
    if not close_col: return None

    df['_dt'] = pd.to_datetime(df[date_col].astype(str), errors='coerce')
    df = df.dropna(subset=['_dt', close_col]).sort_values('_dt')
    if len(df) == 0: return None

    # resample 到月末（适配日线/月线两种输入）
    df = df.set_index('_dt')
    monthly = pd.to_numeric(df[close_col], errors='coerce').resample('ME').last().dropna()
    monthly = monthly.tail(n + 1)
    if len(monthly) < 2: return None

    labels = [d.strftime('%Y-%m') for d in monthly.index]
    values = [round(float(v), 2) for v in monthly]
    latest, prev = values[-1], values[-2]
    return {
        "value": latest, "date": labels[-1],
        "change_pct": round((latest/prev-1)*100, 2),
        "trend_labels": labels[-n:], "trend_values": values[-n:],
    }

def ak_china_cpi(n=13):
    ak = _ak()
    if not ak: return None
    try:
        df = _ak_call(ak.macro_china_cpi_monthly)
        return _ak_extract(df, value_keywords=["同比","今值","现值","公布值"], n=n)
    except Exception as e:
        print(f"    [akshare] CPI: {type(e).__name__}: {e}"); return None

def ak_china_pmi_both(n=13):
    """同时返回(制造业PMI, 非制造业PMI)，共享一次API调用"""
    ak = _ak()
    if not ak: return (None, None)
    try:
        df = _ak_call(ak.macro_china_pmi)
        if df is None or len(df) == 0:
            print("    [akshare] PMI: 返回空数据")
            return (None, None)
        df = df.copy()
        date_col = _find_date_col(df)
        if not date_col:
            print(f"    [akshare] PMI: 找不到日期列。实际列名: {list(df.columns)}")
            return (None, None)

        # 制造业-指数：含"制造业"且不含"非"
        mfg_col = next((c for c in df.columns
            if "制造业" in str(c) and "非" not in str(c) and "指数" in str(c)
            and c != date_col), None)
        # 非制造业-指数
        svc_col = next((c for c in df.columns
            if "非制造业" in str(c) and "指数" in str(c) and c != date_col), None)

        if not mfg_col and not svc_col:
            print(f"    [akshare] PMI: 找不到指数列。实际列名: {list(df.columns)}")
            return (None, None)

        df['_dt'] = df[date_col].apply(_parse_any_date)
        df = df.dropna(subset=['_dt']).sort_values('_dt').tail(n + 5)

        def _build(col, label):
            if not col: return None
            labels, values = [], []
            for _, row in df.iterrows():
                try:
                    v = float(row[col])
                    if v < 30 or v > 70: continue
                    labels.append(row['_dt'].strftime('%Y-%m'))
                    values.append(v)
                except: pass
            if len(values) < 2:
                print(f"    [akshare] PMI {label}: 解析后数据不足（仅{len(values)}条）")
                return None
            return {"value":values[-1], "date":labels[-1],
                    "trend_labels":labels[-n:], "trend_values":values[-n:]}
        return _build(mfg_col, "制造业"), _build(svc_col, "非制造业")
    except Exception as e:
        print(f"    [akshare] PMI: {type(e).__name__}: {e}"); return (None, None)

def ak_china_ppi(n=13):
    ak = _ak()
    if not ak: return None
    try:
        df = _ak_call(ak.macro_china_ppi_yearly)
        return _ak_extract(df, value_keywords=["今值","现值","公布值"], n=n)
    except Exception as e:
        print(f"    [akshare] PPI: {type(e).__name__}: {e}"); return None

def ak_china_lpr(n=13):
    ak = _ak()
    if not ak: return None
    try:
        df = _ak_call(ak.macro_china_lpr)
        # LPR 数据列名通常是 "LPR1Y" 或 "1年期LPR"
        return _ak_extract(df, value_keywords=["1Y","1年","LPR1","1_year"], n=n)
    except Exception as e:
        print(f"    [akshare] LPR: {type(e).__name__}: {e}"); return None

def ak_china_gdp(n=13):
    ak = _ak()
    if not ak: return None
    try:
        df = _ak_call(ak.macro_china_gdp_yearly)
        return _ak_extract(df, value_keywords=["今值","现值","公布值"], n=n)
    except Exception as e:
        print(f"    [akshare] GDP: {type(e).__name__}: {e}"); return None

# ── 中国指数：多重 fallback ─────────────────────────
_INDEX_PREFIX = {  # akshare stock_zh_index_daily 需要的前缀
    "000001":"sh", "000300":"sh", "000016":"sh", "000688":"sh",
    "399001":"sz", "399006":"sz", "399005":"sz",
}

def ak_index_monthly(symbol, n=13):
    """获取A股指数月度数据。多重fallback：
       1) index_zh_a_hist monthly  → 2) index_zh_a_hist daily  → 3) stock_zh_index_daily"""
    ak = _ak()
    if not ak: return None
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=420)).strftime("%Y%m%d")

    # 方法1：月线
    try:
        df = _ak_call(ak.index_zh_a_hist, symbol=symbol, period="monthly",
                      start_date=start_date, end_date=end_date)
        r = _ak_index_extract(df, n)
        if r: return r
    except Exception as e:
        print(f"    [akshare] {symbol} monthly: {type(e).__name__}")

    # 方法2：日线 + 重采样
    try:
        df = _ak_call(ak.index_zh_a_hist, symbol=symbol, period="daily",
                      start_date=start_date, end_date=end_date)
        r = _ak_index_extract(df, n)
        if r: return r
    except Exception as e:
        print(f"    [akshare] {symbol} daily: {type(e).__name__}")

    # 方法3：stock_zh_index_daily（带sh/sz前缀）
    try:
        prefix = _INDEX_PREFIX.get(symbol, "sh" if symbol.startswith("0") else "sz")
        df = _ak_call(ak.stock_zh_index_daily, symbol=f"{prefix}{symbol}")
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df[df['date'] >= datetime.now() - timedelta(days=420)]
        r = _ak_index_extract(df, n)
        if r: return r
    except Exception as e:
        print(f"    [akshare] {symbol} stock_zh: {type(e).__name__}")

    return None

# ═══════════════════════════════════════════════════════════
# 7. 当前判断引擎（基于实时数值生成解读）
# ═══════════════════════════════════════════════════════════
INTERPRET_RULES = {
  # ── 美国 ──────────────────────────────────────────
  "us_cpi": [
    (lambda v: v < 1.5,  "通胀低于美联储目标，降息空间充裕。债券和黄金受益，但需警惕背后的经济疲软。"),
    (lambda v: v < 2.5,  "通胀接近美联储2%目标，政策从紧缩转向中性。利好风险资产估值修复。"),
    (lambda v: v < 3.5,  "通胀仍粘性偏高，美联储倾向维持高利率。对长久期资产（科技股、长期债券）形成压制。"),
    (lambda v: True,     "通胀严重偏离目标，加息预期升温。股债双杀风险，黄金等避险资产相对受益。"),
  ],
  "us_pce": [
    (lambda v: v < 2,    "美联储首选通胀指标已达标，降息确信度提升，利率敏感资产受益。"),
    (lambda v: v < 3,    "核心通胀仍高于2%目标，政策维持限制性。债券有交易性机会但需耐心。"),
    (lambda v: True,     "核心通胀粘性强，美联储难以转向。建议加强防御配置。"),
  ],
  "us_rate": [
    (lambda v: v < 2,    "处于宽松货币环境，风险资产估值有支撑。但需警惕未来加息时点。"),
    (lambda v: v < 4,    "中性利率区间，关注政策方向变化。市场对利率敏感度降低。"),
    (lambda v: True,     "限制性利率水平，对经济活动有抑制。市场已price in高利率，转向时反应剧烈。"),
  ],
  "us_t10": [
    (lambda v: v < 3,    "长端利率较低，股票估值有支撑，房贷融资成本舒适。"),
    (lambda v: v < 4.5,  "中性收益率区间。重点关注与2年期利差的变化（曲线倒挂是衰退信号）。"),
    (lambda v: True,     "高收益率压制股票估值（尤其成长股），房贷成本上升抑制地产。债券配置价值显现。"),
  ],
  "us_payroll": [
    (lambda v: v < 10,   "就业增长疲弱，软着陆叙事受挑战。降息预期升温，债券受益。"),
    (lambda v: v < 20,   "就业增长温和，符合软着陆路径。利好平衡型资产配置。"),
    (lambda v: True,     "就业过热，工资增长加快，通胀压力难消。利率高位维持时间会延长。"),
  ],
  "us_gdp": [
    (lambda v: v < 0,    "经济陷入收缩，技术性衰退风险显现。央行将加速降息。"),
    (lambda v: v < 1,    "经济增长低迷，关注是否进入衰退。债券和黄金有配置价值。"),
    (lambda v: v < 3,    "经济增长稳健，符合软着陆路径。股债平衡配置较优。"),
    (lambda v: True,     "经济增长强劲，但需警惕过热和通胀回升风险。"),
  ],
  "us_indpro": [
    (lambda v: v < -1,   "工业产出萎缩，制造业衰退。工业股、铜铝等大宗商品承压。"),
    (lambda v: v < 1,    "工业产出停滞，等待复苏信号。"),
    (lambda v: True,     "工业产出增长，制造业扩张，原材料和工业股受益。"),
  ],
  "us_retail": [
    (lambda v: v < 0,    "消费支出萎缩，衰退信号显现。可选消费股承压，必需消费品防御性更强。"),
    (lambda v: v < 4,    "消费支出温和增长，经济动能稳定。"),
    (lambda v: True,     "消费支出强劲，但通胀回落难度增加，美联储更难降息。"),
  ],

  # ── 中国 ──────────────────────────────────────────
  "cn_cpi": [
    (lambda v: v < 0,    "通缩环境，反映内需严重不足。货币政策有更大宽松空间，但传导效率受限，需关注财政发力。"),
    (lambda v: v < 1,    "通胀偏低，内需疲软。等待房地产稳定与财政刺激信号。"),
    (lambda v: v < 3,    "通胀温和健康，政策环境友好。"),
    (lambda v: True,     "通胀偏高，政策面临两难。"),
  ],
  "cn_ppi": [
    (lambda v: v < -3,   "工业深度通缩，企业盈利全面承压。需供给侧改革或大规模需求刺激才能扭转。"),
    (lambda v: v < 0,    "工业品价格仍弱势，关注是否触底。PPI转正是周期股盈利改善的关键信号。"),
    (lambda v: v < 3,    "PPI转正且温和，工业企业盈利修复，钢铁、有色、化工等周期股有机会。"),
    (lambda v: True,     "PPI偏高，警惕传导至CPI推升通胀的风险。"),
  ],
  "cn_gdp": [
    (lambda v: v < 4,    "GDP明显偏离目标，财政货币政策刺激可期。但需要看到实际效果传导。"),
    (lambda v: v < 5,    "GDP略低于目标，政策仍需发力。市场情绪偏谨慎。"),
    (lambda v: v < 6,    "GDP达标稳健，经济运行良好。"),
    (lambda v: True,     "GDP超预期增长，但近年这种情况较少见，需核实数据可比性。"),
  ],
  "cn_mfg_pmi": [
    (lambda v: v < 49,   "制造业明显收缩，铁矿石、铜等工业原材料价格承压。期待政策托底。"),
    (lambda v: v < 50,   "制造业弱势，处于收缩边缘，需要政策刺激。"),
    (lambda v: v < 51,   "制造业弱扩张，复苏不稳固。"),
    (lambda v: True,     "制造业明显扩张，工业链上下游受益，大宗商品有支撑。"),
  ],
  "cn_svc_pmi": [
    (lambda v: v < 50,   "服务业收缩，消费动能不足。餐饮、旅游、零售板块承压。"),
    (lambda v: v < 52,   "服务业温和扩张，符合中国消费复苏路径。"),
    (lambda v: True,     "服务业强劲扩张，消费股、餐饮旅游受益。"),
  ],
  "cn_lpr": [
    (lambda v: v < 3.0,  "LPR处于历史低位，货币政策已较宽松。后续降息空间收窄。"),
    (lambda v: v < 4.0,  "LPR中性偏低，政策仍有适度宽松空间。"),
    (lambda v: True,     "LPR偏高，房贷与企业融资成本压力较大。"),
  ],

  # ── 日本 ──────────────────────────────────────────
  "jp_cpi": [
    (lambda v: v < 0,    "通缩重现，BOJ可能放缓或暂停加息。日元承压。"),
    (lambda v: v < 2,    "通胀低于目标，BOJ政策正常化进程缓慢。"),
    (lambda v: v < 3,    "通胀达到BOJ 2%目标，加息周期可持续。日元有支撑。"),
    (lambda v: True,     "通胀偏高，BOJ加息压力加大，对全球套利交易（Carry Trade）形成扰动。"),
  ],
  "jp_rate": [
    (lambda v: v < 0.1,  "处于零利率附近，套利交易（借日元买美元资产）仍活跃。BOJ每次加息都会引发全球资产联动波动。"),
    (lambda v: v < 0.5,  "BOJ已开启加息周期，套利交易承压平仓，日元升值压力增加。"),
    (lambda v: True,     "日本利率水平已较高，对全球流动性影响显著。"),
  ],

  # ── 欧元区 ────────────────────────────────────────
  "eu_cpi": [
    (lambda v: v < 2,    "通胀已回落至ECB目标以下，降息周期可持续。欧债和欧股受益。"),
    (lambda v: v < 3,    "通胀接近目标，ECB降息节奏温和。欧元/美元方向取决于Fed态度。"),
    (lambda v: True,     "通胀仍偏高，ECB政策受制约。"),
  ],
  "eu_rate": [
    (lambda v: v < 2,    "ECB存款利率处于宽松区间，欧元区流动性充裕。"),
    (lambda v: v < 4,    "中性利率区间。关注与Fed利率差对欧元/美元的影响。"),
    (lambda v: True,     "限制性利率水平，但ECB通常先于Fed降息。"),
  ],

  # ── 全球市场（数值型）────────────────────────────
  "vix": [
    (lambda v: v < 13,   "市场过度乐观，自满情绪明显。隐藏风险最高时往往是保险最便宜时——警惕回调。"),
    (lambda v: v < 20,   "市场情绪正常，风险偏好平衡。常态运行区间。"),
    (lambda v: v < 30,   "市场紧张，风险偏好下降。开始有逆向布局机会。"),
    (lambda v: True,     "市场恐慌，历史上常对应阶段性底部。逆向投资者的进场窗口。"),
  ],
  "dxy": [
    (lambda v: v < 95,   "美元偏弱，大宗商品（黄金、原油、铜）受益，新兴市场资金流入，人民币压力减轻。"),
    (lambda v: v < 105,  "美元中性区间，全球资产相对均衡。"),
    (lambda v: True,     "美元偏强，非美资产承压，大宗商品下行压力大，新兴市场资金外流，人民币贬值压力加大。"),
  ],
  "oil": [
    (lambda v: v < 60,   "油价低位，对通胀有压制，利好航空、化工等下游。但反映需求疲软或OPEC+减产失效。"),
    (lambda v: v < 90,   "油价中性区间，对宏观经济相对平衡。能源股估值合理。"),
    (lambda v: True,     "油价偏高，推升通胀，美联储维持高利率压力大。能源股受益但需警惕需求破坏。"),
  ],
}

def _trend_judge(ind, asset_type="该资产"):
    """对没有明确数值规则的市场指数，基于12个月趋势给出解读"""
    trend = ind.get("trend_values", [])
    if len(trend) < 6 or not trend[0]: return ""
    yoy = (ind["value"] / trend[0] - 1) * 100
    # 短期 (3个月) 动能
    short = ""
    if len(trend) >= 4 and trend[-4]:
        qoq = (trend[-1] / trend[-4] - 1) * 100
        if abs(qoq) > 3:
            short = f"，近3个月{'走强' if qoq > 0 else '走弱'} {abs(qoq):.1f}%"

    if yoy > 15:
        return f"过去12个月{asset_type}上涨 {yoy:.1f}%{short}，处于明显上升趋势，需关注估值是否过度。"
    if yoy < -15:
        return f"过去12个月{asset_type}下跌 {abs(yoy):.1f}%{short}，处于明显下行趋势，关注是否触底。"
    return f"过去12个月{asset_type}变化 {yoy:+.1f}%{short}，处于震荡整理区间。"

# 市场指数类型映射（用于 trend_judge 的中文描述）
_TREND_TYPE = {
    "us_t10":"收益率","sp500":"美股","cn_market":"上证","cn_hs300":"沪深300",
    "hk_market":"恒生","jp_market":"日经","eu_market":"DAX",
    "usdjpy":"美元/日元","gold":"金价","copper":"铜价",
}

def interpret(iid, ind):
    """根据指标当前值/趋势生成解读和判断"""
    if ind.get("error") or ind.get("value") is None: return ""
    v = ind["value"]
    rules = INTERPRET_RULES.get(iid)
    if rules:
        for pred, text in rules:
            try:
                if pred(v): return text
            except: continue
        return ""
    # 没有数值规则的（如多数股指），用趋势判断
    return _trend_judge(ind, _TREND_TYPE.get(iid, "该指标"))

# ═══════════════════════════════════════════════════════════
# 7.5 个人影响与应对（基于当前信号动态匹配，针对中国境内个人投资者）
# ═══════════════════════════════════════════════════════════
PERSONAL_IMPACT = {
  # ── 美国 ────────────────────────────────────────
  "us_cpi": {
    "green": ("美国通胀温和→美联储有降息空间→美元走弱→人民币压力减轻、进口商品（汽车、3C、化妆品）相对便宜。",
              "海外旅游/留学/购车计划可关注；境内黄金、QDII科技基金有支撑；现金类理财收益预期下降，可锁定中长期固收。"),
    "yellow":("美国通胀超目标→美联储维持高利率→美元偏强→人民币贬值压力延续、进口商品涨价。",
              "海外消费提前规划分批换汇；增配黄金ETF（如518880）做对冲；A股成长板块（科技）短期承压，红利/消费板块相对稳定。"),
    "red":   ("高通胀+高利率组合是新兴市场最不利情景→人民币弱、A股流动性差、进口贵价商品涨更猛。",
              "推迟非必需的海外大额开支（车、奢侈品）；超配黄金（占资产5–10%）和A股红利低估值板块；避免新借入海外货币贷款。"),
  },
  "us_pce": {
    "green": ("美联储首选指标达标，全球流动性预期改善。", "海外资产/QDII配置时机较好，现金过多是机会成本。"),
    "yellow":("核心通胀粘性强，美联储难放松，美元延续偏强。", "保留黄金对冲；A股侧重防御板块；推迟海外消费计划。"),
    "red":   ("核心通胀严重失控，全球资产价格剧烈波动可期。", "防御为主：黄金、必需消费、高股息；避免加杠杆。"),
  },
  "us_rate": {
    "green": ("美联储宽松→全球流动性回升→新兴市场资金流入→A股估值修复机会、黄金有支撑。",
              "可逐步增配A股宽基ETF（沪深300/中证500）、港股通；海外科技股有反弹机会；现金不必过度持有。"),
    "yellow":("中性利率水平，市场已充分定价。无明显趋势性机会。",
              "保持均衡配置（股债6:4）；定投而非择时；现金应急金做好（6–12个月支出）即可。"),
    "red":   ("美国限制性高利率→A股估值难大幅扩张、人民币承压、新兴市场资金外流。",
              "现金/固收占比可适当提高（30–40%）；股票侧重高股息（红利ETF如510880）；推迟加杠杆型投资（房产）；新借贷优先固定利率。"),
  },
  "us_t10": {
    "green": ("全球长端利率下行→长久期资产估值改善→对A股科技、生物医药、REITs利好。",
              "可适度增配科技/医药主题ETF；长债（如30年国债ETF 511130）有交易性机会。"),
    "yellow":("中性区间。重点关注与2年期收益率差值（曲线倒挂仍是衰退信号）。",
              "保持债券久期分散；不押注单一方向；密切关注美联储议息会议指引。"),
    "red":   ("10年高收益率压制全球风险资产→A股科技股、高估值板块、地产链都承压。",
              "回避高估值成长股；A股侧重防御（公用、银行、消费必需）；评估现有房贷利率风险。"),
  },
  "us_payroll": {
    "green": ("美国就业强劲→经济动能足→美联储维持高利率→对全球流动性是制约。",
              "美元延续强势预期，海外消费成本偏高；A股流动性改善预期减弱；保留防御配置。"),
    "yellow":("就业放缓符合软着陆→市场降息预期升温→对全球资产偏利好。",
              "可逐步增加成长资产（美股科技QDII、A股成长股）配置。"),
    "red":   ("就业大幅恶化→美联储加速降息→但同时反映衰退风险。",
              "防御性配置：增配债券、黄金；股票侧重必需消费、医药等抗周期板块；推迟新增高风险投资。"),
  },
  "us_gdp": {
    "green": ("美国经济稳健，全球需求有支撑。", "对中国出口链相关股（家电、电子、纺织）是利好。"),
    "yellow":("美国经济放缓，软着陆中。", "保持均衡配置；密切关注就业和通胀走向。"),
    "red":   ("美国陷入衰退，全球需求收缩。", "防御为主：增配债券、黄金；回避出口型周期股；持有现金等待机会。"),
  },
  "us_indpro": {
    "green": ("美国制造业扩张→对中国机械/零部件出口商利好；铜、铝等工业品需求向好。", "可适度配置工业股或大宗商品ETF；关注出口链概念。"),
    "yellow":("制造业疲软，等待复苏。", "回避周期股；保留观望仓位。"),
    "red":   ("制造业衰退→全球经济风险显现，工业品需求承压。", "回避大宗商品和工业股；增配防御资产（债券、黄金、必需消费）。"),
  },
  "us_retail": {
    "green": ("美国消费强劲→对全球出口型企业（含中国制造业）是支撑。", "对应中国出口链股票（家电、纺织、电子）；但通胀回落难度增加。"),
    "yellow":("消费温和。", "保持均衡配置。"),
    "red":   ("美国消费萎缩→衰退确认信号→出口承压。", "增配防御资产；回避出口链股票；关注中国内需消费替代板块。"),
  },

  # ── 中国 ────────────────────────────────────────
  "cn_cpi": {
    "green": ("通胀健康温和→央行政策稳定→消费板块（白酒、家电、食品饮料）受益。",
              "可适度增配消费板块ETF；维持均衡配置；现金类理财收益符合预期。"),
    "yellow":("通胀偏低→反映内需偏弱→货币宽松空间大→债券受益、消费板块承压。",
              "增配中长期国债ETF（如511260）；股票侧重高股息、央国企（红利ETF 510880）；房地产投资需谨慎。"),
    "red":   ("通胀异常（通缩或过热）→经济失衡→政策可能转向。",
              "通缩情景：增配长债、黄金，股票仅保留防御股。过热情景：减少长债，配置黄金、能源等抗通胀资产。"),
  },
  "cn_ppi": {
    "green": ("PPI转正→工业企业盈利修复→周期股（钢铁、有色、化工、煤炭）业绩有望改善。",
              "可适度增加周期主题ETF（有色金属159980、煤炭515220）；制造业转型也可关注。"),
    "yellow":("PPI仍弱势→工业品价格通缩持续→上游承压、下游成本受益。",
              "回避周期股，增配下游消费（白酒、家电）；高股息防御策略仍有效。"),
    "red":   ("工业深度通缩→制造业普遍亏损→可能引发产能出清或政策强刺激。",
              "短期回避所有周期类资产；密切关注政策出台信号（财政、地产松绑）；股票侧重必需消费内需。"),
  },
  "cn_gdp": {
    "green": ("GDP达标→经济稳健运行→A股基本面预期支撑。", "维持现有A股配置；定投宽基ETF是好选择。"),
    "yellow":("GDP略低于目标→政策仍需发力→市场情绪谨慎。", "保持均衡配置；侧重高股息防御板块；现金保留10–20%伺机加仓。"),
    "red":   ("GDP明显偏离目标→大概率触发刺激政策→短期或有波动，但中期是布局窗口。",
              "分批逆向加仓宽基ETF；关注政策受益板块（基建、地产、消费）；不要在悲观中割肉。"),
  },
  "cn_mfg_pmi": {
    "green": ("制造业扩张→工业链上下游受益→原材料、机械、化工股有支撑。", "可适度配置周期ETF（有色、煤炭、化工）；关注大宗商品价格联动。"),
    "yellow":("制造业疲软或边缘扩张→等待政策托底信号。", "保持均衡，回避过度押注周期；红利防御策略继续有效。"),
    "red":   ("制造业明显收缩→经济动能不足→大宗承压。", "回避周期股；增配债券和高股息防御板块；现金保留待政策刺激信号。"),
  },
  "cn_svc_pmi": {
    "green": ("服务业稳健扩张→消费板块（餐饮、旅游、零售）景气向好。", "可适度增配消费ETF（消费159928、食品饮料159996）。"),
    "yellow":("服务业弱扩张→消费温和复苏。", "保持现有消费板块配置，无需大动作。"),
    "red":   ("服务业收缩→消费动能不足→消费股承压。", "回避可选消费（旅游、餐饮），保留必需消费（食品饮料、药品）。"),
  },
  "cn_lpr": {
    "green": ("LPR处于低位→房贷利率友好（首套约3–4%）→借款成本低、存款收益也低。",
              "现房贷关注是否可转换利率；新购房可受益于利率下行；存款类资产收益不及通胀，用债券基金/中长期理财补充。"),
    "yellow":("LPR中性偏低→政策仍有降息空间。",
              "现有浮动房贷会自动跟随下行；现金类理财收益可能继续走低，提前锁定中长期固收。"),
    "red":   ("LPR若处于历史高位（罕见）→新增房贷成本上升。",
              "暂缓加杠杆购房；现有浮动房贷需评估月供承受能力；存款收益短期上升。"),
  },
  "cn_market": {
    "green": ("上证处于上升趋势→市场情绪偏暖→融资活跃。",
              "继续持有现有仓位；新资金分批定投宽基ETF；高估值题材股止盈一部分；避免追高。"),
    "yellow":("A股震荡格局，缺乏明确方向。",
              "网格交易或定投平摊成本；现金保留10–20%伺机加仓；避免重仓单一题材。"),
    "red":   ("A股下行趋势→悲观情绪占主导→但深跌往往孕育中长期机会。",
              "分批逆向买入红利ETF（510880）、银行/公用板块；定投宽基降低成本；避免使用杠杆；不要轻易割肉。"),
  },
  "cn_hs300": {
    "green": ("沪深300（A股核心资产）上行→机构资金回流→白酒、银行、保险等龙头受益。", "可定投沪深300ETF（510300）；外资若持续流入是积极信号。"),
    "yellow":("沪深300震荡。", "定投策略最优；不必择时。"),
    "red":   ("沪深300下行→核心资产估值收缩→机构持仓承压。", "分批加仓沪深300ETF；时间是逆向投资者的朋友。"),
  },
  "hk_market": {
    "green": ("恒生上行→外资对中国资产情绪改善→港股通板块受益。", "通过港股通可适度配置恒生ETF（513180）或港股科技ETF（513380）。"),
    "yellow":("港股震荡。", "保持现有配置。"),
    "red":   ("恒生下行→外资撤离→AH溢价或上升。", "港股估值已较低（PE通常低于A股），分批配置可能是机会，但需有耐心。"),
  },

  # ── 日本 ────────────────────────────────────────
  "jp_cpi": {
    "green": ("日本通胀达标→BOJ加息周期可持续→日元升值预期。", "持有日元资产或日股QDII受益；套利交易（Carry Trade）平仓引发的全球波动需注意。"),
    "yellow":("日本通胀偏低，BOJ政策正常化进程缓慢。", "对个人配置影响有限；维持现状。"),
    "red":   ("日本通胀异常（通缩或失控）。", "通缩：日元保值属性；失控：BOJ加息加快，全球流动性紧张，需提高防御。"),
  },
  "jp_rate": {
    "green": ("日本零利率延续→套利交易活跃→全球流动性宽松。", "对全球风险资产是顺风；但需警惕未来BOJ转向时的剧烈调整。"),
    "yellow":("BOJ温和加息周期→套利交易部分平仓→日元升值。", "波动可能加大；持有日元类资产受益；回避高杠杆全球资产。"),
    "red":   ("BOJ激进加息→全球套利交易大规模平仓→风险资产剧烈调整。", "提高现金/防御性资产比例；避免新增高杠杆；这种环境下黄金、日元都是避险标的。"),
  },
  "jp_market": {
    "green": ("日经上行→日元贬值+企业盈利双重驱动。", "QDII日股基金可参与；但需注意日元汇率风险（如未对冲，回报可能被汇率吃掉）。"),
    "yellow":("日经震荡。", "对个人非核心配置，无需调整。"),
    "red":   ("日经下行→通常伴随日元升值（避险情绪）。", "回避日股，但日元资产有避险属性。"),
  },
  "usdjpy": {
    "green": ("日元偏强（汇率<130）→出口商承压→日经压力。", "如有日股仓位，关注日元升值带来的汇兑收益。"),
    "yellow":("中性区间。", "无需特别行动。"),
    "red":   ("日元过弱（>150）→日本央行可能干预→可能引发剧烈反转。", "持有日股需关注汇率反转风险；不建议此时新增日元资产。"),
  },

  # ── 欧元区 ──────────────────────────────────────
  "eu_cpi": {
    "green": ("欧元区通胀达标→ECB降息持续→欧债欧股受益。", "QDII欧洲ETF有机会；但欧洲股市流动性和增长性都不如美股。"),
    "yellow":("欧元区通胀仍偏高，ECB政策受制约。", "对个人配置影响有限。"),
    "red":   ("欧元区通胀失控或通缩。", "通常是欧洲经济结构性问题，回避欧洲风险资产。"),
  },
  "eu_rate": {
    "green": ("ECB宽松→欧元承压→对欧元区出口商有利。", "影响相对间接，不必特别配置。"),
    "yellow":("ECB中性。", "无影响。"),
    "red":   ("ECB限制性利率→欧债承压。", "回避欧洲风险资产。"),
  },
  "eu_market": {
    "green": ("DAX上行→德国出口和制造业景气→对全球工业链是积极信号。", "可关注中国对欧出口链股票；DAX的QDII配置作用相对有限。"),
    "yellow":("DAX震荡。", "无需调整。"),
    "red":   ("DAX下行→欧洲经济压力大→中国对欧出口承压。", "回避德国汽车产业链相关A股（如对欧出口的零部件供应商）。"),
  },

  # ── 全球市场 ────────────────────────────────────
  "sp500": {
    "green": ("标普500上行→全球风险偏好高→A股流动性预期改善。",
              "QDII美股基金（标普500 ETF如513500）持有受益；但需注意估值是否过高（PE>25倍需警惕）。"),
    "yellow":("标普500震荡。", "定投策略仍是最优解；不必频繁交易。"),
    "red":   ("标普500下行→全球风险偏好下降→A股流动性也受影响。",
              "QDII美股短期承压，但深跌往往是长期布局机会；分批定投，不追高也不恐慌出清。"),
  },
  "vix": {
    "green": ("市场情绪正常→无明显机会信号。", "维持现有配置；可在区间内做小幅调仓优化。"),
    "yellow":("市场过度紧张或过度自满→结构性风险积累。",
              "VIX异常低（<13）：减少高估值仓位；VIX在20–30：适度逆向加仓优质股。"),
    "red":   ("市场恐慌→历史上往往是优质资产的折价买入时机（2008、2020都是典型）。",
              "分批逆向买入指数ETF（沪深300、标普500）；避免使用杠杆；不要在恐慌中卖出底仓。"),
  },
  "dxy": {
    "green": ("弱美元→人民币升值→进口商品（汽车、化妆品）便宜→海外旅游/留学性价比提升。",
              "海外消费/留学的换汇时机较好；境内黄金ETF（518880）继续看涨；A股流动性改善预期。"),
    "yellow":("美元中性→无明显方向偏好。", "保持现有配置；不必专门对冲汇率。"),
    "red":   ("强美元→人民币贬值→进口商品涨价→海外消费/留学成本上升→A股流动性受抑。",
              "未来海外大额开支可分批换汇锁定汇率；境内增加黄金对冲；减少A股集中度，增加防御板块。"),
  },
  "gold": {
    "green": ("金价上涨→反映美元走弱、避险需求或央行购金强劲。",
              "持有黄金继续持有；新增配置分批定投而非追高；金价高位时实物投资金条性价比下降，ETF更优。"),
    "yellow":("金价震荡→无明确方向。", "黄金作为长期配置工具（5–10%总资产），可继续定投；不必频繁交易。"),
    "red":   ("金价回落→可能反映美元走强或避险情绪退潮。",
              "如长期看好，分批补仓是机会；不必恐慌减仓——黄金的核心价值是长期对冲，不是短期投机。"),
  },
  "oil": {
    "green": ("油价中性区间→对家庭加油成本和制造业成本影响有限。", "无需特别行动；能源股估值合理，可作为均衡配置一部分。"),
    "yellow":("高油价→推升通胀和家庭交通成本→CPI压力增大→航空、化工等下游受损，能源股受益。",
              "可适度增配能源股（中石油、中海油），减配航空和化工；个人开支考虑电动车补贴或公共交通替代。"),
    "red":   ("油价低位→反映需求疲软或供给过剩→家庭加油成本下降→能源股盈利承压。",
              "回避能源股；油价反弹时航空板块有交易机会；家庭交通成本降低，是阶段性消费升级窗口。"),
  },
  "copper": {
    "green": ("铜价上行→反映全球需求向好（尤其中国基建）→工业景气。", "适度配置有色金属ETF（159980）；铜与A股周期股相关性高。"),
    "yellow":("铜价震荡。", "保持现有配置。"),
    "red":   ("铜价大跌→反映全球需求疲软→衰退预警。", "回避周期股；增配黄金、防御板块。"),
  },
}

def _trend_signal(ind):
    """对没有数值阈值的指标（市场指数等），从12月趋势推断信号色"""
    trend = ind.get("trend_values", [])
    if len(trend) < 6 or not trend[0]: return None
    yoy = (ind["value"] / trend[0] - 1) * 100
    if yoy > 10:  return "green"
    if yoy < -10: return "red"
    return "yellow"

def _personal_advice(iid, ind):
    """返回(impact, action)；找不到规则或信号无法判断时返回(None, None)"""
    rules = PERSONAL_IMPACT.get(iid)
    if not rules: return (None, None)
    color = ind.get("signal_color", "neutral")
    if color == "neutral":   # 市场指数：用趋势作为fallback信号
        color = _trend_signal(ind) or "neutral"
    advice = rules.get(color)
    if not advice or len(advice) != 2: return (None, None)
    return advice

# ═══════════════════════════════════════════════════════════
# 7.6 综合概览引擎：告警 / 风险评分 / 资产配置 / 历史回测
# ═══════════════════════════════════════════════════════════

# ── 7.6.1 关键指标变动告警 ─────────────────────────
ALERT_RULES = {
    # iid: (中文标签, 模式, 阈值, 单位)
    # 模式: "abs"=绝对差; "pct"=百分比变化
    "us_cpi":     ("美国CPI",       "abs", 0.5,  "%"),
    "us_pce":     ("核心PCE",       "abs", 0.3,  "%"),
    "us_rate":    ("联邦利率",      "abs", 0.25, "%"),
    "us_t10":     ("10年美债",      "abs", 0.3,  "%"),
    "us_payroll": ("非农就业",      "abs", 10,   "万人"),
    "cn_cpi":     ("中国CPI",       "abs", 0.5,  "%"),
    "cn_ppi":     ("中国PPI",       "abs", 1.0,  "%"),
    "cn_lpr":     ("LPR",          "abs", 0.10, "%"),
    "cn_mfg_pmi": ("中国制造业PMI", "abs", 1.5,  "点"),
    "vix":        ("VIX恐慌指数",   "abs", 5.0,  "点"),
    "dxy":        ("美元指数",      "abs", 2.0,  "点"),
    "gold":       ("黄金",         "pct", 5,    "%"),
    "oil":        ("原油",         "pct", 10,   "%"),
    "sp500":      ("标普500",      "pct", 5,    "%"),
    "cn_market":  ("上证综指",     "pct", 5,    "%"),
    "cn_hs300":   ("沪深300",      "pct", 5,    "%"),
    "hk_market":  ("恒生指数",     "pct", 5,    "%"),
    "jp_market":  ("日经225",      "pct", 5,    "%"),
}

def _all_cards(data):
    """遍历数据中所有指标卡片"""
    for region in data.get("regions", {}).values():
        for section in region.get("sections", {}).values():
            for card in section: yield card

def detect_alerts(data):
    """检测关键指标的显著变动（基于上月→当月）"""
    alerts = []
    for card in _all_cards(data):
        if card.get("error"): continue
        rule = ALERT_RULES.get(card.get("id"))
        if not rule: continue
        label, mode, thr, unit = rule
        trend = card.get("trend_values", [])
        if len(trend) < 2: continue
        try:
            prev, curr = float(trend[-2]), float(trend[-1])
        except: continue

        if mode == "abs":
            diff = curr - prev
            if abs(diff) >= thr:
                direction = "上升" if diff > 0 else "下降"
                alerts.append({
                    "label": label,
                    "msg": f"{direction} {abs(diff):.2f}{unit}（{prev:.2f} → {curr:.2f}）",
                    "severity": "high" if abs(diff) >= thr * 2 else "med",
                })
        elif mode == "pct":
            if prev == 0: continue
            pct = (curr / prev - 1) * 100
            if abs(pct) >= thr:
                direction = "上涨" if pct > 0 else "下跌"
                alerts.append({
                    "label": label,
                    "msg": f"{direction} {abs(pct):.1f}%（{prev:.1f} → {curr:.1f}）",
                    "severity": "high" if abs(pct) >= thr * 2 else "med",
                })
    alerts.sort(key=lambda x: 0 if x["severity"] == "high" else 1)
    return alerts


# ── 7.6.2 综合风险偏好评分 ────────────────────────
# 每个指标对"是否利好风险资产"的评分 (绿/黄/红)
# 正值=利好风险资产 (股票), 负值=利好防御资产 (现金/债券/黄金)
RISK_SCORES = {
    # 美国：通胀/利率低=利好；过高=不利
    "us_cpi":     ( 6,  0, -10),
    "us_pce":     ( 3,  0,  -5),
    "us_rate":    ( 6,  0, -10),
    "us_t10":     ( 3,  0,  -5),
    "us_payroll": ( 2, -1,  -5),
    "us_gdp":     ( 5, -2, -10),
    "us_indpro":  ( 3, -1,  -3),
    "us_retail":  ( 3,  0,  -3),
    # 中国：本国指标加权较高（用户在境内）
    "cn_cpi":     ( 5, -3,  -5),
    "cn_ppi":     ( 5, -2,  -5),
    "cn_gdp":     ( 6, -3, -10),
    "cn_mfg_pmi": ( 5, -2,  -6),
    "cn_svc_pmi": ( 3,  0,  -3),
    "cn_lpr":     ( 3,  0,  -3),
    "cn_market":  ( 6,  0,  -3),
    "cn_hs300":   ( 3,  0,  -2),
    "hk_market":  ( 3,  0,  -2),
    # 日本/欧元区：低权重
    "jp_cpi":     ( 1,  0,  -1),
    "jp_rate":    ( 2,  0,  -3),
    "jp_market":  ( 1,  0,  -1),
    "usdjpy":     ( 0,  0,  -2),
    "eu_cpi":     ( 1,  0,  -1),
    "eu_rate":    ( 1,  0,  -2),
    "eu_market":  ( 1,  0,  -1),
    # 全球市场：DXY 对国内影响大；VIX红色其实是逆向机会
    "sp500":      ( 5,  0,  -3),
    "vix":        ( 3, -3,   2),  # 红色=恐慌=反向加分（逆向买入）
    "dxy":        ( 5,  0, -10),
    "gold":       (-1,  0,   1),  # 金涨通常伴随不确定性
    "oil":        ( 1, -2,  -1),
    "copper":     ( 3,  0,  -3),
}

def calc_risk_score(data):
    """计算综合风险偏好评分 (-100 极防御 ~ +100 极风险偏好)"""
    total = 0; max_abs = 0
    contribs = []
    for card in _all_cards(data):
        if card.get("error"): continue
        iid = card.get("id")
        rule = RISK_SCORES.get(iid)
        if not rule: continue
        g, y, r = rule
        color = card.get("signal_color", "neutral")
        if color == "neutral":
            color = _trend_signal(card) or "neutral"
        if color == "neutral": continue
        score = {"green": g, "yellow": y, "red": r}.get(color, 0)
        total += score
        max_abs += max(abs(g), abs(r))
        if abs(score) >= 2:
            contribs.append({"label": card.get("name", iid), "score": score, "color": color})

    if max_abs == 0:
        return {"score": 0, "regime": "数据不足", "regime_color": "yellow",
                "drags": [], "supports": []}

    norm = round(total / max_abs * 100, 1)
    if   norm >=  40: regime, rcolor = "强顺风（利好风险资产）", "green"
    elif norm >=  15: regime, rcolor = "顺风（偏向风险资产）",   "green"
    elif norm >  -15: regime, rcolor = "中性（建议均衡配置）",   "yellow"
    elif norm >  -40: regime, rcolor = "逆风（偏向防御）",       "yellow"
    else:             regime, rcolor = "强逆风（高度防御）",     "red"

    drags    = sorted([c for c in contribs if c["score"] < 0], key=lambda x: x["score"])[:5]
    supports = sorted([c for c in contribs if c["score"] > 0], key=lambda x: -x["score"])[:5]
    return {"score": norm, "regime": regime, "regime_color": rcolor,
            "drags": drags, "supports": supports}


# ── 7.6.3 资产配置推荐 ────────────────────────────
def get_allocation(score):
    """基于风险评分动态调整两套配置（进取型 / 防御型）"""
    s = score / 10   # 调整因子
    aggressive = {
        "股票": 60 + s * 3.0,
        "债券": 25 - s * 1.5,
        "黄金":  5 + max(0, -s) * 0.5,
        "现金": 10 - s * 1.0,
    }
    defensive = {
        "股票": 30 + s * 2.0,
        "债券": 50 - s * 1.0,
        "黄金": 10 + max(0, -s) * 0.8,
        "现金": 10 - s * 0.5,
    }
    def normalize(d):
        for k in d: d[k] = max(3, min(85, d[k]))
        total = sum(d.values())
        return {k: round(v / total * 100, 1) for k, v in d.items()}
    return {"aggressive": normalize(aggressive), "defensive": normalize(defensive)}


# ── 7.6.4 历史相似时点匹配 ────────────────────────
HISTORICAL_SCENARIOS = [
    {
        "id": "2008_gfc", "name": "2008 金融危机",
        "period": "2008-Q3 ~ 2009-Q1",
        "summary": "次贷危机引发全球流动性冻结，VIX飙至89历史峰值，美联储紧急降息至零，标普半年跌38%。",
        "fingerprint": {
            "vix": "red", "us_rate": "green", "sp500": "red", "gold": "green",
            "us_payroll": "red", "us_gdp": "red", "us_cpi": "yellow",
            "cn_market": "red", "dxy": "yellow",
        },
        "performance": {
            "美股(标普500)": "-38%", "黄金": "+5%", "长期国债": "+20%",
            "美元指数": "+15%", "新兴市场股票": "-50%", "原油": "-50%",
        },
        "lesson": "极端恐慌点是优质资产折价买入窗口。当时坚持持有并在VIX回落到30以下时分批进场风险资产，可以抓住历史性反弹（标普2009-2011累计+90%）。",
    },
    {
        "id": "2018_q4", "name": "2018 Q4 抛售",
        "period": "2018-10 ~ 2018-12",
        "summary": "美联储紧缩+中美贸易战，全球股市Q4回调，VIX飙升，但2019初Fed转向后V型反弹。",
        "fingerprint": {
            "us_rate": "red", "us_t10": "red", "vix": "yellow", "sp500": "red",
            "us_cpi": "yellow", "us_payroll": "green", "dxy": "yellow",
            "cn_market": "red",
        },
        "performance": {
            "美股(标普500)": "-14% (Q4单季)", "黄金": "+7%", "美债10年": "+3%",
            "原油": "-38%", "A股(沪深300)": "-12%",
        },
        "lesson": "美联储紧缩末期+地缘冲突是典型的'股债双弱'环境。事后看，Fed转向后股市快速反弹，提前埋伏债券和黄金的可平稳过渡。",
    },
    {
        "id": "2020_covid", "name": "2020 新冠崩盘",
        "period": "2020-02 ~ 2020-04",
        "summary": "新冠全球大流行引发恐慌，VIX飙至80以上，但央行天量放水后市场快速V型反弹。",
        "fingerprint": {
            "vix": "red", "us_rate": "green", "sp500": "red", "gold": "green",
            "us_payroll": "red", "us_gdp": "red", "dxy": "yellow",
            "oil": "red", "cn_market": "yellow",
        },
        "performance": {
            "美股(标普500)": "崩-34% 后反弹+18% (年内)", "黄金": "+25%",
            "美债": "+12%", "原油": "短暂负油价", "比特币": "+300% (年内)",
        },
        "lesson": "央行'无限量宽'下V型反弹比预期快。永远不要在恐慌中清仓优质资产。当时分批买入定投宽基ETF的，2年回报普遍翻倍。",
    },
    {
        "id": "2022_inflation", "name": "2022 通胀冲击",
        "period": "2022 全年",
        "summary": "俄乌冲突+疫后供应链问题导致40年最高通胀，美联储激进加息525bp，股债同时大跌。",
        "fingerprint": {
            "us_cpi": "red", "us_pce": "red", "us_rate": "red", "us_t10": "red",
            "sp500": "red", "dxy": "red", "gold": "yellow", "oil": "yellow",
            "cn_market": "red",
        },
        "performance": {
            "美股(标普500)": "-19%", "美债20年+": "-31%",
            "60/40组合": "-16% (历史最差)", "黄金": "-1%", "原油": "+7%",
            "美元(DXY)": "+8%",
        },
        "lesson": "高通胀+加息环境下，传统股债组合失效。能源股、抗通胀债券（TIPS）、现金（美元）、大宗商品相对受益；杠杆和长久期资产是大忌。",
    },
    {
        "id": "2015_china_crash", "name": "2015 A股股灾",
        "period": "2015-06 ~ 2016-02",
        "summary": "去杠杆引发A股断崖暴跌，沪深300半年腰斩，叠加人民币'811汇改'贬值压力。",
        "fingerprint": {
            "cn_market": "red", "cn_hs300": "red", "dxy": "red",
            "cn_cpi": "yellow", "cn_mfg_pmi": "red", "hk_market": "red",
        },
        "performance": {
            "上证综指": "-49% (峰底)", "沪深300": "-46%",
            "人民币兑美元": "-7%", "黄金": "+10%", "美股(标普500)": "区间震荡",
        },
        "lesson": "A股去杠杆+汇率贬值是最不利组合。当时持有黄金、美元资产（QDII）的投资者明显跑赢；事后看2016下半年A股完成筑底，长期定投者获利。",
    },
]

def find_historical_match(data):
    """对比当前信号与历史场景，返回匹配度最高的前3个"""
    current = {}
    for card in _all_cards(data):
        if card.get("error"): continue
        iid = card.get("id")
        color = card.get("signal_color", "neutral")
        if color == "neutral":
            color = _trend_signal(card) or "neutral"
        current[iid] = color

    results = []
    for sc in HISTORICAL_SCENARIOS:
        m, t = 0, 0
        for sid, expected in sc["fingerprint"].items():
            cur = current.get(sid)
            if cur and cur != "neutral":
                t += 1
                if cur == expected: m += 1
        if t >= 3:   # 至少3个有效信号才纳入对比
            results.append({**sc, "match_pct": round(m/t*100), "matched": m, "total": t})
    results.sort(key=lambda x: -x["match_pct"])
    return results[:3]


def build_overview(data):
    """构建综合概览数据块"""
    risk = calc_risk_score(data)
    return {
        "alerts":     detect_alerts(data),
        "risk":       risk,
        "allocation": get_allocation(risk["score"]),
        "historical": find_historical_match(data),
    }


# ═══════════════════════════════════════════════════════════
# 8. 组装单个指标卡片数据
# ═══════════════════════════════════════════════════════════
def _check_stale(card, max_age_months=6):
    """如果数据老于 max_age_months 个月，添加陈旧标记"""
    if not card or card.get('error'): return card
    try:
        d = card.get("date", "")
        if len(d) >= 7:
            yr, mo = int(d[:4]), int(d[5:7])
            data_dt = datetime(yr, mo, 1)
            now = datetime.now()
            age = (now.year - yr) * 12 + (now.month - mo)
            if age >= max_age_months:
                card["stale"] = True
                card["stale_msg"] = f"数据滞后 {age} 个月"
    except: pass
    return card

def _card(iid, raw):
    name, unit, desc, rules, pmi_line = IND.get(iid, (iid,""," "," ",None))
    if not raw:
        return {"id":iid,"name":name,"unit":unit,"error":True,
                "desc":desc,"rules":rules,"pmi_line":pmi_line}
    v = raw["value"]
    sc, sl = _signal(iid, v)
    card = {
        "id": iid, "name": name, "unit": unit, "error": False,
        "value": v, "date": raw.get("date",""),
        "change_pct": raw.get("change_pct"),
        "signal_color": sc, "signal_text": sl,
        "trend_labels": raw.get("trend_labels",[]),
        "trend_values": raw.get("trend_values",[]),
        "desc": desc, "rules": rules, "pmi_line": pmi_line,
    }
    card["interpret"] = interpret(iid, card)
    impact, action = _personal_advice(iid, card)
    card["impact"] = impact
    card["action"] = action
    return _check_stale(card)

# ═══════════════════════════════════════════════════════════
# 7.7  综合面板（资产配置 / 告警 / 历史相似度）
# ═══════════════════════════════════════════════════════════

# 每个指标的"风险偏好得分贡献"——绿/黄/红三档对应得分
SIGNAL_SCORES = {
    # 通胀类（红 = 高通胀 = 对风险资产负面）
    "us_cpi":(5,-3,-10), "us_pce":(5,-3,-10), "cn_cpi":(3,-2,-5),
    "cn_ppi":(5,-3,-8),  "eu_cpi":(3,-2,-5),  "jp_cpi":(2,-2,-4),
    # 利率/流动性类（绿 = 宽松）
    "us_rate":(8,0,-10), "us_t10":(5,0,-8),   "cn_lpr":(5,0,-3),
    "jp_rate":(1,0,-1),  "eu_rate":(1,0,-1),  "dxy":(3,0,-5),
    # 经济景气类（绿 = 扩张）
    "us_payroll":(5,0,-5),"us_gdp":(6,-2,-10),"us_indpro":(4,-2,-6),
    "us_retail":(4,0,-6), "cn_gdp":(6,-2,-8), "cn_mfg_pmi":(5,-3,-7),
    "cn_svc_pmi":(4,-2,-5),"copper":(3,0,-3),
    # 风险情绪类
    "vix":(5,-2,-8), "sp500":(4,0,-4), "cn_market":(5,0,-5),
    "cn_hs300":(3,0,-3), "hk_market":(3,0,-3), "jp_market":(1,0,-1),
    "eu_market":(1,0,-1), "usdjpy":(1,0,-1),
    # 大宗商品（黄金反向：金价上涨 = 避险情绪 = 风险偏好低）
    "gold":(-2,0,2), "oil":(2,-3,-2),
}

# 指标→大类映射（用于分项打分）
COMPONENT_MAP = {
    "us_cpi":"inflation","us_pce":"inflation","cn_cpi":"inflation",
    "cn_ppi":"inflation","eu_cpi":"inflation","jp_cpi":"inflation","oil":"inflation",
    "us_rate":"liquidity","us_t10":"liquidity","cn_lpr":"liquidity",
    "jp_rate":"liquidity","eu_rate":"liquidity","dxy":"liquidity",
    "us_payroll":"cycle","us_gdp":"cycle","us_indpro":"cycle","us_retail":"cycle",
    "cn_gdp":"cycle","cn_mfg_pmi":"cycle","cn_svc_pmi":"cycle","copper":"cycle",
    "vix":"sentiment","sp500":"sentiment","cn_market":"sentiment",
    "cn_hs300":"sentiment","hk_market":"sentiment","jp_market":"sentiment",
    "eu_market":"sentiment","usdjpy":"sentiment","gold":"sentiment",
}
COMPONENT_NAMES = {"inflation":"通胀环境","liquidity":"流动性",
                   "cycle":"经济景气","sentiment":"风险情绪"}

# 资产配置基线（按风险偏好型/稳健型）
ALLOC_BASE = {
    "进取型": {"股票":65, "债券":15, "黄金":10, "现金":10},
    "稳健型": {"股票":35, "债券":35, "黄金":10, "现金":20},
}
ALLOC_SENS = {"进取型":25, "稳健型":15}  # 股票仓位的浮动幅度

# 告警规则
ALERT_RULES = {
    "us_cpi":  {"red":"通胀严重偏离美联储目标，股债承压、黄金有支撑","mom":0.3,"since":0.3},
    "us_pce":  {"red":"核心通胀粘性强，美联储难以放松","since":0.3},
    "us_rate": {"red":"限制性高利率水平，全球流动性紧张","since":0.25},
    "us_t10":  {"red":"10年国债收益率高位，全球资产估值承压","since":0.3},
    "vix":     {"red":"市场恐慌！但历史上常对应阶段性底部，逆向布局窗口","mom_pct":30},
    "dxy":     {"red":"强美元环境，新兴市场和大宗承压","since":1.5,"mom_pct":2},
    "cn_cpi":  {"red":"通胀异常（通缩或过热），政策可能转向","since":0.3},
    "cn_ppi":  {"red":"工业深度通缩，企业盈利全面承压","since":0.5},
    "cn_lpr":  {"since":0.05},
    "cn_market":{"mom_pct":8},
    "cn_hs300":{"mom_pct":8},
    "sp500":   {"mom_pct":8},
    "gold":    {"mom_pct":6},
    "oil":     {"mom_pct":15},
}

# 历史时点指纹库（用于相似度匹配）
HISTORICAL_PERIODS = [
    {
        "name":"2008 Q4 雷曼危机", "date":"2008-09 至 2008-12",
        # 标志: 极端VIX、市场崩盘、就业崩塌、油价暴跌（中端流动性宽松)
        "fingerprint":{"vix":"red", "sp500":"red", "cn_market":"red",
            "us_payroll":"red", "us_gdp":"red", "oil":"red", "us_rate":"green"},
        "summary":"雷曼破产引发全球金融危机，VIX冲到80+，全球紧急降息和释放流动性。",
        "perf":"标普500 -38%（自年内高点），A股 -65%，黄金 +5%，长债 +20%（避险买盘）",
        "lesson":"极端恐慌后是历史性买入窗口——事后6-12个月内分批配置宽基指数和优质蓝筹回报丰厚。",
    },
    {
        "name":"2018 Q4 加息+贸易战", "date":"2018-10 至 2018-12",
        # 标志: 美元偏强、Fed加息高、长债收益率高、股市重挫但就业景气仍好
        "fingerprint":{"us_rate":"red", "us_t10":"red", "sp500":"red", "cn_market":"red",
            "dxy":"green", "us_payroll":"green", "us_gdp":"green", "vix":"yellow"},
        "summary":"美联储加息至2.5%叠加中美贸易战，全球股市暴跌但经济基本面尚健康。",
        "perf":"标普500 -20%（季度内），A股 -25%，黄金 +6%，长债 +5%",
        "lesson":"美联储2019年初转向后市场快速反弹（标普500当年+28%）——坚持持有优质龙头是正确选择。",
    },
    {
        "name":"2020 Q1 新冠冲击", "date":"2020-02 至 2020-04",
        # 标志: 极端VIX、Fed紧急降息至零、油价负值、就业崩塌、黄金避险
        "fingerprint":{"vix":"red", "us_rate":"green", "sp500":"red",
            "us_payroll":"red", "oil":"red", "gold":"green", "us_gdp":"red"},
        "summary":"新冠疫情全球扩散，原油暴跌至负值，美联储紧急降息至0+无限QE。",
        "perf":"标普500 -34%（一个月），原油负值，黄金 +15%，长债 +20%",
        "lesson":"央行无限放水后风险资产快速反弹，2020全年标普500反而 +18%。",
    },
    {
        "name":"2022-2023 高通胀+加息", "date":"2022-03 至 2023-03",
        # 标志: CPI/PCE高、利率高、长债收益率高、强美元、油价高（最具识别度）
        "fingerprint":{"us_cpi":"red", "us_pce":"red", "us_rate":"red", "us_t10":"red",
            "dxy":"red", "oil":"red", "sp500":"red"},
        "summary":"美国通胀冲到9%，美联储快速加息500bp，股债双杀（2022年罕见双重亏损年）。",
        "perf":"标普500 -19%，纳指 -32%，长债 -25%，黄金 +0%（被强美元压制）",
        "lesson":"高通胀+加息环境下，传统60/40组合失效——短债、能源股、防御板块更稳健。",
    },
    {
        "name":"2024-2025 软着陆+AI牛市", "date":"2024-01 至 2025-04",
        # 标志: VIX低位、美股新高、就业强劲、黄金创新高、通胀回落（独特组合）
        "fingerprint":{"vix":"green", "sp500":"green", "us_payroll":"green",
            "us_gdp":"green", "gold":"green", "us_cpi":"yellow"},
        "summary":"美国经济软着陆，AI热潮推动美股屡创新高；中国仍处于内需弱复苏。",
        "perf":"标普500 +25%（年化），黄金 +30%，A股 横盘，全球分化明显",
        "lesson":"宏观分化时代——单一押注风险大，全球分散+黄金对冲是稳健策略。",
    },
]

# ── 工具函数 ──────────────────────────────────────────
def _flat_cards(dashboard):
    """从 dashboard 数据结构中扁平化所有指标卡片"""
    cards = []
    for region in dashboard.get("regions", {}).values():
        for sec in region.get("sections", {}).values():
            for c in sec:
                cards.append(c)
    return cards

def _signal_of(card):
    """获取信号色：优先 _signal()，市场指数等用趋势 fallback"""
    sc = card.get("signal_color", "neutral")
    if sc == "neutral":
        sc = _trend_signal(card) or "neutral"
    return sc

# ── 核心计算 ──────────────────────────────────────────
def compute_macro_score(cards):
    """聚合所有指标→得到 -100（极度防御）至 +100（极度进取）的综合分"""
    total, max_pos, max_neg = 0, 0, 0
    for c in cards:
        if c.get("error"): continue
        s = SIGNAL_SCORES.get(c["id"])
        if not s: continue
        g, y, r = s
        sig = _signal_of(c)
        contrib = {"green":g, "yellow":y, "red":r}.get(sig, 0)
        total += contrib
        max_pos += max(g, y, r)
        max_neg += min(g, y, r)
    if max_pos == 0 and max_neg == 0: return 0
    if total >= 0:
        return round(total / max_pos * 100, 1) if max_pos > 0 else 0
    return round(total / abs(max_neg) * 100, 1) if max_neg < 0 else 0

def compute_components(cards):
    """按四大类（通胀/流动性/景气/情绪）分别计算得分"""
    cats = {k: [] for k in COMPONENT_NAMES}
    cat_max = {k: 0 for k in COMPONENT_NAMES}
    cat_min = {k: 0 for k in COMPONENT_NAMES}
    for c in cards:
        if c.get("error"): continue
        cat = COMPONENT_MAP.get(c["id"])
        if not cat: continue
        s = SIGNAL_SCORES.get(c["id"])
        if not s: continue
        g, y, r = s
        sig = _signal_of(c)
        contrib = {"green":g, "yellow":y, "red":r}.get(sig, 0)
        cats[cat].append(contrib)
        cat_max[cat] += max(g, y, r); cat_min[cat] += min(g, y, r)
    out = {}
    for cat, items in cats.items():
        if not items: out[cat] = 0; continue
        total = sum(items)
        if total >= 0:
            out[cat] = round(total / cat_max[cat] * 100) if cat_max[cat] > 0 else 0
        else:
            out[cat] = round(total / abs(cat_min[cat]) * 100) if cat_min[cat] < 0 else 0
    return out

def compute_allocations(score):
    """根据综合分推荐两套资产配置：进取型 / 稳健型"""
    f = max(-1, min(1, score / 100))
    out = {}
    for profile, base in ALLOC_BASE.items():
        sens = ALLOC_SENS[profile]
        shift = f * sens
        a = dict(base)
        if f >= 0:   # 风险偏好高：加股票，减债/金/现金
            a["股票"] += shift
            a["债券"] -= shift * 0.3
            a["黄金"] -= shift * 0.3
            a["现金"] -= shift * 0.4
        else:        # 风险偏好低：减股票，加债/金/现金
            a["股票"] += shift
            a["债券"] -= shift * 0.4
            a["黄金"] -= shift * 0.3
            a["现金"] -= shift * 0.3
        a = {k: max(0, round(v)) for k, v in a.items()}
        # 归一化到 100%
        diff = 100 - sum(a.values())
        a["现金"] = max(0, a["现金"] + diff)
        out[profile] = a
    return out

def generate_alerts(cards, prev_snapshot=None):
    """生成关键变动告警"""
    alerts = []
    prev_map = {p["id"]: p for p in (prev_snapshot or [])}
    for c in cards:
        if c.get("error"): continue
        rules = ALERT_RULES.get(c["id"])
        if not rules: continue
        unit = c.get("unit", "")

        # 1) 红色信号告警
        if _signal_of(c) == "red" and rules.get("red"):
            alerts.append({
                "level":"red", "indicator": c["name"],
                "value": f"{c['value']}{unit}", "msg": rules["red"],
            })

        # 2) 月度变化告警
        trend = c.get("trend_values", [])
        if len(trend) >= 2:
            prev_val = trend[-2]
            if prev_val:
                if "mom" in rules:
                    diff = c["value"] - prev_val
                    if abs(diff) >= rules["mom"]:
                        d = "上升" if diff > 0 else "下降"
                        alerts.append({"level":"yellow","indicator":c["name"],
                            "value":f"{c['value']}{unit}","msg":f"较上月{d} {abs(diff):.2f}{unit}"})
                if "mom_pct" in rules:
                    pct = (c["value"]/prev_val - 1) * 100
                    if abs(pct) >= rules["mom_pct"]:
                        d = "上涨" if pct > 0 else "下跌"
                        alerts.append({"level":"yellow","indicator":c["name"],
                            "value":f"{c['value']}{unit}","msg":f"较上月{d} {abs(pct):.1f}%"})

        # 3) 与上次运行对比
        prev = prev_map.get(c["id"])
        if prev and "value" in prev and "since" in rules:
            delta = c["value"] - prev["value"]
            if abs(delta) >= rules["since"]:
                d = "上升" if delta > 0 else "下降"
                alerts.append({"level":"yellow","indicator":c["name"],
                    "value":f"{c['value']}{unit}","msg":f"较上次运行{d} {abs(delta):.2f}{unit}"})
    return alerts[:10]

def compute_history_match(cards):
    """对比当前各指标信号色 vs 历史时点指纹，按相似度排序。
       打分: 完全匹配 +1, 相邻(含黄色) +0.3, 反向(绿红) -0.5"""
    cur = {c["id"]: _signal_of(c) for c in cards if not c.get("error")}
    matches = []
    for p in HISTORICAL_PERIODS:
        score, total = 0.0, 0
        for iid, hist_sig in p["fingerprint"].items():
            if iid not in cur or cur[iid] == "neutral": continue
            total += 1
            cur_sig = cur[iid]
            if cur_sig == hist_sig:
                score += 1.0          # 完全匹配
            elif "yellow" in (cur_sig, hist_sig):
                score += 0.3          # 相邻（其中一个是黄色）
            else:
                score -= 0.5          # 反向（一个绿一个红）
        if total < 4: continue
        sim = max(0, score / total) * 100
        matches.append({**p, "similarity": round(sim, 1)})
    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return matches[:3]

def build_summary_panel(cards, prev_snapshot=None):
    """组装综合面板的所有数据"""
    score = compute_macro_score(cards)
    if score >= 30:    regime = ("明显偏向风险偏好", "green")
    elif score >= 10:  regime = ("略偏风险偏好",     "green")
    elif score >= -10: regime = ("中性平衡",         "yellow")
    elif score >= -30: regime = ("略偏防御",         "yellow")
    else:              regime = ("明显偏防御",       "red")
    return {
        "score": score, "regime_text": regime[0], "regime_color": regime[1],
        "components": compute_components(cards),
        "allocations": compute_allocations(score),
        "alerts": generate_alerts(cards, prev_snapshot),
        "histories": compute_history_match(cards),
    }

# ── 快照持久化（用于"较上次运行"对比）─────────────────
def _snapshot_path():
    return SCRIPT_DIR / ".dashboard_snapshot.json"

def load_snapshot():
    p = _snapshot_path()
    if not p.exists(): return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except: return None

def save_snapshot(cards):
    snap = [{"id":c["id"], "value":c["value"], "date":c.get("date"),
             "signal_color":c.get("signal_color")}
            for c in cards if not c.get("error")]
    try:
        _snapshot_path().write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    except: pass


# ═══════════════════════════════════════════════════════════
# 8. 全量数据采集
# ═══════════════════════════════════════════════════════════
def fetch_all(key):
    print("⏳ 正在采集数据……\n")

    # ── 美国 ──────────────────────────────────────────
    print("  [1/5] 美国…")
    us_pay = fred_get("PAYEMS", key, "mom")
    if us_pay:  # 千人 → 万人
        us_pay["value"]        = round(us_pay["value"] / 100, 1)
        us_pay["trend_values"] = [round(v/100,1) for v in us_pay["trend_values"]]

    # ── 中国 ──────────────────────────────────────────
    print("  [2/5] 中国…")
    cn_cpi = ak_china_cpi() or fred_get("CHNCPIALLMINMEI", key, "yoy")
    cn_mfg, cn_svc = ak_china_pmi_both()
    cn_ppi = ak_china_ppi()
    cn_gdp = ak_china_gdp()
    cn_lpr = ak_china_lpr()

    # ── 日本 ──────────────────────────────────────────
    print("  [3/5] 日本…")

    # ── 欧元区 ────────────────────────────────────────
    print("  [4/5] 欧元区…")

    # ── 全球市场 ──────────────────────────────────────
    print("  [5/5] 全球市场…")

    data = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "regions": {
            "us": {
                "name": "🇺🇸 美国",
                "sections": {
                    "通胀与货币政策": [
                        _card("us_cpi",  fred_get("CPIAUCSL",       key,"yoy")),
                        _card("us_pce",  fred_get("PCEPILFE",        key,"yoy")),
                        _card("us_rate", fred_get("FEDFUNDS",        key,"latest")),
                        _card("us_t10",  fred_get("DGS10",           key,"latest")),
                    ],
                    "经济景气": [
                        _card("us_payroll", us_pay),
                        _card("us_gdp",     fred_get("A191RL1Q225SBEA",key,"latest")),
                        _card("us_indpro",  fred_get("INDPRO",          key,"yoy")),
                        _card("us_retail",  fred_get("RSAFS",           key,"yoy")),
                    ],
                }
            },
            "cn": {
                "name": "🇨🇳 中国",
                "sections": {
                    "宏观经济": [
                        _card("cn_cpi",     cn_cpi),
                        _card("cn_ppi",     cn_ppi),
                        _card("cn_gdp",     cn_gdp),
                    ],
                    "景气指标": [
                        _card("cn_mfg_pmi", cn_mfg),
                        _card("cn_svc_pmi", cn_svc),
                    ],
                    "货币政策": [
                        _card("cn_lpr",     cn_lpr),
                    ],
                    "资本市场": [
                        _card("cn_market", ak_index_monthly("000001") or yf_get("000001.SS")),
                        _card("cn_hs300",  ak_index_monthly("000300") or yf_get("000300.SS")),
                        _card("hk_market", yf_get("^HSI")),
                    ],
                }
            },
            "jp": {
                "name": "🇯🇵 日本",
                "sections": {
                    "宏观经济": [
                        # 日本CPI：先试新的"已是同比%"序列，失败则用旧索引算同比
                        _card("jp_cpi",
                            fred_get("CPALTT01JPM659N", key, "latest")  # OECD新序列，直接是YoY%
                            or fred_get("JPNCPIALLMINMEI", key, "yoy")), # 旧索引，计算YoY
                        # 日本利率：两个序列都是%，可以用chain
                        _card("jp_rate", fred_get_chain(
                            ["IRSTCI01JPM156N", "INTDSRJPM193N"], key, "latest")),
                    ],
                    "资本市场": [
                        _card("jp_market", yf_get("^N225")),
                        _card("usdjpy",    yf_get("USDJPY=X")),
                    ],
                }
            },
            "eu": {
                "name": "🇪🇺 欧元区",
                "sections": {
                    "宏观经济": [
                        _card("eu_cpi",
                            fred_get("CPHPTT01EZM659N", key, "latest")     # 欧元区HICP同比%
                            or fred_get("CP0000EZ19M086NEST", key, "yoy")), # 旧序列，计算YoY
                        _card("eu_rate", fred_get("ECBDFR", key, "latest")),
                    ],
                    "资本市场": [
                        _card("eu_market", yf_get("^GDAXI")),
                    ],
                }
            },
            "global": {
                "name": "🌐 全球市场",
                "sections": {
                    "股票与情绪": [
                        _card("sp500", yf_get("^GSPC")),
                        _card("vix",   yf_get("^VIX")),
                        _card("dxy",   yf_get("DX-Y.NYB")),
                    ],
                    "大宗商品": [
                        _card("gold",   yf_get("GC=F")),
                        _card("oil",    yf_get("CL=F")),
                        _card("copper", yf_get("HG=F")),
                    ],
                }
            },
        }
    }

    # ── 综合面板：评分/告警/配置/历史相似度 ──
    print("  ▸ 综合面板计算中...")
    cards = _flat_cards(data)
    prev = load_snapshot()
    summary = build_summary_panel(cards, prev)
    save_snapshot(cards)
    # 把综合面板作为第一个 region 插入
    data["regions"] = {
        "summary": {"name": "📊 综合面板", "type": "summary", "data": summary},
        **data["regions"],
    }
    return data

# ═══════════════════════════════════════════════════════════
# 9. 生成 HTML
# ═══════════════════════════════════════════════════════════
def gen_html(data):
    data_json = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>宏观经济仪表盘 · {data['updated']}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#f5f7fa;--card:#ffffff;--border:#e5e7eb;--border2:#f3f4f6;
  --t1:#111827;--t2:#4b5563;--t3:#9ca3af;
  --blue:#2563eb;--blue-light:#3b82f6;
  --green:#16a34a;--green-bg:#ecfdf5;--green-border:#bbf7d0;
  --yellow:#ca8a04;--yellow-bg:#fefce8;--yellow-border:#fde68a;
  --red:#dc2626;--red-bg:#fef2f2;--red-border:#fecaca;
  --neutral-bg:#f3f4f6;
  --shadow-sm:0 1px 2px rgba(15,23,42,.04);
  --shadow:0 1px 3px rgba(15,23,42,.06),0 1px 2px rgba(15,23,42,.04);
  --shadow-md:0 4px 12px rgba(15,23,42,.06),0 2px 4px rgba(15,23,42,.04);
  --radius:10px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--t1);
      font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei','Segoe UI',sans-serif;
      min-height:100vh;-webkit-font-smoothing:antialiased}}
a{{color:var(--blue);text-decoration:none}}

/* ── header ── */
.hdr{{background:#fff;border-bottom:1px solid var(--border);padding:18px 32px;
      display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;
      box-shadow:var(--shadow-sm)}}
.hdr-title{{font-size:20px;font-weight:700;letter-spacing:-.3px;color:var(--t1)}}
.hdr-title em{{color:var(--blue);font-style:normal}}
.hdr-meta{{font-size:12px;color:var(--t2)}}
.hdr-dot{{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);
          box-shadow:0 0 6px rgba(22,163,74,.5);margin-right:6px;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}

/* ── tabs ── */
.tabs{{display:flex;gap:2px;padding:0 32px;background:#fff;
       border-bottom:1px solid var(--border);overflow-x:auto;
       box-shadow:var(--shadow-sm)}}
.tab{{padding:13px 22px;font-size:14px;color:var(--t2);cursor:pointer;
      border:none;background:none;border-bottom:2px solid transparent;
      white-space:nowrap;transition:color .15s,border-color .15s;font-weight:500}}
.tab:hover{{color:var(--t1)}}
.tab.active{{color:var(--blue);border-bottom-color:var(--blue)}}

/* ── content ── */
.wrap{{padding:28px 32px;max-width:1400px;margin:0 auto}}
.section{{margin-bottom:32px}}
.sec-title{{font-size:11px;font-weight:600;color:var(--t3);text-transform:uppercase;
            letter-spacing:1.2px;margin-bottom:14px;padding-bottom:10px;
            border-bottom:1px solid var(--border)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}}

/* ── card ── */
.card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
       padding:18px 20px;box-shadow:var(--shadow-sm);
       transition:border-color .2s,box-shadow .2s,transform .15s}}
.card:hover{{border-color:#cbd5e1;box-shadow:var(--shadow-md)}}
.card.err{{opacity:.55}}
.c-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.c-name{{font-size:12px;color:var(--t2);font-weight:500}}
.badge{{font-size:10px;font-weight:600;padding:3px 9px;border-radius:999px;border:1px solid transparent}}
.bg{{background:var(--green-bg);color:var(--green);border-color:var(--green-border)}}
.by{{background:var(--yellow-bg);color:var(--yellow);border-color:var(--yellow-border)}}
.br{{background:var(--red-bg);color:var(--red);border-color:var(--red-border)}}
.bn{{background:var(--neutral-bg);color:var(--t2);border-color:var(--border)}}

.c-val{{display:flex;align-items:baseline;gap:5px;margin-bottom:2px}}
.c-num{{font-size:28px;font-weight:700;line-height:1;letter-spacing:-.5px;color:var(--t1)}}
.c-unit{{font-size:12px;color:var(--t2)}}
.c-chg{{margin-left:auto;font-size:12px;font-weight:600}}
.up{{color:var(--green)}}.dn{{color:var(--red)}}
.c-date{{font-size:11px;color:var(--t3);margin-bottom:10px}}
.c-stale{{display:inline-block;margin-left:6px;padding:1px 6px;font-size:10px;
          color:#92400e;background:#fef3c7;border:1px solid #fcd34d;border-radius:4px}}
.chart-box{{height:80px;margin:10px 0 6px}}
.err-msg{{color:var(--red);font-size:12px;margin:14px 0}}

/* ── 当前判断 ── */
.judge{{margin-top:12px;padding:10px 12px;background:#f8fafc;border:1px solid var(--border);
        border-left:3px solid var(--blue);border-radius:6px}}
.judge-g{{border-left-color:var(--green);background:var(--green-bg)}}
.judge-y{{border-left-color:var(--yellow);background:var(--yellow-bg)}}
.judge-r{{border-left-color:var(--red);background:var(--red-bg)}}
.judge-label{{font-size:11px;font-weight:600;color:var(--t2);margin-bottom:5px;
              display:flex;align-items:center;gap:4px}}
.judge-text{{font-size:12px;color:var(--t1);line-height:1.65}}

/* ── 个人参考方向 ── */
.advice{{margin-top:10px;padding:11px 13px;background:#fffaf0;
         border:1px solid #fde68a;border-left:3px solid #f59e0b;border-radius:6px}}
.advice-title{{font-size:11px;font-weight:600;color:#92400e;margin-bottom:7px;
               display:flex;align-items:center;gap:4px}}
.advice-row{{display:flex;gap:6px;font-size:12px;line-height:1.6;color:var(--t1);
             margin-bottom:5px}}
.advice-row:last-child{{margin-bottom:0}}
.advice-label{{flex-shrink:0;font-weight:600;color:#92400e}}

/* ── 指标详解（折叠）── */
.exp-btn{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--blue);
          cursor:pointer;background:none;border:none;padding:0;margin-top:10px;font-weight:500}}
.exp-btn:hover{{color:var(--blue-light)}}
.exp-body{{display:none;margin-top:10px;padding-top:10px;
           border-top:1px solid var(--border2);font-size:12px;color:var(--t2);line-height:1.75}}
.exp-body.open{{display:block}}
.rules{{margin-top:8px;padding:7px 10px;background:var(--neutral-bg);
        border-radius:6px;font-size:11px;color:var(--t2)}}

@media(max-width:640px){{
  .hdr,.tabs,.wrap{{padding-left:16px;padding-right:16px}}
  .c-num{{font-size:24px}}
}}

/* ══ 综合面板 ══════════════════════════════════════ */
.sm-section{{background:#fff;border:1px solid var(--border);border-radius:var(--radius);
            padding:20px 22px;margin-bottom:16px;box-shadow:var(--shadow-sm)}}
.sm-h{{font-size:15px;font-weight:700;margin-bottom:14px;color:var(--t1);
       display:flex;align-items:center;gap:6px}}
.sm-sub{{font-size:12px;color:var(--t3);margin-left:8px;font-weight:400}}

/* —— 告警 —— */
.alert{{display:flex;gap:10px;padding:10px 12px;margin-bottom:8px;
        background:#fefce8;border:1px solid #fde68a;border-left:3px solid #f59e0b;
        border-radius:6px}}
.alert:last-child{{margin-bottom:0}}
.alert-r{{background:var(--red-bg);border-color:var(--red-border);border-left-color:var(--red)}}
.alert-icon{{flex-shrink:0;font-size:13px}}
.alert-body{{flex:1;font-size:13px;line-height:1.5}}
.alert-name{{font-weight:600;color:var(--t1)}}
.alert-msg{{font-size:12px;color:var(--t2);margin-top:2px}}
.alert-empty{{font-size:13px;color:var(--t3);text-align:center;padding:14px 0}}

/* —— 评分 —— */
.score-box{{display:flex;gap:24px;align-items:center;flex-wrap:wrap}}
.score-big{{flex-shrink:0;text-align:center;min-width:160px}}
.score-num{{font-size:56px;font-weight:800;letter-spacing:-2px;line-height:1}}
.score-num.green{{color:var(--green)}}
.score-num.yellow{{color:var(--yellow)}}
.score-num.red{{color:var(--red)}}
.score-label{{font-size:13px;color:var(--t2);margin-top:6px;font-weight:500}}
.comp-list{{flex:1;min-width:220px;display:flex;flex-direction:column;gap:8px}}
.comp-row{{display:flex;align-items:center;gap:10px;font-size:12px}}
.comp-label{{width:70px;flex-shrink:0;color:var(--t2);font-weight:500}}
.comp-bar{{flex:1;height:7px;background:#f1f5f9;border-radius:4px;position:relative;overflow:hidden}}
.comp-bar-mid{{position:absolute;top:-2px;bottom:-2px;left:50%;width:1px;background:var(--border)}}
.comp-bar-fill{{position:absolute;top:0;bottom:0;border-radius:4px}}
.comp-bar-fill.pos{{background:var(--green);left:50%}}
.comp-bar-fill.neg{{background:var(--red);right:50%}}
.comp-value{{width:36px;text-align:right;font-weight:600;color:var(--t1)}}

/* —— 资产配置 —— */
.alloc-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:8px}}
.alloc-card{{border:1px solid var(--border);border-radius:8px;padding:16px;background:#fafbfc}}
.alloc-title{{font-size:14px;font-weight:600;color:var(--t1);text-align:center;margin-bottom:8px}}
.alloc-chart{{height:170px;position:relative}}
.alloc-list{{display:grid;grid-template-columns:repeat(2,1fr);gap:6px 12px;margin-top:10px;font-size:12px}}
.alloc-item{{display:flex;align-items:center;gap:5px}}
.alloc-dot{{width:9px;height:9px;border-radius:2px;flex-shrink:0}}
.alloc-pct{{margin-left:auto;font-weight:600;color:var(--t1)}}
.alloc-note{{margin-top:14px;padding:10px 12px;background:#f0f9ff;border:1px solid #bae6fd;
            border-radius:6px;font-size:12px;color:#0c4a6e;line-height:1.6}}

/* —— 历史相似度 —— */
.hist-list{{display:flex;flex-direction:column;gap:10px}}
.hist-card{{border:1px solid var(--border);border-radius:8px;padding:14px 16px;background:#fafbfc}}
.hist-head{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;gap:10px}}
.hist-name{{font-size:14px;font-weight:600;color:var(--t1)}}
.hist-date{{font-size:11px;color:var(--t3);margin-top:2px}}
.hist-sim{{font-size:11px;font-weight:600;padding:3px 10px;border-radius:999px;
          background:#fef3c7;color:#92400e;flex-shrink:0;border:1px solid #fcd34d}}
.hist-sim.high{{background:#fee2e2;color:#991b1b;border-color:#fca5a5}}
.hist-row{{font-size:12px;line-height:1.65;color:var(--t2);margin-bottom:4px}}
.hist-row:last-child{{margin-bottom:0}}
.hist-label{{font-weight:600;color:#475569;margin-right:4px}}

@media(max-width:640px){{
  .alloc-grid{{grid-template-columns:1fr}}
  .score-box{{flex-direction:column;align-items:stretch}}
}}

/* ════════════════════════════════════════════════ */
/* 综合概览 Tab 样式                                 */
/* ════════════════════════════════════════════════ */
.ov-section{{background:var(--card);border:1px solid var(--border);
             border-radius:var(--radius);padding:20px 24px;margin-bottom:18px;
             box-shadow:var(--shadow-sm)}}
.ov-title{{font-size:14px;font-weight:600;color:var(--t1);margin-bottom:14px;
           display:flex;align-items:center;gap:8px}}
.ov-count{{font-size:11px;background:var(--blue);color:#fff;
           padding:2px 8px;border-radius:999px;font-weight:600}}
.ov-subtitle{{font-size:12px;color:var(--t2);margin-bottom:6px}}

/* ── 告警 ── */
.alert{{display:flex;align-items:center;gap:10px;padding:9px 12px;
        border-radius:6px;margin-bottom:6px;font-size:13px}}
.alert:last-child{{margin-bottom:0}}
.alert-high{{background:#fef2f2;border-left:3px solid var(--red)}}
.alert-med{{background:#fefce8;border-left:3px solid var(--yellow)}}
.alert-icon{{font-size:14px}}
.alert-label{{font-weight:600;color:var(--t1);min-width:80px}}
.alert-msg{{color:var(--t2);flex:1}}

/* ── 评分仪表 ── */
.gauge{{margin:16px 0}}
.gauge-track{{position:relative;height:14px;border-radius:999px;
              background:linear-gradient(90deg,#fca5a5 0%,#fbbf24 50%,#86efac 100%);
              margin-bottom:18px}}
.gauge-marker{{position:absolute;top:50%;transform:translate(-50%,-50%);
               z-index:2}}
.gauge-marker-dot{{width:18px;height:18px;border-radius:50%;
                   background:#fff;border:3px solid var(--t1);
                   box-shadow:0 2px 4px rgba(0,0,0,.15)}}
.gauge-marker-value{{position:absolute;top:24px;left:50%;
                     transform:translateX(-50%);
                     font-size:13px;font-weight:700;color:var(--t1);
                     white-space:nowrap}}
.gauge-labels{{display:flex;justify-content:space-between;
               font-size:11px;color:var(--t3);margin-top:4px}}
.regime{{display:inline-block;padding:6px 14px;border-radius:6px;
         font-size:13px;font-weight:600;margin:8px 0 14px}}
.regime-green{{background:var(--green-bg);color:var(--green);
               border:1px solid var(--green-border)}}
.regime-yellow{{background:var(--yellow-bg);color:var(--yellow);
                border:1px solid var(--yellow-border)}}
.regime-red{{background:var(--red-bg);color:var(--red);
             border:1px solid var(--red-border)}}
.contribs{{display:flex;flex-wrap:wrap;align-items:center;gap:6px;
           font-size:12px;margin-top:8px}}
.contribs-label{{color:var(--t2);font-weight:500;margin-right:4px}}
.contrib{{padding:3px 9px;border-radius:4px;font-size:11px;font-weight:500}}
.contrib-pos{{background:var(--green-bg);color:var(--green)}}
.contrib-neg{{background:var(--red-bg);color:var(--red)}}

/* ── 资产配置 ── */
.alloc-block{{margin-bottom:18px}}
.alloc-block:last-child{{margin-bottom:0}}
.alloc-name{{font-size:13px;font-weight:600;color:var(--t1);margin-bottom:8px;
             display:flex;align-items:center;gap:6px}}
.alloc-bar{{display:flex;height:36px;border-radius:6px;overflow:hidden;
            border:1px solid var(--border)}}
.alloc-seg{{display:flex;flex-direction:column;justify-content:center;
            align-items:center;color:#fff;font-size:11px;font-weight:600;
            transition:filter .2s;overflow:hidden;min-width:0}}
.alloc-seg:hover{{filter:brightness(1.1)}}
.alloc-pct{{font-size:13px;font-weight:700}}
.alloc-label{{font-size:10px;opacity:.95}}
.alloc-note{{font-size:12px;color:var(--t2);margin-top:14px;line-height:1.6;
             padding:10px 12px;background:#f9fafb;border-radius:6px;
             border-left:3px solid var(--blue)}}

/* ── 历史回测 ── */
.scenario{{padding:16px;background:#fafbfc;border:1px solid var(--border2);
           border-radius:8px;margin-bottom:12px}}
.scenario:last-child{{margin-bottom:0}}
.scenario-head{{display:flex;align-items:center;gap:10px;margin-bottom:8px;
                flex-wrap:wrap}}
.scenario-match{{padding:3px 10px;background:var(--blue);color:#fff;
                 border-radius:4px;font-size:11px;font-weight:700}}
.scenario-name{{font-size:14px;font-weight:600;color:var(--t1)}}
.scenario-period{{font-size:11px;color:var(--t3)}}
.scenario-summary{{font-size:12px;color:var(--t2);line-height:1.65;margin-bottom:10px}}
.scenario-perf{{margin-bottom:10px}}
.perf-title{{font-size:11px;font-weight:600;color:var(--t2);margin-bottom:4px}}
.perf-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:4px 12px}}
.perf-row{{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;
           border-bottom:1px dashed var(--border2)}}
.perf-row span:first-child{{color:var(--t2)}}
.perf-val{{font-weight:600;color:var(--t1)}}
.scenario-lesson{{font-size:12px;color:var(--t1);line-height:1.65;
                  padding:10px 12px;background:#fffaf0;border-radius:6px;
                  border-left:3px solid #f59e0b;margin-top:8px}}

.no-alerts{{font-size:12px;color:var(--t2);font-style:italic;text-align:center;
            padding:12px}}
</style>
</head>
<body>
<header class="hdr">
  <div>
    <div class="hdr-title">📊 <em>宏观经济</em>仪表盘</div>
    <div class="hdr-meta">FRED API · Yahoo Finance · akshare</div>
  </div>
  <div class="hdr-meta"><span class="hdr-dot"></span>更新时间: <span id="ts"></span></div>
</header>
<div class="tabs" id="tabs"></div>
<div class="wrap" id="wrap"></div>

<script>
const D = {data_json};
const charts = {{}};

const badgeClass = {{green:"bg",yellow:"by",red:"br",neutral:"bn"}};

function fmt(v, unit) {{
  if (v == null) return '--';
  const abs = Math.abs(v);
  if (abs >= 10000) return v.toLocaleString('zh-CN', {{maximumFractionDigits:0}});
  if (abs >= 1000)  return v.toLocaleString('zh-CN', {{maximumFractionDigits:1}});
  return v.toLocaleString('zh-CN', {{maximumFractionDigits:2}});
}}

function chgHtml(c) {{
  if (c == null) return '';
  const cls = c >= 0 ? 'up' : 'dn';
  const arrow = c >= 0 ? '▲' : '▼';
  return `<span class="c-chg ${{cls}}">${{arrow}}${{Math.abs(c).toFixed(2)}}%</span>`;
}}

function cardHtml(ind) {{
  if (ind.error) return `
    <div class="card err">
      <div class="c-head"><div class="c-name">${{ind.name||ind.id}}</div></div>
      <div class="err-msg">⚠ 数据获取失败</div>
    </div>`;

  const bc = badgeClass[ind.signal_color] || 'bn';
  const badge = ind.signal_text && ind.signal_text !== '—'
    ? `<span class="badge ${{bc}}">${{ind.signal_text}}</span>` : '';

  // 当前判断（背景色随信号色调）
  const judgeColorClass = {{green:"judge-g",yellow:"judge-y",red:"judge-r"}}[ind.signal_color] || '';
  const judgeHtml = ind.interpret ? `
    <div class="judge ${{judgeColorClass}}">
      <div class="judge-label">💡 当前判断</div>
      <div class="judge-text">${{ind.interpret}}</div>
    </div>` : '';

  // 个人参考方向
  const adviceHtml = (ind.impact && ind.action) ? `
    <div class="advice">
      <div class="advice-title">🧭 个人参考方向</div>
      <div class="advice-row">
        <span class="advice-label">影响：</span>
        <span>${{ind.impact}}</span>
      </div>
      <div class="advice-row">
        <span class="advice-label">应对：</span>
        <span>${{ind.action}}</span>
      </div>
    </div>` : '';

  const descHtml = ind.desc ? `
    <button class="exp-btn" onclick="tog('${{ind.id}}')">
      <span id="arr_${{ind.id}}">▶</span>&nbsp;指标详解
    </button>
    <div class="exp-body" id="exp_${{ind.id}}">
      ${{ind.desc}}
      ${{ind.rules ? `<div class="rules">${{ind.rules}}</div>` : ''}}
    </div>` : '';

  return `
  <div class="card" id="card_${{ind.id}}">
    <div class="c-head">
      <div class="c-name">${{ind.name}}</div>
      ${{badge}}
    </div>
    <div class="c-val">
      <span class="c-num">${{fmt(ind.value, ind.unit)}}</span>
      <span class="c-unit">${{ind.unit||''}}</span>
      ${{chgHtml(ind.change_pct)}}
    </div>
    <div class="c-date">最新数据：${{ind.date||'--'}}${{ind.stale ? `<span class="c-stale">⚠ ${{ind.stale_msg}}</span>` : ''}}</div>
    <div class="chart-box"><canvas id="cv_${{ind.id}}"></canvas></div>
    ${{judgeHtml}}
    ${{adviceHtml}}
    ${{descHtml}}
  </div>`;
}}

function initChart(ind) {{
  const el = document.getElementById('cv_' + ind.id);
  if (!el || !ind.trend_values || ind.trend_values.length === 0) return;
  if (charts[ind.id]) {{ charts[ind.id].destroy(); delete charts[ind.id]; }}

  const datasets = [{{
    data: ind.trend_values,
    borderColor: '#2563eb',
    backgroundColor: 'rgba(37,99,235,.08)',
    fill: true, tension: 0.4,
    pointRadius: 2, pointHoverRadius: 5,
    pointBackgroundColor: '#2563eb',
    borderWidth: 1.8,
  }}];

  if (ind.pmi_line) {{
    datasets.push({{
      data: Array(ind.trend_values.length).fill(ind.pmi_line),
      borderColor: 'rgba(220,38,38,.5)',
      borderDash: [5,4], borderWidth: 1,
      pointRadius: 0, fill: false,
    }});
  }}

  const minVal = Math.min(...ind.trend_values);
  const maxVal = Math.max(...ind.trend_values);
  const pad = Math.max((maxVal - minVal) * 0.15, 0.1);

  charts[ind.id] = new Chart(el.getContext('2d'), {{
    type: 'line',
    data: {{ labels: ind.trend_labels, datasets }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      animation: {{ duration: 400 }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: '#ffffff',
          borderColor: '#e5e7eb', borderWidth: 1,
          titleColor: '#4b5563', bodyColor: '#111827',
          padding: 8,
          callbacks: {{
            label: ctx => `${{ctx.raw}} ${{ind.unit||''}}`,
            title: ctx => ctx[0].label,
          }}
        }}
      }},
      scales: {{
        x: {{ display: false }},
        y: {{
          min: minVal - pad, max: maxVal + pad,
          display: true, border: {{ display: false }},
          grid: {{ color: 'rgba(229,231,235,.7)' }},
          ticks: {{ color:'#9ca3af', font:{{size:9}}, maxTicksLimit:4 }},
        }}
      }}
    }}
  }});
}}

function tog(id) {{
  const el = document.getElementById('exp_' + id);
  const arr = document.getElementById('arr_' + id);
  const open = el.classList.toggle('open');
  if (arr) arr.textContent = open ? '▼' : '▶';
}}

let curRegion = null;

const ALLOC_COLORS = {{"股票":"#3b82f6", "债券":"#10b981", "黄金":"#f59e0b", "现金":"#94a3b8"}};

function renderSummary(d) {{
  const wrap = document.getElementById('wrap');
  const compNames = {{inflation:"通胀环境", liquidity:"流动性", cycle:"经济景气", sentiment:"风险情绪"}};
  let html = '<div class="summary">';

  // ── 关键变动告警 ──
  html += `<div class="sm-section"><div class="sm-h">⚠ 关键变动告警 <span class="sm-sub">${{d.alerts.length}}条</span></div>`;
  if (d.alerts.length === 0) {{
    html += '<div class="alert-empty">当前无重大变动信号 ✓</div>';
  }} else {{
    for (const a of d.alerts) {{
      const cls = a.level === 'red' ? 'alert-r' : '';
      const icon = a.level === 'red' ? '🔴' : '🟡';
      html += `<div class="alert ${{cls}}">
        <div class="alert-icon">${{icon}}</div>
        <div class="alert-body">
          <span class="alert-name">${{a.indicator}}</span> = ${{a.value}}
          <div class="alert-msg">${{a.msg}}</div>
        </div></div>`;
    }}
  }}
  html += '</div>';

  // ── 综合评分 + 分项 ──
  const scClass = d.regime_color || 'yellow';
  html += `<div class="sm-section">
    <div class="sm-h">🎯 宏观环境综合评分</div>
    <div class="score-box">
      <div class="score-big">
        <div class="score-num ${{scClass}}">${{d.score >= 0 ? '+' : ''}}${{d.score}}</div>
        <div class="score-label">${{d.regime_text}}</div>
      </div>
      <div class="comp-list">`;
  for (const [k, v] of Object.entries(d.components)) {{
    const isPos = v >= 0;
    const w = Math.min(50, Math.abs(v) / 2);
    html += `<div class="comp-row">
      <div class="comp-label">${{compNames[k] || k}}</div>
      <div class="comp-bar">
        <div class="comp-bar-mid"></div>
        <div class="comp-bar-fill ${{isPos ? 'pos' : 'neg'}}" style="width:${{w}}%"></div>
      </div>
      <div class="comp-value">${{v >= 0 ? '+' : ''}}${{v}}</div>
    </div>`;
  }}
  html += '</div></div></div>';

  // ── 资产配置 ──
  html += `<div class="sm-section">
    <div class="sm-h">📊 资产配置参考 <span class="sm-sub">基于当前评分 ${{d.score}} 自动调整</span></div>
    <div class="alloc-grid">`;
  for (const [profile, alloc] of Object.entries(d.allocations)) {{
    html += `<div class="alloc-card">
      <div class="alloc-title">${{profile}}</div>
      <div class="alloc-chart"><canvas id="alloc_${{profile}}"></canvas></div>
      <div class="alloc-list">`;
    for (const [asset, pct] of Object.entries(alloc)) {{
      html += `<div class="alloc-item">
        <div class="alloc-dot" style="background:${{ALLOC_COLORS[asset]}}"></div>
        <span>${{asset}}</span>
        <span class="alloc-pct">${{pct}}%</span>
      </div>`;
    }}
    html += '</div></div>';
  }}
  html += '</div>';
  html += `<div class="alloc-note">💡 配置仅供参考。建议结合个人风险承受能力、收入稳定性和投资期限做最终决策。
            进取型适合长期（>5年）、能承受>20%回撤；稳健型适合中期（3-5年）、希望平衡风险收益。</div>`;
  html += '</div>';

  // ── 历史相似度 ──
  if (d.histories && d.histories.length > 0) {{
    html += '<div class="sm-section"><div class="sm-h">📜 历史相似度对比 <span class="sm-sub">参考历史时点的市场表现</span></div><div class="hist-list">';
    for (const h of d.histories) {{
      const simClass = h.similarity >= 65 ? 'high' : '';
      html += `<div class="hist-card">
        <div class="hist-head">
          <div>
            <div class="hist-name">${{h.name}}</div>
            <div class="hist-date">${{h.date}}</div>
          </div>
          <div class="hist-sim ${{simClass}}">相似度 ${{h.similarity}}%</div>
        </div>
        <div class="hist-row"><span class="hist-label">概况：</span>${{h.summary}}</div>
        <div class="hist-row"><span class="hist-label">市场表现：</span>${{h.perf}}</div>
        <div class="hist-row"><span class="hist-label">教训：</span>${{h.lesson}}</div>
      </div>`;
    }}
    html += '</div></div>';
  }}

  html += '</div>';
  wrap.innerHTML = html;

  // ── 渲染配置环形图 ──
  requestAnimationFrame(() => {{
    for (const [profile, alloc] of Object.entries(d.allocations)) {{
      const el = document.getElementById('alloc_' + profile);
      if (!el) continue;
      new Chart(el.getContext('2d'), {{
        type: 'doughnut',
        data: {{
          labels: Object.keys(alloc),
          datasets: [{{
            data: Object.values(alloc),
            backgroundColor: Object.keys(alloc).map(k => ALLOC_COLORS[k] || '#888'),
            borderWidth: 0,
          }}]
        }},
        options: {{
          responsive: true, maintainAspectRatio: false, cutout: '62%',
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              backgroundColor:'#fff', borderColor:'#e5e7eb', borderWidth:1,
              titleColor:'#4b5563', bodyColor:'#111827',
              callbacks: {{ label: ctx => `${{ctx.label}}  ${{ctx.raw}}%` }}
            }}
          }}
        }}
      }});
    }}
  }});
}}

function show(key) {{
  curRegion = key;
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.key === key));

  const region = D.regions[key];
  // 综合面板特殊渲染
  if (region.type === 'summary') {{
    renderSummary(region.data);
    return;
  }}
  // 常规指标卡片渲染
  let html = '';
  for (const [sec, inds] of Object.entries(region.sections)) {{
    html += `<div class="section">
      <div class="sec-title">${{sec}}</div>
      <div class="grid">${{inds.map(cardHtml).join('')}}</div>
    </div>`;
  }}
  document.getElementById('wrap').innerHTML = html;

  requestAnimationFrame(() => {{
    for (const inds of Object.values(region.sections))
      inds.forEach(ind => {{ if (!ind.error) initChart(ind); }});
  }});
}}

// init
document.getElementById('ts').textContent = D.updated;
const tabsEl = document.getElementById('tabs');
Object.entries(D.regions).forEach(([key, r], i) => {{
  const btn = document.createElement('button');
  btn.className = 'tab' + (i===0?' active':'');
  btn.dataset.key = key;
  btn.textContent = r.name;
  btn.onclick = () => show(key);
  tabsEl.appendChild(btn);
}});
show(Object.keys(D.regions)[0]);
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════
# 10. 定时任务（可选）
# ═══════════════════════════════════════════════════════════
def setup_cron():
    print("\n配置定时执行")
    print("  a) 每周一 08:00")
    print("  b) 每月1日 08:00")
    print("  c) 跳过")
    ch = input("  请选择 [a/b/c，默认c]: ").strip().lower() or "c"
    if ch not in ("a","b"): print("  已跳过"); return
    py  = sys.executable
    cmd = f"{py} {Path(__file__).resolve()} --no-open >> {SCRIPT_DIR}/dashboard.log 2>&1"
    expr = "0 8 * * 1" if ch=="a" else "0 8 1 * *"
    existing = subprocess.run(["crontab","-l"],capture_output=True,text=True).stdout
    lines = [l for l in existing.splitlines() if "econ_dashboard" not in l and l.strip()]
    subprocess.run(["crontab","-"],input="\n".join(lines+[f"{expr} {cmd}"])+"\n",text=True)
    print(f"  ✅ 已设置：{'每周一' if ch=='a' else '每月1日'} 08:00 自动执行")

# ═══════════════════════════════════════════════════════════
# 11.5 Markdown 摘要 + 微信推送（用于CI/定时任务）
# ═══════════════════════════════════════════════════════════
def gen_markdown_summary(data, public_url=None):
    """生成简洁的Markdown摘要，适合推送到微信"""
    summary = data["regions"]["summary"]["data"]
    md = []
    md.append(f"# 📊 宏观经济仪表盘  \n*{data['updated']}*\n")

    # 综合评分
    score = summary["score"]
    color = summary["regime_color"]
    score_emoji = {"green":"🟢", "yellow":"🟡", "red":"🔴"}.get(color, "⚪")
    sign = "+" if score >= 0 else ""
    md.append(f"## 🎯 综合评分: **{sign}{score}** ({summary['regime_text']}) {score_emoji}\n")

    comp_names = {"inflation":"通胀环境", "liquidity":"流动性",
                  "cycle":"经济景气", "sentiment":"风险情绪"}
    for k, v in summary["components"].items():
        emoji = "🟢" if v >= 10 else ("🟡" if v >= -10 else "🔴")
        sign = "+" if v >= 0 else ""
        md.append(f"- {comp_names.get(k,k)}: **{sign}{v}** {emoji}")
    md.append("")

    # 关键告警
    alerts = summary.get("alerts", [])
    if alerts:
        md.append(f"## ⚠ 关键告警 ({len(alerts)}条)\n")
        for a in alerts[:6]:
            icon = "🔴" if a["level"] == "red" else "🟡"
            md.append(f"- {icon} **{a['indicator']}** = {a['value']} — {a['msg']}")
        md.append("")
    else:
        md.append("## ✅ 当前无关键告警\n")

    # 资产配置
    md.append("## 💰 资产配置参考\n")
    for profile, alloc in summary["allocations"].items():
        items = " · ".join([f"{k} **{v}%**" for k, v in alloc.items()])
        md.append(f"**{profile}**: {items}  ")
    md.append("")

    # 历史相似度Top1
    histories = summary.get("histories", [])
    if histories:
        h = histories[0]
        md.append(f"## 📜 最相似历史时点\n")
        md.append(f"**{h['name']}** · 相似度 **{h['similarity']}%**  ")
        md.append(f"- 概况: {h['summary']}")
        md.append(f"- 当时表现: {h['perf']}")
        md.append(f"- 教训: {h['lesson']}")
        md.append("")

    if public_url:
        md.append("---")
        md.append(f"\n[👉 查看完整报告（含趋势图、详解、个人参考）]({public_url})")

    return "\n".join(md)


def push_to_wechat(title, content, sendkey=None):
    """通过 Server酱 (sct.ftqq.com) 推送到个人微信
       注册 https://sct.ftqq.com 获取 SendKey 后设置环境变量 SERVERCHAN_KEY"""
    sendkey = sendkey or os.environ.get("SERVERCHAN_KEY", "").strip()
    if not sendkey:
        print("⚠ 未设置 SERVERCHAN_KEY，跳过微信推送")
        return False
    try:
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        r = requests.post(url, data={"title": title, "desp": content}, timeout=15)
        result = r.json()
        if result.get("code") == 0:
            print(f"✅ 已推送到微信 (Server酱)")
            return True
        print(f"❌ 微信推送失败: {result.get('message','未知错误')}")
        return False
    except Exception as e:
        print(f"❌ 微信推送异常: {type(e).__name__}: {e}")
        return False


def push_to_wecom(title, content, webhook=None):
    """通过企业微信群机器人推送（可选备用方案，无每日限额）
       创建群机器人后获取 webhook URL，设置环境变量 WECOM_WEBHOOK"""
    webhook = webhook or os.environ.get("WECOM_WEBHOOK", "").strip()
    if not webhook: return False
    try:
        # 企业微信 markdown 不支持复杂 markdown，简化一下
        full = f"## {title}\n\n{content}"
        r = requests.post(webhook, json={
            "msgtype": "markdown",
            "markdown": {"content": full[:4000]},  # 长度限制
        }, timeout=15)
        result = r.json()
        if result.get("errcode") == 0:
            print("✅ 已推送到企业微信")
            return True
        print(f"❌ 企业微信推送失败: {result}")
        return False
    except Exception as e:
        print(f"❌ 企业微信推送异常: {e}")
        return False



if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="宏观经济仪表盘 v2.0")
    ap.add_argument("--no-open",    action="store_true", help="不自动打开浏览器")
    ap.add_argument("--setup-cron", action="store_true", help="配置定时任务（Linux/macOS）")
    ap.add_argument("--ci-mode",    action="store_true", help="CI模式：无交互、无浏览器、固定文件名")
    ap.add_argument("--output-dir", default=None,        help="HTML输出目录（默认脚本同目录）")
    ap.add_argument("--summary-md", default=None,        help="额外输出Markdown摘要到指定路径")
    ap.add_argument("--push-wechat",action="store_true", help="通过Server酱推送到微信")
    ap.add_argument("--public-url", default=None,        help="完整报告的公开URL（如 GitHub Pages 链接）")
    args = ap.parse_args()

    key  = get_fred_key()
    data = fetch_all(key)
    html = gen_html(data)

    # 输出目录
    out_dir = Path(args.output_dir) if args.output_dir else SCRIPT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # 固定文件名（用于gh-pages部署），同时保留时间戳副本
    stable = out_dir / "dashboard.html"
    stable.write_text(html, encoding="utf-8")
    if not args.ci_mode:
        ts = out_dir / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        ts.write_text(html, encoding="utf-8")
        print(f"\n✅ 报告已生成: {ts}")
    else:
        print(f"\n✅ 报告已生成: {stable}")

    # Markdown 摘要
    if args.summary_md or args.push_wechat:
        md = gen_markdown_summary(data, args.public_url)
        if args.summary_md:
            Path(args.summary_md).write_text(md, encoding="utf-8")
            print(f"✅ Markdown 摘要: {args.summary_md}")

        # 微信推送
        if args.push_wechat:
            summary = data["regions"]["summary"]["data"]
            score = summary["score"]
            # 标题加上简短状态标签
            tag = ""
            if score <= -30:   tag = " ⚠ 偏防御"
            elif score >= 30:  tag = " ✓ 偏进取"
            elif summary.get("alerts"):
                red_count = sum(1 for a in summary["alerts"] if a["level"] == "red")
                if red_count >= 2: tag = f" ⚠ {red_count}条红色告警"
            title = f"📊 宏观日报 {datetime.now().strftime('%m-%d')}{tag}"
            push_to_wechat(title, md)

    # 浏览器打开（CI模式跳过）
    if not args.ci_mode and not args.no_open:
        webbrowser.open(stable.resolve().as_uri())
        print("🌐 已在浏览器中打开")

    # 配置定时任务（CI模式跳过）
    if not args.ci_mode:
        if args.setup_cron:
            setup_cron()
        elif sys.stdin.isatty() and not IS_WINDOWS:
            ans = input("\n是否配置定时自动执行？[y/N]: ").strip().lower()
            if ans == "y": setup_cron()
