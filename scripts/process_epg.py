#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz
import os
import gzip

def download_epg(url):
    """下载EPG数据"""
    print(f"Downloading EPG from {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text

def convert_timezone(epg_xml, target_timezone='Asia/Shanghai'):
    """将EPG数据时区转换为东八区"""
    print("Converting timezone to Asia/Shanghai...")
    
    # 创建目标时区
    tz_target = pytz.timezone(target_timezone)
    
    try:
        root = ET.fromstring(epg_xml)
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return epg_xml
    
    # 更新XML的时区信息
    root.set('date', datetime.now(tz_target).strftime('%Y%m%d%H%M%S'))
    
    # 处理每个programme元素的时间
    for programme in root.findall('.//programme'):
        for time_attr in ['start', 'stop', 'start-time', 'stop-time']:
            if time_attr in programme.attrib:
                try:
                    original_time = programme.get(time_attr)
                    # 处理不同的时间格式
                    if len(original_time) == 14:  # YYYYMMDDHHMMSS
                        dt = datetime.strptime(original_time, '%Y%m%d%H%M%S')
                        # 假设原始时间是UTC，转换为东八区
                        dt_utc = pytz.utc.localize(dt)
                        dt_target = dt_utc.astimezone(tz_target)
                        new_time = dt_target.strftime('%Y%m%d%H%M%S %z')
                        programme.set(time_attr, new_time)
                    elif ' ' in original_time:  # 已经有时区信息
                        time_str, tz_str = original_time.split(' ')
                        dt = datetime.strptime(time_str, '%Y%m%d%H%M%S')
                        if tz_str == '+0000' or tz_str == 'UTC':
                            dt_utc = pytz.utc.localize(dt)
                        else:
                            # 简单处理，假设其他时区也转换为东八区
                            dt_utc = pytz.utc.localize(dt)
                        dt_target = dt_utc.astimezone(tz_target)
                        new_time = dt_target.strftime('%Y%m%d%H%M%S +0800')
                        programme.set(time_attr, new_time)
                except Exception as e:
                    print(f"Error processing time {original_time}: {e}")
                    continue
    
    return ET.tostring(root, encoding='utf-8').decode()

def save_epg_data(content, filename):
    """保存EPG数据"""
    os.makedirs('epg_data', exist_ok=True)
    
    # 保存原始XML
    with open(f'epg_data/{filename}', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 保存压缩版本
    with gzip.open(f'epg_data/{filename}.gz', 'wt', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Saved {filename} and {filename}.gz")

def generate_subscription_index():
    """生成订阅索引文件"""
    base_url = "https://raw.githubusercontent.com/9602894/JMYG/main/epg_data"
    
    index_content = f"""# EPG Subscription Index
# Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 包含中国大陆和台湾地区的EPG数据，时区已转换为东八区

{base_url}/epg_cn.xml
{base_url}/epg_tw.xml
{base_url}/epg_cn.xml.gz
{base_url}/epg_tw.xml.gz

# 合并版本（包含所有数据）
{base_url}/epg_merged.xml
{base_url}/epg_merged.xml.gz
"""
    
    with open('epg_data/subscribe.txt', 'w', encoding='utf-8') as f:
        f.write(index_content)

def merge_epg_data(cn_content, tw_content):
    """合并两个EPG数据源"""
    try:
        root_cn = ET.fromstring(cn_content)
        root_tw = ET.fromstring(tw_content)
        
        # 创建新的根元素
        merged_root = ET.Element('tv')
        merged_root.set('source-info-name', 'Merged EPG')
        merged_root.set('source-info-url', 'https://github.com/9602894/JMYG')
        merged_root.set('generator-info-name', 'JMYG EPG Merger')
        merged_root.set('generator-info-url', 'https://github.com/9602894/JMYG')
        
        # 合并channel元素
        for channel in root_cn.findall('.//channel'):
            merged_root.append(channel)
        for channel in root_tw.findall('.//channel'):
            merged_root.append(channel)
        
        # 合并programme元素
        for programme in root_cn.findall('.//programme'):
            merged_root.append(programme)
        for programme in root_tw.findall('.//programme'):
            merged_root.append(programme)
        
        return ET.tostring(merged_root, encoding='utf-8').decode()
    except Exception as e:
        print(f"Error merging EPG data: {e}")
        return None

def main():
    epg_sources = {
        'epg_cn.xml': 'https://epg.pw/xmltv/epg_CN.xml',
        'epg_tw.xml': 'https://epg.pw/xmltv/epg_TW.xml'
    }
    
    processed_data = {}
    
    for filename, url in epg_sources.items():
        try:
            # 下载原始数据
            raw_epg = download_epg(url)
            
            # 转换时区
            converted_epg = convert_timezone(raw_epg)
            
            # 保存处理后的数据
            save_epg_data(converted_epg, filename)
            processed_data[filename] = converted_epg
            
        except Exception as e:
            print(f"Error processing {url}: {e}")
    
    # 合并数据
    if 'epg_cn.xml' in processed_data and 'epg_tw.xml' in processed_data:
        merged_epg = merge_epg_data(processed_data['epg_cn.xml'], processed_data['epg_tw.xml'])
        if merged_epg:
            save_epg_data(merged_epg, 'epg_merged.xml')
    
    # 生成订阅索引
    generate_subscription_index()
    print("EPG processing completed!")

if __name__ == '__main__':
    main()
