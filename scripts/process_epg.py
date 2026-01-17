#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
import os
import gzip
from datetime import datetime, timedelta
import re

UTF8_BOM = b'\xef\xbb\xbf'

def safe_download(url):
    try:
        print(f"📥 下载: {url}")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

def parse_xml_bytes(data):
    try:
        return ET.fromstring(data)
    except Exception as e:
        print(f"❌ XML解析失败: {e}")
        return None

def shift_time_to_beijing(time_str):
    """
    将原始数据中的UTC时间向后推8小时，并标记为北京时间(+0800)
    假设原始数据是UTC时间（即时间比北京时间早8小时）
    """
    if not time_str:
        return time_str
    
    # 清理字符串
    time_str = time_str.strip()
    
    # 提取时间部分（去除任何时区信息）
    time_match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', time_str)
    if not time_match:
        return time_str
    
    # 解析为UTC时间
    year, month, day, hour, minute, second = map(int, time_match.groups())
    dt_utc = datetime(year, month, day, hour, minute, second)
    
    # 向后推8小时，得到北京时间
    dt_beijing = dt_utc + timedelta(hours=8)
    
    # 格式化：YYYYMMDDHHMMSS +0800
    return dt_beijing.strftime('%Y%m%d%H%M%S +0800')

def convert_all_times_in_xml(root):
    """
    将XML中所有的时间向后推8小时（UTC→北京时间）
    并清理频道显示名称
    """
    if root is None:
        return None
    
    print("🕐 将UTC时间转换为北京时间 (UTC+8)...")
    
    # 转换所有programme的start和stop属性
    programme_count = 0
    for programme in root.findall('programme'):
        programme_count += 1
        
        for attr in ['start', 'stop']:
            time_str = programme.get(attr)
            if time_str:
                beijing_time = shift_time_to_beijing(time_str)
                programme.set(attr, beijing_time)
    
    print(f"✅ 已转换 {programme_count} 个节目的时间")
    
    # 清理频道显示名称
    channel_count = 0
    for channel in root.findall('channel'):
        channel_count += 1
        for display_name in channel.findall('display-name'):
            if display_name.text:
                # 移除所有时区信息
                original = display_name.text
                cleaned = re.sub(r'\s*\(UTC[+-]\d+\)', '', original)
                cleaned = re.sub(r'\s*\(GMT[+-]\d+\)', '', cleaned)
                cleaned = re.sub(r'\s*UTC[+-]\d+', '', cleaned)
                cleaned = re.sub(r'\s*GMT[+-]\d+', '', cleaned)
                display_name.text = cleaned.strip()
    
    print(f"✅ 已清理 {channel_count} 个频道的显示名称")
    
    return root

def merge_epg_data(cn_root, tw_root):
    print("🔄 合并 EPG 数据...")

    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Ku9 UTF8-BOM EPG')
    merged_root.set('generator-info-name', 'JMYG')
    merged_root.set('date', datetime.now().strftime('%Y%m%d%H%M%S +0800'))

    added_channels = set()

    for name, root in [('CN', cn_root), ('TW', tw_root)]:
        if root is None:
            continue

        # 处理频道
        for ch in root.findall('channel'):
            cid = ch.get('id')
            if cid and cid not in added_channels:
                merged_root.append(ch)
                added_channels.add(cid)

        # 处理节目
        for p in root.findall('programme'):
            merged_root.append(p)

        print(f"✅ 已合并 {name} 数据")
        
    print(f"📊 合并后共有 {len(added_channels)} 个频道")

    xml_body = ET.tostring(
        merged_root,
        encoding='utf-8',
        xml_declaration=True
    )

    # 添加UTF-8 BOM
    return UTF8_BOM + xml_body

def save_data(xml_bytes, filename):
    os.makedirs('epg_data', exist_ok=True)

    xml_path = f'epg_data/{filename}'
    gz_path = f'{xml_path}.gz'

    with open(xml_path, 'wb') as f:
        f.write(xml_bytes)

    with gzip.open(gz_path, 'wb') as f:
        f.write(xml_bytes)

    print(f"💾 已保存: {xml_path}")
    print(f"💾 已保存: {gz_path}")

