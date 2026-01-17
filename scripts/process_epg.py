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

def convert_to_beijing_time(time_str):
    """
    将XMLTV时间字符串转换为北京时间 (UTC+8)
    epg.pw 的数据通常是UTC时间，需要加8小时
    """
    if not time_str:
        return time_str
    
    # 提取时间和时区部分
    match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\s*([+-]\d{4}))?', time_str)
    if not match:
        return time_str
    
    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    tz_part = match.group(7)
    
    # 创建datetime对象
    dt = datetime(year, month, day, hour, minute, second)
    
    # 根据时区调整
    if tz_part:
        # 有时区信息
        tz_sign = -1 if tz_part[0] == '-' else 1
        tz_hours = int(tz_part[1:3])
        tz_minutes = int(tz_part[3:5])
        
        # 计算总偏移小时数
        tz_offset = tz_sign * (tz_hours + tz_minutes/60)
        
        # 转换为UTC
        dt_utc = dt - timedelta(hours=tz_offset)
    else:
        # 假设已经是UTC时间（epg.pw通常是UTC）
        dt_utc = dt
    
    # 转换为北京时间 (UTC+8)
    dt_beijing = dt_utc + timedelta(hours=8)
    
    # 返回北京时间，带 +0800 时区
    return dt_beijing.strftime('%Y%m%d%H%M%S +0800')

def process_programme_time(programme):
    """处理节目时间属性"""
    for attr in ['start', 'stop']:
        time_val = programme.get(attr)
        if time_val:
            beijing_time = convert_to_beijing_time(time_val)
            programme.set(attr, beijing_time)

def merge_epg_data(cn_bytes, tw_bytes):
    print("🔄 合并 EPG 数据...")

    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Ku9 UTF8-BOM EPG')
    merged_root.set('generator-info-name', 'JMYG')
    merged_root.set('date', datetime.now().strftime('%Y%m%d%H%M%S +0800'))

    added_channels = set()

    for name, data in [('CN', cn_bytes), ('TW', tw_bytes)]:
        if not data:
            continue

        root = parse_xml_bytes(data)
        if root is None:
            continue

        # 处理频道
        for ch in root.findall('channel'):
            cid = ch.get('id')
            if cid and cid not in added_channels:
                # 清理频道显示名称中的时区信息
                for elem in ch.findall('display-name'):
                    if elem.text:
                        # 移除UTC/GMT时区信息
                        elem.text = re.sub(r'\s*\(UTC[+-]\d+\)', '', elem.text)
                        elem.text = re.sub(r'\s*\(GMT[+-]\d+\)', '', elem.text)
                merged_root.append(ch)
                added_channels.add(cid)

        # 处理节目，转换时区
        for p in root.findall('programme'):
            process_programme_time(p)
            
            # 也可以处理其他时间相关元素
            for elem in p.findall('start'):
                if elem.text:
                    elem.text = convert_to_beijing_time(elem.text)
            for elem in p.findall('stop'):
                if elem.text:
                    elem.text = convert_to_beijing_time(elem.text)
                    
            merged_root.append(p)

        print(f"✅ 已合并 {name} 数据")

    xml_body = ET.tostring(
        merged_root,
        encoding='utf-8',
        xml_declaration=True
    )

    # ⚠️ 关键：加 UTF-8 BOM
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

def test_time_conversion():
    """测试时间转换函数"""
    test_cases = [
        '20240101000000',  # 无时区
        '20240101000000 +0000',  # UTC
        '20240101000000 +0800',  # 已经是北京时间
        '20240101000000 -0500',  # 美国东部时间
    ]
    
    print("🔍 测试时间转换:")
    for test in test_cases:
        result = convert_to_beijing_time(test)
        print(f"  {test} → {result}")

def main():
    print("🚀 开始生成 Ku9 专用 EPG（北京时间 UTC+8）")
    print("⏰ 所有节目时间已转换为东8区北京时间")
    
    # 测试时间转换
    test_time_conversion()
    
    print("\n📡 开始下载EPG数据...")
    cn = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw = safe_download('https://epg.pw/xmltv/epg_TW.xml')

    merged = merge_epg_data(cn, tw)

    if merged:
        save_data(merged, 'epg_ku9.xml')
        print("\n✅ EPG 生成完成，适用于 Ku9 播放器")
        print("✅ 时区：北京时间 (UTC+8)")
        print("✅ 编码：UTF-8 with BOM")
        print("✅ 格式：原始 XML + 压缩 GZ")
        print("\n📊 统计信息:")
        print("  - 生成时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    else:
        print("❌ 生成失败")

if __name__ == '__main__':
    main()
