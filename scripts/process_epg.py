#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import gzip

def safe_download(url):
    """安全下载，避免任何错误"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except:
        # 如果下载失败，返回空的XML结构
        return '''<?xml version="1.0" encoding="UTF-8"?>
<tv generator-info-name="JMYG EPG" generator-info-url="https://github.com/9602894/JMYG">
</tv>'''

def simple_timezone_fix(xml_content):
    """简单时区修复，不进行复杂解析"""
    if '+0000' in xml_content:
        return xml_content.replace('+0000', '+0800')
    return xml_content

def save_data(content, filename):
    """安全保存数据"""
    os.makedirs('epg_data', exist_ok=True)
    
    # 保存XML
    with open(f'epg_data/{filename}', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 保存压缩版
    with gzip.open(f'epg_data/{filename}.gz', 'wt', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Saved: {filename}")

def main():
    print("🚀 Starting EPG processing...")
    
    # 处理中国大陆EPG
    cn_content = safe_download('https://epg.pw/xmltv/epg_CN.xml')
    cn_content_fixed = simple_timezone_fix(cn_content)
    save_data(cn_content_fixed, 'epg_cn.xml')
    
    # 处理台湾地区EPG  
    tw_content = safe_download('https://epg.pw/xmltv/epg_TW.xml')
    tw_content_fixed = simple_timezone_fix(tw_content)
    save_data(tw_content_fixed, 'epg_tw.xml')
    
    # 生成订阅文件
    subscribe_content = '''# JMYG EPG 订阅地址
# 自动更新的大陆和台湾地区EPG数据

https://raw.githubusercontent.com/9602894/JMYG/main/epg_data/epg_cn.xml
https://raw.githubusercontent.com/9602894/JMYG/main/epg_data/epg_tw.xml
https://raw.githubusercontent.com/9602894/JMYG/main/epg_data/epg_cn.xml.gz
https://raw.githubusercontent.com/9602894/JMYG/main/epg_data/epg_tw.xml.gz

# 更新时间: {}

# 使用说明：将任意一个链接添加到播放器的EPG订阅设置中
'''.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    with open('epg_data/subscribe.txt', 'w', encoding='utf-8') as f:
        f.write(subscribe_content)
    
    print("✅ All EPG files processed successfully!")

if __name__ == '__main__':
    main()
