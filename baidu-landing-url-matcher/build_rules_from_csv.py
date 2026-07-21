# -*- coding: utf-8 -*-
"""
基于真实百度竞价关键词CSV生成可导入工具的JSON规则配置
用法：
  python build_rules_from_csv.py <关键词CSV路径> <输出JSON路径>

- 单元名唯一的用 unit_exact
- 单元名跨计划重复的用 plan_unit_exact（value格式：计划|||单元）
- 主URL占比<80%的单元视为无规律（关键词级URL），跳过并单独导出映射表
"""
import csv, io, json, re, sys, os
from collections import defaultdict, Counter
from urllib.parse import urlparse

# Windows 控制台用 GBK，强制 stdout UTF-8 输出
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

if len(sys.argv) < 3:
    print('用法: python build_rules_from_csv.py <关键词CSV路径> <输出JSON路径>')
    print('示例: python build_rules_from_csv.py "tj选哪儿20_关键词_2026-06-30.csv" "规则配置.json"')
    sys.exit(1)

CSV_PATH = sys.argv[1]
OUT_PATH = sys.argv[2]
MAPPING_PATH = os.path.splitext(OUT_PATH)[0] + '_关键词URL映射表.csv'

# === 读取CSV（自动识别 UTF-16 LE / UTF-8 / GBK 编码）===
with open(CSV_PATH, 'rb') as f:
    raw = f.read()
if raw.startswith(b'\xff\xfe'):
    content = raw[2:].decode('utf-16-le')
elif raw.startswith(b'\xef\xbb\xbf'):
    content = raw[3:].decode('utf-8')
else:
    try:
        content = raw.decode('utf-8')
    except:
        content = raw.decode('gbk')
rows = list(csv.reader(io.StringIO(content)))

data = []
# 百度标准表头是单列 tab 分隔；也兼容标准 CSV 多列
header_cells = rows[0][0].split('\t') if len(rows[0]) == 1 else rows[0]
col_plan = next((i for i, h in enumerate(header_cells) if '推广计划' in h or '计划名称' in h), 0)
col_unit = next((i for i, h in enumerate(header_cells) if '推广单元' in h or '单元名称' in h), 2)
col_kw = next((i for i, h in enumerate(header_cells) if '关键词' in h and 'ID' not in h), 3)
col_url = next((i for i, h in enumerate(header_cells) if '落地页' in h or 'URL' in h), 6)

for r in rows[1:]:
    if not r or not (r[0].strip() if r else ''):
        continue
    cells = r[0].split('\t') if len(r) == 1 else r
    if len(cells) <= max(col_plan, col_unit, col_kw, col_url):
        continue
    data.append({
        'plan': cells[col_plan].strip(),
        'unit': cells[col_unit].strip(),
        'kw': cells[col_kw].strip(),
        'url': cells[col_url].strip(),
    })

print('数据行数:', len(data))

# === 1. 提取域名 ===
domain_set = set()
for r in data:
    try:
        p = urlparse(r['url'])
        domain_set.add(p.netloc)
    except:
        pass

domains = []
domain_id_map = {}
for i, d in enumerate(sorted(domain_set)):
    did = 'dom_' + str(i + 1)
    domain_id_map[d] = did
    remark = ''
    if d.startswith('sh.'): remark = '上海站'
    elif d.startswith('bj.'): remark = '北京站'
    elif d.startswith('js.'): remark = '江苏站'
    elif d.startswith('tj.'): remark = '天津站'
    elif d.startswith('hebei.'): remark = '河北站'
    elif d == 'qgqy.xuannaer.com.cn': remark = '全国园区专题站'
    elif d == 'qgqydoo.xuannaer.com.cn': remark = '全国园区导流站'
    domains.append({
        'id': did,
        'url': 'https://' + d,
        'remark': remark,
        'isDefault': d == 'sh.xuannaer.com.cn',
        'enabled': True
    })

# === 2. 统计每个单元名出现在几个计划中 ===
unit_plans = defaultdict(set)
for r in data:
    unit_plans[r['unit']].add(r['plan'])

# === 3. 提取每个 (plan, unit) 的主URL ===
# 规范化：去掉 e_keywordid2=数字（每词不同）
unit_url_count = defaultdict(Counter)
for r in data:
    key = (r['plan'], r['unit'])
    url_clean = re.sub(r'&e_keywordid2=\d+', '', r['url'])
    unit_url_count[key][url_clean] += 1

# === 4. 解析URL ===
def parse_url_parts(url):
    p = urlparse(url)
    netloc = p.netloc
    path = p.path
    query = p.query  # 保留原始编码（百度通配符 %7Buserid%7D 等原样保留）
    return netloc, path, query

# === 5. 生成规则 ===
rules = []
rule_id_counter = 0

# 先计算每个 (plan, unit) 的主URL占比，区分有规律/无规律
unit_top_ratio = {}
for key, uc in unit_url_count.items():
    total = sum(uc.values())
    top = uc.most_common(1)[0][1]
    unit_top_ratio[key] = top / total if total > 0 else 0

# 5.1 先生成 plan_unit_exact 规则（跨计划重复的单元 + 有规律）
multi_units = {u for u, plans in unit_plans.items() if len(plans) > 1}
for (plan, unit), url_counter in sorted(unit_url_count.items()):
    if unit not in multi_units:
        continue
    if unit_top_ratio[(plan, unit)] < 0.8:
        continue  # 无规律单元跳过
    main_url = url_counter.most_common(1)[0][0]
    netloc, path, query = parse_url_parts(main_url)
    domain_id = domain_id_map.get(netloc, '')
    if not domain_id:
        continue
    rule_id_counter += 1
    kw_count = sum(url_counter.values())
    rules.append({
        'id': 'rule_pu_' + str(rule_id_counter),
        'type': 'plan_unit_exact',
        'value': plan + '|||' + unit,
        'domainId': domain_id,
        'path': path,
        'query': query,
        'remark': '[{}][{}] {}条'.format(plan, unit, kw_count),
        'enabled': True
    })

