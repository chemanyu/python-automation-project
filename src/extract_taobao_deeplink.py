from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException # Import TimeoutException
import time
import re
from urllib.parse import unquote, parse_qs, urlparse, quote
import requests # 导入 requests 包

# 配置 ChromeDriver 路径 - 如果您的路径不同，请替换为您的 ChromeDriver 路径
# 对于 Linux，常见路径是 /usr/bin/chromedriver 或 /usr/local/bin/chromedriver
# 或者确保 chromedriver 在您的系统 PATH 环境变量中
CHROME_DRIVER_PATH = "/opt/homebrew/bin/chromedriver" # <-- 请确保为 Linux 更新此路径

# 添加一个参数 platform，表示选择的系统（安卓或 iOS）
def get_taobao_deeplink(short_url, driver=None, platform="ios"):
    """
    尝试从给定的淘宝短链接中提取 deeplink。
    模拟移动浏览器环境。
    如果提供了 driver 参数，则使用现有浏览器实例，否则创建新的。
    """
    internal_driver = False # 标记是否是内部创建的 driver
    if driver is None:
        internal_driver = True
        chrome_options = Options()
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

        try:
            service = Service(CHROME_DRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)  # 用 seleniumwire 的 webdriver
        except Exception as e:
            print(f"初始化 ChromeDriver 时出错 (路径: '{CHROME_DRIVER_PATH}'): {e}")
            print("尝试从系统 PATH 初始化 ChromeDriver...")
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e_path:
                print(f"从 PATH 初始化 ChromeDriver 时出错: {e_path}")
                print("请确保 Chrome/Chromium 和正确的 ChromeDriver 已安装并配置。")
                return None
    
    deeplink = None
    try:
        #print(f"导航到短链接: {short_url}") # 函数内部日志保持
        driver.get(short_url)
        
        # 使用显式等待页面加载完成
        current_url = driver.current_url
        #print(f"初始加载后当前 URL: {current_url}")

        print(f"plat: {platform }")

        # 策略 2：查找 href 以 taobao:// 或 tbopen:// 开头的 <a> 标签
        # 使用显式等待页面加载完成，并等待目标 <a> 标签出现
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//a[starts-with(@href, 'taobao://') or starts-with(@href, 'tbopen://')]") )
            )
        except TimeoutException:
            print("页面加载或 deeplink <a> 标签等待超时，继续后续处理")

        try:
            deeplink_elements = driver.find_elements(By.XPATH, "//a[starts-with(@href, 'taobao://') or starts-with(@href, 'tbopen://')]")
            if deeplink_elements:
                deeplink = deeplink_elements[0].get_attribute("href")
                #print(f"在 <a> 标签中找到的 deeplink: {deeplink}")
                return deeplink, process_deeplink(deeplink, platform)
        except Exception as e:
            print(f"注意: 查找 <a> 标签中的 deeplink 时出错（或未找到）: {e}")

        print("未能找到 Deeplink。", {current_url})

    except Exception as e:
        print(f"提取deeplink过程中发生错误: {e}") # 函数内部日志保持
        # 如果是内部创建的 driver 且发生错误，可以考虑在这里关闭，但通常外部 finally 会处理
    finally:
        if internal_driver and driver is not None: # 只关闭内部创建的 driver
            print("关闭内部创建的浏览器实例。") # 函数内部日志保持
            driver.quit()

    # 如果未找到 Deeplink，返回 None
    return None

def process_deeplink(deeplink, platform):
    """
    根据平台处理 Deeplink。
    如果是 iOS 平台，进行 URL 编码并拼接。
    如果是安卓平台，直接返回原始 Deeplink。
    """
    if platform.lower() == "ios":
        # 对提取到的 Deeplink 进行 URL 编码并拼接
        encoded_deeplink = quote(deeplink)
        final_url = f"https://ace.tb.cn/t?smburl={encoded_deeplink}"
        #print(f"最终拼接的 URL: {final_url}")
        return final_url
    else:
        #print(f"安卓平台，返回原始 Deeplink: {deeplink}")
        return deeplink
