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
    返回格式：YYYYMMDDHHMMSS +0800
    """
    if not time_str:
        return time_str
    
    # 匹配原始时间 + 可选时区
    match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\s*([+-]\d{4}))?', time_str)
    if not match:
        return time_str

    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    tz_part = match.group(7)

    dt = datetime(year, month, day, hour, minute, second)

    # 如果有时区信息，先转换成 UTC
    if tz_part:
        tz_sign = -1 if tz_part[0] == '-' else 1
        tz_hours = int(tz_part[1:3])
        tz_minutes = int(tz_part[3:5])
        dt = dt - timedelta(hours=tz_sign*tz_hours + tz_sign*tz_minutes/60)
    
    # 再转换成北京时间
    dt += timedelta(hours=8)
    return dt.strftime('%Y%m%d%H%M%S +0800')

def process_programme_time(programme):
    """直接修改原始 programme 的 start/stop 为北京时间"""
    for attr in ['start', 'stop']:
        if programme.get(attr):
            programme.set(attr, convert_to_beijing_time(programme.get(attr)))

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
                clean_channel_name(ch)
                merged_root.append(ch)
                added_channels.add(cid)

        # 处理节目，直接修改为北京时间
        for p in root.findall('programme'):
            process_programme_time(p)
            merged_root.append(p)

        print(f"✅ 已合并 {name} 数据")

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
    print("⏰ 所有节目时间将直接修改为东8区")

    # 下载数据
    cn = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw = safe_download('https://epg.pw/xmltv/epg_TW.xml')

    merged = merge_epg_data(cn, tw)

    if merged:
        save_data(merged, 'epg_ku9.xml')
        print("\n✅ EPG 生成完成，适用于 Ku9 播放器")
        print("✅ 时区：北京时间 (UTC+8)")
        print("✅ 编码：UTF-8 with BOM")
    else:
        print("❌ 生成失败")

if __name__ == '__main__':
    main()