def test_time_shifting():
    """
    测试时间转换：UTC时间向后推8小时
    原始epg.pw数据通常是UTC时间，需要显示为北京时间
    """
    print("🔍 测试时间转换 (UTC → 北京时间):")
    
    # 示例：UTC时间 12:00 → 北京时间 20:00
    test_cases = [
        ('20240101120000', '20240101200000 +0800'),  # UTC 12:00 → 北京 20:00
        ('20240101000000', '20240101080000 +0800'),  # UTC 00:00 → 北京 08:00
        ('20240101230000', '20240102070000 +0800'),  # UTC 23:00 → 北京 07:00 (+1天)
        ('20240101120000 +0000', '20240101200000 +0800'),  # 带时区标记的UTC
        ('20240101120000 UTC', '20240101200000 +0800'),    # 带UTC标记
    ]
    
    for input_time, expected_output in test_cases:
        output = shift_time_to_beijing(input_time)
        status = "✓" if output == expected_output else "✗"
        print(f"  {status} UTC: {input_time}")
        print(f"      → 北京: {output}")
        if output != expected_output:
            print(f"     预期: {expected_output}")

def show_sample_times(root, source_name):
    """
    显示一些样本时间，确认转换是否正确
    """
    if root is None:
        return
    
    print(f"\n🔍 {source_name} 数据样本:")
    
    # 取前3个节目的时间
    programmes = list(root.findall('programme'))[:3]
    
    if not programmes:
        print("  没有节目数据")
        return
    
    for i, prog in enumerate(programmes):
        channel = prog.get('channel', '未知')
        start = prog.get('start', '未知')
        stop = prog.get('stop', '未知')
        
        # 解析时间显示
        if start and ' ' in start:
            time_part = start.split()[0]
            if len(time_part) >= 12:
                hour_min = f"{time_part[8:10]}:{time_part[10:12]}"
                print(f"  {i+1}. {channel}: {hour_min} (+0800)")
        else:
            print(f"  {i+1}. {channel}: {start}")

def main():
    print("🚀 开始生成 Ku9 专用 EPG")
    print("🕐 时间处理: UTC时间 → 北京时间 (+8小时)")
    print("📍 您的时区: 东8区 (中国标准时间)")
    
    # 测试时间转换逻辑
    test_time_shifting()
    
    print("\n📡 开始下载EPG数据...")
    cn_bytes = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw_bytes = safe_download('https://epg.pw/xmltv/epg_TW.xml')
    
    if not cn_bytes and not tw_bytes:
        print("❌ 没有下载到任何数据")
        return
    
    # 解析XML
    print("\n🔄 解析XML数据...")
    cn_root = parse_xml_bytes(cn_bytes) if cn_bytes else None
    tw_root = parse_xml_bytes(tw_bytes) if tw_bytes else None
    
    # 转换时区
    if cn_root:
        print("\n🔄 处理CN数据时区...")
        cn_root = convert_all_times_in_xml(cn_root)
        show_sample_times(cn_root, "CN")
    
    if tw_root:
        print("\n🔄 处理TW数据时区...")
        tw_root = convert_all_times_in_xml(tw_root)
        show_sample_times(tw_root, "TW")
    
    # 合并数据
    print("\n🔄 合并所有数据...")
    if cn_root or tw_root:
        merged_xml = merge_epg_data(cn_root, tw_root)
        
        if merged_xml:
            # 最终验证
            print("\n🔍 最终验证:")
            merged_root = ET.fromstring(merged_xml[len(UTF8_BOM):])
            
            # 统计
            channels = list(merged_root.findall('channel'))
            programmes = list(merged_root.findall('programme'))
            
            print(f"  频道总数: {len(channels)}")
            print(f"  节目总数: {len(programmes)}")
            
            # 检查时间格式
            if programmes:
                sample = programmes[0]
                start_time = sample.get('start', '')
                if '+0800' in start_time:
                    print("  ✓ 所有时间已标记为北京时间 (+0800)")
                    
                    # 显示具体时间对比示例
                    print("\n🕐 时间转换示例:")
                    for i, prog in enumerate(programmes[:2]):
                        channel = prog.get('channel', '未知')
                        start = prog.get('start', '未知')
                        if start and ' ' in start:
                            time_part = start.split()[0]
                            if len(time_part) >= 12:
                                utc_hour = (int(time_part[8:10]) - 8) % 24
                                beijing_hour = time_part[8:10]
                                print(f"  {channel}: UTC {utc_hour:02d}:{time_part[10:12]} → 北京 {beijing_hour}:{time_part[10:12]}")
                else:
                    print(f"  ✗ 时间未正确转换: {start_time}")
            
            # 保存文件
            save_data(merged_xml, 'epg_ku9.xml')
            
            print("\n✅ EPG 生成完成!")
            print("✅ 时区: 北京时间 (UTC+8)")
            print("✅ 编码: UTF-8 with BOM")
            print("✅ 格式: XML + GZ")
            print(f"\n📁 文件位置: epg_data/epg_ku9.xml")
            print(f"📁 压缩文件: epg_data/epg_ku9.xml.gz")
        else:
            print("❌ 合并失败")
    else:
        print("❌ 无有效数据可合并")

if __name__ == '__main__':
    main()
