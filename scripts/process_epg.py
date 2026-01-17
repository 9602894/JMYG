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

def analyze_timezone_format(data):
    """
    分析XML数据的时间格式和时区信息
    返回: (has_timezone_info, is_beijing_timezone)
    """
    root = parse_xml_bytes(data)
    if not root:
        return False, False
    
    beijing_tz_found = False
    has_tz_info = False
    sample_count = 0
    
    # 检查前10个programme元素（如果有的话）
    for programme in root.findall('programme'):
        if sample_count >= 10:
            break
            
        start_time = programme.get('start')
        if start_time:
            sample_count += 1
            
            # 检查是否有时区信息
            match = re.search(r'([+-]\d{4})$', start_time)
            if match:
                has_tz_info = True
                tz_str = match.group(1)
                # 检查是否是东8区（+0800）
                if tz_str in ['+0800', '+08:00', '+08']:
                    beijing_tz_found = True
                    print(f"  ⏰ 发现东8区时间格式: {start_time}")
                else:
                    print(f"  ⏰ 发现非东8区时间格式: {start_time}")
    
    print(f"🔍 时间格式分析结果:")
    print(f"  - 有时区信息: {has_tz_info}")
    print(f"  - 是东8区: {beijing_tz_found}")
    
    return has_tz_info, beijing_tz_found

def convert_to_beijing_time(time_str):
    """
    将 XMLTV 时间字符串转换为北京时间 (UTC+8)
    返回格式：YYYYMMDDHHMMSS +0800
    """
    if not time_str:
        return time_str

    # 匹配时间 + 可选时区
    match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\s*([+-]\d{4}))?', time_str)
    if not match:
        return time_str

    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    tz_part = match.group(7)

    dt = datetime(year, month, day, hour, minute, second)

    # 如果有时区信息，转换到UTC然后到北京时间
    if tz_part:
        tz_sign = 1 if tz_part[0] == '+' else -1
        tz_hours = int(tz_part[1:3])
        tz_minutes = int(tz_part[3:5])
        # 从原时区转换到UTC
        dt -= timedelta(hours=tz_sign*tz_hours, minutes=tz_sign*tz_minutes)
    
    # 从UTC转换到北京时间 (UTC+8)
    dt += timedelta(hours=8)

    return dt.strftime('%Y%m%d%H%M%S +0800')

def should_convert_timezone(data):
    """
    判断是否需要转换时区
    返回: True如果需要转换，False如果已经是东8区
    """
    has_tz_info, is_beijing = analyze_timezone_format(data)
    
    # 如果没有时区信息，默认需要转换（假设是UTC）
    if not has_tz_info:
        print("⚠️  XML中没有时区信息，假设需要转换到东8区")
        return True
    
    # 如果已经是东8区，不需要转换
    if is_beijing:
        print("✅ XML已经是东8区时间，跳过时区转换")
        return False
    
    print("⚠️  XML不是东8区时间，需要转换到东8区")
    return True

def process_programme_time(programme, need_conversion):
    """处理programme的时间，根据need_conversion决定是否转换"""
    if not need_conversion:
        # 不需要转换，只确保格式正确
        for attr in ['start', 'stop']:
            val = programme.get(attr)
            if val:
                # 确保有时区信息
                if not re.search(r'([+-]\d{4})$', val):
                    # 如果没有时区信息，添加+0800
                    val = val.strip() + ' +0800'
                    programme.set(attr, val)
        return
    
    # 需要转换时区
    for attr in ['start', 'stop']:
        val = programme.get(attr)
        if val:
            programme.set(attr, convert_to_beijing_time(val))

def clean_channel_name(channel):
    """移除 display-name 中的 UTC/GMT 时区信息"""
    for elem in channel.findall('display-name'):
        if elem.text:
            elem.text = re.sub(r'\s*\(UTC[+-]\d+\)', '', elem.text)
            elem.text = re.sub(r'\s*\(GMT[+-]\d+\)', '', elem.text)

def merge_epg_data(cn_bytes, tw_bytes):
    print("🔄 合并 EPG 数据...")

    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Ku9 UTF8-BOM EPG')
    merged_root.set('generator-info-name', 'JMYG')
    merged_root.set('date', datetime.now().strftime('%Y%m%d%H%M%S +0800'))

    added_channels = set()

    data_sources = [
        ('CN', cn_bytes),
        ('TW', tw_bytes)
    ]

    for name, data in data_sources:
        if not data:
            print(f"⚠️  {name} 数据为空，跳过")
            continue

        print(f"📊 处理 {name} 数据...")
        
        # 分析是否需要转换时区
        need_conversion = should_convert_timezone(data)
        
        root = parse_xml_bytes(data)
        if root is None:
            continue

        # 处理频道
        for ch in root.findall('channel'):
            cid = ch.get('id')
            if cid and cid not in added_channels:
                clean_channel_name(ch)
                merged_root.append(ch)
                added_channels.add(cid)

        # 处理节目，根据是否需要转换时区来处理时间
        programme_count = 0
        for p in root.findall('programme'):
            process_programme_time(p, need_conversion)
            merged_root.append(p)
            programme_count += 1

        print(f"✅ 已合并 {name} 数据: {programme_count} 个节目")

    xml_body = ET.tostring(
        merged_root,
        encoding='utf-8',
        xml_declaration=True
    )

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

def main():
    print("🚀 开始生成 Ku9 专用 EPG（北京时间 UTC+8）")
    print("=" * 50)

    # 下载数据
    cn = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw = safe_download('https://epg.pw/xmltv/epg_TW.xml')

    if not cn and not tw:
        print("❌ 没有可用的EPG数据")
        return

    merged = merge_epg_data(cn, tw)

    if merged:
        save_data(merged, 'epg_ku9.xml')
        print("\n" + "=" * 50)
        print("✅ EPG 生成完成")
        print("📺 适用于 Ku9 播放器")
        print("⏰ 时区：北京时间 (UTC+8)")
        print("🔤 编码：UTF-8 with BOM")
    else:
        print("❌ 生成失败")

if __name__ == '__main__':
    main()
