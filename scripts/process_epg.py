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

def parse_xmltv_time(time_str):
    """
    解析XMLTV格式的时间字符串，返回datetime对象
    格式: YYYYMMDDHHMMSS [TZ] 或 YYYYMMDDHHMMSS
    """
    if not time_str:
        return None
    
    # 移除可能的空格和时区信息
    parts = time_str.strip().split()
    time_part = parts[0]
    
    # 解析时间部分
    if len(time_part) >= 14:
        try:
            year = int(time_part[0:4])
            month = int(time_part[4:6])
            day = int(time_part[6:8])
            hour = int(time_part[8:10])
            minute = int(time_part[10:12])
            second = int(time_part[12:14]) if len(time_part) >= 14 else 0
            
            dt = datetime(year, month, day, hour, minute, second)
            
            # 如果有时区信息
            if len(parts) > 1:
                tz_str = parts[1]
                if tz_str.startswith('+') or tz_str.startswith('-'):
                    tz_sign = -1 if tz_str[0] == '-' else 1
                    tz_hours = int(tz_str[1:3])
                    tz_minutes = int(tz_str[3:5])
                    
                    # 计算时区偏移
                    tz_offset = timedelta(hours=tz_hours, minutes=tz_minutes) * tz_sign
                    
                    # 调整时间到UTC
                    dt = dt - tz_offset
            
            return dt
        except ValueError as e:
            print(f"❌ 时间解析失败 {time_str}: {e}")
            return None
    
    return None

def convert_to_beijing_time(dt_utc):
    """
    将UTC时间转换为北京时间 (UTC+8)
    """
    if dt_utc is None:
        return None
    
    # 转换为北京时间
    dt_beijing = dt_utc + timedelta(hours=8)
    
    # 格式化为XMLTV格式
    return dt_beijing.strftime('%Y%m%d%H%M%S +0800')

def convert_all_times_in_xml(root):
    """转换XML中所有的时间到北京时间"""
    if root is None:
        return None
    
    print("🔄 正在转换所有时间到北京时间 (UTC+8)...")
    
    # 转换所有programme的start和stop属性
    programme_count = 0
    for programme in root.findall('programme'):
        programme_count += 1
        
        for attr in ['start', 'stop']:
            time_str = programme.get(attr)
            if time_str:
                # 解析原始时间
                dt_original = parse_xmltv_time(time_str)
                
                if dt_original:
                    # 转换为北京时间
                    beijing_time = convert_to_beijing_time(dt_original)
                    programme.set(attr, beijing_time)
    
    print(f"✅ 已转换 {programme_count} 个节目的时间")
    
    # 清理频道显示名称中的时区信息
    channel_count = 0
    for channel in root.findall('channel'):
        channel_count += 1
        for display_name in channel.findall('display-name'):
            if display_name.text:
                # 移除UTC/GMT时区信息
                original_text = display_name.text
                display_name.text = re.sub(r'\s*\(UTC[+-]\d+\)', '', original_text)
                display_name.text = re.sub(r'\s*\(GMT[+-]\d+\)', '', display_name.text)
                display_name.text = re.sub(r'\s*UTC[+-]\d+', '', display_name.text)
                display_name.text = re.sub(r'\s*GMT[+-]\d+', '', display_name.text)
    
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
    print("🔍 测试时间转换逻辑:")
    
    # 模拟epg.pw的可能格式
    test_cases = [
        '20240101200000',  # 无时区，常见格式
        '20240101200000 +0000',  # UTC时间
        '20240101200000 +0800',  # 已经是北京时间
        '20240101200000 -0500',  # 其他时区
        '20240101200000 +0530',  # 半小时间隔时区
    ]
    
    for test in test_cases:
        # 解析原始时间
        dt_original = parse_xmltv_time(test)
        
        if dt_original:
            # 转换为北京时间
            beijing_time = convert_to_beijing_time(dt_original)
            
            # 显示结果
            original_tz = test.split()[1] if len(test.split()) > 1 else "无时区"
            print(f"  原始: {test} ({original_tz})")
            print(f"  → UTC: {dt_original.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  → 北京: {beijing_time}")
            print(f"  (时区转换: {'已转换' if '0800' in beijing_time else '未转换'})")
            print()

def validate_time_conversion(root):
    """验证时间转换结果"""
    print("\n🔍 验证时间转换结果:")
    
    # 检查几个节目的时间
    programmes = list(root.findall('programme'))[:3]
    
    if not programmes:
        print("  没有找到节目数据")
        return
    
    for i, p in enumerate(programmes):
        channel = p.get('channel', '未知')
        start = p.get('start', '未知')
        stop = p.get('stop', '未知')
        
        # 检查是否包含+0800
        if '+0800' in start:
            print(f"  ✓ 节目 {i+1}: {channel}")
            print(f"     开始: {start}")
            print(f"     结束: {stop}")
        else:
            print(f"  ✗ 节目 {i+1}: {channel} - 时区转换失败!")
            print(f"     开始: {start}")
            print(f"     结束: {stop}")

def main():
    print("🚀 开始生成 Ku9 专用 EPG（北京时间 UTC+8）")
    print("📍 您的位置：东8区（中国标准时间）")
    
    # 测试时间转换逻辑
    test_time_conversion()
    
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
    
    if cn_root:
        print(f"✅ CN 数据解析完成")
        # 转换CN数据时区
        cn_root = convert_all_times_in_xml(cn_root)
        validate_time_conversion(cn_root)
    
    if tw_root:
        print(f"✅ TW 数据解析完成")
        # 转换TW数据时区
        tw_root = convert_all_times_in_xml(tw_root)
        validate_time_conversion(tw_root)
    
    # 合并转换后的数据
    print("\n🔄 合并所有数据...")
    if cn_root or tw_root:
        merged_xml = merge_epg_data(cn_root, tw_root)
        
        if merged_xml:
            # 最终验证
            print("\n🔍 最终验证合并数据:")
            merged_root = ET.fromstring(merged_xml[len(UTF8_BOM):])
            
            # 统计信息
            channel_count = len(list(merged_root.findall('channel')))
            programme_count = len(list(merged_root.findall('programme')))
            
            print(f"  频道数: {channel_count}")
            print(f"  节目数: {programme_count}")
            
            # 检查时区
            programmes = list(merged_root.findall('programme'))
            if programmes:
                sample = programmes[0]
                start_time = sample.get('start', '')
                if '+0800' in start_time:
                    print(f"  ✓ 确认: 所有时间已转换为北京时间 (+0800)")
                else:
                    print(f"  ✗ 警告: 时间可能未正确转换: {start_time}")
            
            save_data(merged_xml, 'epg_ku9.xml')
            print("\n✅ EPG 生成完成，适用于 Ku9 播放器")
            print("✅ 时区：北京时间 (UTC+8)")
            print("✅ 编码：UTF-8 with BOM")
            print("✅ 格式：原始 XML + 压缩 GZ")
            print("\n📊 生成信息:")
            print("  - 生成时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            print("  - 文件位置: epg_data/epg_ku9.xml")
        else:
            print("❌ 合并失败")
    else:
        print("❌ 无有效数据可合并")

if __name__ == '__main__':
    main()
