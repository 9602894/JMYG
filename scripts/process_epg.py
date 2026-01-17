#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
import os
import gzip
from datetime import datetime

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
        # 处理可能的BOM
        if data.startswith(b'\xef\xbb\xbf'):
            data = data[3:]
        return ET.fromstring(data)
    except Exception as e:
        print(f"❌ XML解析失败: {e}")
        return None

def fix_timezone_in_xml(xml_content):
    """修复XML中的时区信息"""
    if xml_content:
        # 将UTC时间(+0000)转换为北京时间(+0800)，但不改变实际时间值
        # 这样Ku9播放器会按北京时间显示
        xml_str = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
        # 替换时区标识
        xml_str = xml_str.replace('+0000', '+0800')
        # 处理可能的UTC文本
        xml_str = xml_str.replace(' UTC', ' +0800')
        # 确保所有时间都有时区标识
        xml_str = xml_str.replace(' ', ' +0800 ')
        # 修复可能的重复
        xml_str = xml_str.replace('+0800 +0800', '+0800')
        return xml_str.encode('utf-8') if isinstance(xml_content, bytes) else xml_str
    return xml_content

def merge_epg_data(cn_bytes, tw_bytes):
    print("🔄 合并 EPG 数据...")

    # 先修复时区
    cn_fixed = fix_timezone_in_xml(cn_bytes) if cn_bytes else None
    tw_fixed = fix_timezone_in_xml(tw_bytes) if tw_bytes else None

    merged_root = ET.Element('tv')
    merged_root.set('source-info-name', 'JMYG Ku9 UTF8-BOM EPG')
    merged_root.set('generator-info-name', 'JMYG')
    merged_root.set('generator-info-url', 'https://github.com/9602894/JMYG')
    merged_root.set('date', datetime.now().strftime('%Y%m%d%H%M%S +0800'))

    added_channels = set()

    for name, data in [('CN', cn_fixed), ('TW', tw_fixed)]:
        if not data:
            continue

        root = parse_xml_bytes(data)
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

        print(f"✅ 已合并 {name} 数据（时区已修复为 +0800）")

    xml_body = ET.tostring(
        merged_root,
        encoding='utf-8',
        xml_declaration=True
    )

    # 确保最终的XML也有正确的时区
    xml_str = xml_body.decode('utf-8')
    xml_str = xml_str.replace('+0000', '+0800')
    
    # ⚠️ 关键：加 UTF-8 BOM
    return UTF8_BOM + xml_str.encode('utf-8')

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
    print("🚀 开始生成 Ku9 专用 EPG")
    print("⏰ 时区修复：UTC+0000 → 北京时间+0800")
    print("📝 说明：时间值保持不变，只修改时区标识")
    print("       Ku9播放器会根据时区标识显示本地时间\n")

    cn = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    tw = safe_download('https://epg.pw/xmltv/epg_TW.xml')

    merged = merge_epg_data(cn, tw)

    if merged:
        save_data(merged, 'epg_ku9.xml')
        print("\n✅ EPG 生成完成，适用于 Ku9 播放器")
        print("✅ 时区：北京时间 (UTC+8)")
        print("✅ 编码：UTF-8 with BOM")
        print("✅ 格式：原始 XML + 压缩 GZ")
        print(f"✅ 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("❌ 生成失败")

if __name__ == '__main__':
    main()
