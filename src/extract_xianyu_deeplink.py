from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import time
import re
import json
from urllib.parse import urlparse

# 配置 ChromeDriver 路径
CHROME_DRIVER_PATH = "/opt/homebrew/bin/chromedriver"

def get_xianyu_deeplink(short_url, driver=None, platform="android"):
    """
    从闲鱼短链接中提取 deeplink
    platform: "android" 或 "ios"
    """
    internal_driver = False
    if driver is None:
        internal_driver = True
        chrome_options = Options()
        
        # 根据平台选择不同的 User-Agent
        if platform.lower() == "android":
            mobile_emulation = {
                "deviceMetrics": {"width": 412, "height": 915, "pixelRatio": 3.5},
                "userAgent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36"
            }
        else:
            mobile_emulation = {
                "deviceMetrics": {"width": 375, "height": 812, "pixelRatio": 3.0},
                "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1"
            }
        
        chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument('log-level=3')

        # Selenium Wire 配置
        seleniumwire_options = {
            'disable_capture': False,
            'exclude_hosts': [],
        }

        try:
            service = Service(CHROME_DRIVER_PATH)
            driver = webdriver.Chrome(
                service=service, 
                options=chrome_options,
                seleniumwire_options=seleniumwire_options
            )
        except Exception as e:
            print(f"初始化 ChromeDriver 时出错: {e}")
            try:
                driver = webdriver.Chrome(
                    options=chrome_options,
                    seleniumwire_options=seleniumwire_options
                )
            except Exception as e_path:
                print(f"从 PATH 初始化 ChromeDriver 时出错: {e_path}")
                return None

    try:
        print(f"正在访问闲鱼链接: {short_url}, 平台: {platform}")
        
        # Android 平台：使用 CDP 监听所有导航尝试
        fleamarket_url_found = None
        if platform.lower() == "android":
            # 启用 CDP 的 Page 域来监听导航
            driver.execute_cdp_cmd('Page.enable', {})
            
            # 访问页面前，我们需要在页面加载时立即执行脚本
            print("✅ 已启用 CDP Page 监听")
        
        driver.get(short_url)
        
        # 使用显式等待页面加载完成
        print("等待页面加载...")
        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except TimeoutException:
            print("页面加载等待超时，继续后续处理")
        
        current_url = driver.current_url
        print(f"当前 URL: {current_url}")
        
        # Android 平台：多种方法捕获 fleamarket 链接
        if platform.lower() == "android":
            print("=" * 80)
            print("Android 平台，开始搜索 fleamarket 链接...")
            print("=" * 80)
            
            # 方法1: 从浏览器控制台日志中查找（可能有 console.log 输出的链接）
            try:
                logs = driver.get_log('browser')
                print(f"\n[方法1] 检查浏览器控制台日志 ({len(logs)} 条)...")
                for log in logs:
                    message = log.get('message', '')
                    if 'fleamarket://' in message:
                        # 提取 fleamarket URL
                        match = re.search(r'fleamarket://[^\s"\'<>]+', message)
                        if match:
                            fleamarket_url_found = match.group(0)
                            print(f"✅ 从控制台日志找到: {fleamarket_url_found}")
                            return fleamarket_url_found
            except Exception as e:
                print(f"读取控制台日志出错: {e}")
        
        # iOS 平台：返回 pages.goofish.com 链接
        if platform.lower() == "ios":
            if 'pages.goofish.com' in current_url:
                print(f"iOS 平台，返回: {current_url}")
                return current_url
            for request in driver.requests:
                if 'pages.goofish.com' in request.url:
                    print(f"从网络请求找到: {request.url}")
                    return request.url
            
            return None

    except Exception as e:
        print(f"提取过程中发生错误: {e}")
        return None
    finally:
        if internal_driver and driver is not None:
            driver.quit()

    return None
