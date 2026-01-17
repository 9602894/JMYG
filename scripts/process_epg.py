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

def convert_utc_to_beijing_time(time_str):
    """
    将UTC时间字符串转换为北京时间 (UTC+8)
    输入格式: 20240101200000 或 20240101200000 +0000
    输出格式: 20240102040000 +0800
    """
    if not time_str:
        return time_str
    
    # 清理字符串
    time_str = time_str.strip()
    
    # 提取基本时间部分
    match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', time_str)
    if not match:
        return time_str
    
    year, month, day, hour, minute, second = map(int, match.groups())
    
    # 创建UTC时间对象
    dt_utc = datetime(year, month, day, hour, minute, second)
    
    # 转换为北京时间 (UTC+8)
    dt_beijing = dt_utc + timedelta(hours=8)
    
    # 返回北京时间，带 +0800 时区
    return dt_beijing.strftime('%Y%m%d%H%M%S +0800')

def convert_time_in_xml(root):
    """转换XML中所有的时间到北京时间"""
    if root is None:
        return None
    
    # 转换所有programme的start和stop属性
    for programme in root.findall('programme'):
        for attr in ['start', 'stop']:
            time_val = programme.get(attr)
            if time_val:
                beijing_time = convert_utc_to_beijing_time(time_val)
                programme.set(attr, beijing_time)
    
    # 清理频道显示名称中的时区信息
    for channel in root.findall('channel'):
        for display_name in channel.findall('display-name'):
            if display_name.text:
                # 移除UTC/GMT时区信息
                display_name.text = re.sub(r'\s*\(UTC[+-]\d+\)', '', display_name.text)
                display_name.text = re.sub(r'\s*\(GMT[+-]\d+\)', '', display_name.text)
                display_name.text = re.sub(r'\s*UTC[+-]\d+', '', display_name.text)
                display_name.text = re.sub(r'\s*GMT[+-]\d+', '', display_name.text)
    
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
        '20240101200000',  # 无时区，假设是UTC
        '20240101200000 +0000',  # UTC
        '20240101200000 +0800',  # 已经是北京时间
        '20240101080000 -0500',  # 美国东部时间
    ]
    
    print("🔍 测试时间转换:")
    for test in test_cases:
        result = convert_utc_to_beijing_time(test)
        print(f"  {test} → {result}")

def main():
    print("🚀 开始生成 Ku9 专用 EPG（北京时间 UTC+8）")
    print("⏰ 所有节目时间已转换为东8区北京时间")
    print("📍 您的位置：东8区（中国标准时间）")
    
    # 测试时间转换
    test_time_conversion()
    
    print("\n📡 开始下载EPG数据...")
    cn_bytes = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw_bytes = safe_download('https://epg.pw/xmltv/epg_TW.xml')
    
    # 解析并转换时区
    print("\n🔄 转换时区到北京时间...")
    
    cn_root = parse_xml_bytes(cn_bytes)
    tw_root = parse_xml_bytes(tw_bytes)
    
    if cn_root:
        cn_root = convert_time_in_xml(cn_root)
        print("✅ CN 数据时区转换完成")
    
    if tw_root:
        tw_root = convert_time_in_xml(tw_root)
        print("✅ TW 数据时区转换完成")
    
    # 合并转换后的数据
    if cn_root or tw_root:
        merged_xml = merge_epg_data(cn_root, tw_root)
        
        if merged_xml:
            save_data(merged_xml, 'epg_ku9.xml')
            print("\n✅ EPG 生成完成，适用于 Ku9 播放器")
            print("✅ 时区：北京时间 (UTC+8)")
            print("✅ 编码：UTF-8 with BOM")
            print("✅ 格式：原始 XML + 压缩 GZ")
            print("\n📊 统计信息:")
            print("  - 生成时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # 验证结果
            print("\n🔍 验证示例节目时间:")
            test_root = ET.fromstring(merged_xml[len(UTF8_BOM):])
            programmes = list(test_root.findall('programme'))[:2]
            for p in programmes:
                channel = p.get('channel', '未知')
                start = p.get('start', '未知')
                stop = p.get('stop', '未知')
                print(f"  - {channel}: {start} → {stop}")
        else:
            print("❌ 合并失败")
    else:
        print("❌ 无有效数据可合并")

if __name__ == '__main__':
    main()