pu_count = len(rules)

# 5.2 再生成 unit_exact 规则（单元名唯一的 + 有规律）
for (plan, unit), url_counter in sorted(unit_url_count.items()):
    if unit in multi_units:
        continue
    if unit_top_ratio[(plan, unit)] < 0.8:
        continue  # 无规律单元跳过
    main_url = url_counter.most_common(1)[0][0]
    netloc, path, query = parse_url_parts(main_url)
    domain_id = domain_id_map.get(netloc, '')
    if not domain_id:
        continue
    rule_id_counter += 1
    kw_count = sum(url_counter.values())
    rules.append({
        'id': 'rule_u_' + str(rule_id_counter),
        'type': 'unit_exact',
        'value': unit,
        'domainId': domain_id,
        'path': path,
        'query': query,
        'remark': '[{}][{}] {}条'.format(plan, unit, kw_count),
        'enabled': True
    })

u_count = len(rules) - pu_count

# 统计被跳过的无规律单元
skipped = [(p, u, sum(uc.values())) for (p, u), uc in unit_url_count.items() if unit_top_ratio[(p, u)] < 0.8]
skipped_kw = sum(x[2] for x in skipped)
print('计划+单元组合规则数:', pu_count)
print('单元精确规则数:', u_count)
print('跳过的无规律单元（关键词级URL）:', len(skipped), '个, 覆盖', skipped_kw, '条关键词')

# === 6. 默认URL ===
default_url = 'https://sh.xuannaer.com.cn/yuanqu/list/?utm_source=SEM-baidu-PC&utm_medium=PC&utm_platform=ZS&utm_module=QGXN20&e_user={userid}&e_plan={planid}&e_unit={unitid}&e_keyword={keywordid}'

# === 7. 组装 ===
config = {
    'domains': domains,
    'rules': rules,
    'defaultUrl': default_url,
    'lastResults': []
}

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

pu_count = len([r for r in rules if r['type'] == 'plan_unit_exact'])
u_count = len([r for r in rules if r['type'] == 'unit_exact'])
print('\n配置已生成:', OUT_PATH)
print('  域名数:', len(domains))
print('  规则总数:', len(rules))
print('    - 计划+单元组合(plan_unit_exact):', pu_count)
print('    - 单元精确(unit_exact):', u_count)

# === 8. 全量验证 ===
print('\n=== 全量验证 ===')
# 构建索引
pu_map = {}
u_map = {}
for r in rules:
    if r['type'] == 'plan_unit_exact':
        pu_map[r['value']] = r
    elif r['type'] == 'unit_exact':
        u_map[r['value']] = r

domain_map = {d['id']: d for d in config['domains']}

def build_url(rule):
    d = domain_map.get(rule['domainId'])
    if not d: return ''
    base = d['url'].rstrip('/')
    url = base + rule['path']
    if rule['query']:
        url += ('&' if '?' in url else '?') + rule['query']
    return url

total = 0
matched = 0
rule_matched = 0  # 命中规则且URL一致
rule_missed = 0   # 命中规则但URL不一致
no_rule = 0       # 无规则覆盖
fail_examples = []
for r in data:
    total += 1
    actual = re.sub(r'&e_keywordid2=\d+', '', r['url'])
    # 先查 plan_unit_exact
    pu_key = r['plan'] + '|||' + r['unit']
    rule = pu_map.get(pu_key)
    if not rule:
        rule = u_map.get(r['unit'])
    if rule:
        built = build_url(rule)
        if built == actual:
            matched += 1
            rule_matched += 1
        else:
            rule_missed += 1
            if len(fail_examples) < 5:
                fail_examples.append((r['plan'], r['unit'], built, actual))
    else:
        no_rule += 1

print('  总数:', total)
print('  命中规则且URL一致:', rule_matched)
print('  命中规则但URL不一致:', rule_missed)
print('  无规则覆盖（无规律单元）:', no_rule)
print('  整体准确率: {:.2f}%'.format(matched * 100 / total))
print('  有规则覆盖部分准确率: {:.2f}%'.format(rule_matched * 100 / (rule_matched + rule_missed) if (rule_matched + rule_missed) > 0 else 0))
if fail_examples:
    print('\n命中规则但URL不一致样本:')
    for ex in fail_examples:
        print('  [{}][{}]'.format(ex[0], ex[1]))
        print('    生成: {}'.format(ex[2][:120] if ex[2] != 'NO_RULE' else '无规则'))
        print('    实际: {}'.format(ex[3][:120]))

# === 9. 导出无规则覆盖的关键词→URL 映射表 ===
print('\n=== 导出无规律单元关键词映射表 ===')
out_rows = []
for r in data:
    pu_key = r['plan'] + '|||' + r['unit']
    rule = pu_map.get(pu_key) or u_map.get(r['unit'])
    if not rule:
        out_rows.append([r['plan'], r['unit'], r['kw'], r['url']])

if out_rows:
    with open(MAPPING_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['推广计划', '推广单元', '关键词', '落地页URL'])
        w.writerows(out_rows)
    print('  映射表已导出:', MAPPING_PATH)
    print('  共 {} 条关键词'.format(len(out_rows)))
else:
    print('  所有关键词均已被规则覆盖，无需映射表')

print('\n完成。请将', OUT_PATH, '导入工具使用。')
