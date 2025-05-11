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

def get_taobao_deeplink(short_url, driver=None): # 添加 driver 参数
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
            driver = webdriver.Chrome(service=service, options=chrome_options)
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
        print(f"导航到短链接: {short_url}") # 函数内部日志保持
        driver.get(short_url)
        
        # 使用显式等待替换固定的 time.sleep()
        time.sleep(10) # 原来的固定等待，现在被上面的显式等待替代

        current_url = driver.current_url
        print(f"初始加载后当前 URL: {current_url}")

        # 策略 1：检查当前 URL 是否包含 'tbopenurl' 或类似参数
        parsed_url = urlparse(current_url)
        query_params = parse_qs(parsed_url.query)
        
        if 'tbopenurl' in query_params:
            potential_deeplink = query_params['tbopenurl'][0]
            if potential_deeplink.startswith("taobao://") or potential_deeplink.startswith("tbopen://"):
                deeplink = unquote(potential_deeplink)
                print(f"在 URL 参数 'tbopenurl' 中找到的 deeplink: {deeplink}")
                # 对提取到的 Deeplink 进行 URL 编码并拼接
                encoded_deeplink = quote(deeplink)
                final_url = f"https://ace.tb.cn/t?smburl={encoded_deeplink}"
                print(f"最终拼接的 URL: {final_url}")
                return final_url 
            # 有时它是嵌套的，例如在 'params'（JSON格式）中
        
        if 'url' in query_params: # 另一个常见参数
            potential_deeplink = query_params['url'][0]
            if potential_deeplink.startswith("taobao://") or potential_deeplink.startswith("tbopen://"):
                deeplink = unquote(potential_deeplink)
                print(f"在 URL 参数 'url' 中找到的 deeplink: {deeplink}")
                # 对提取到的 Deeplink 进行 URL 编码并拼接
                encoded_deeplink = quote(deeplink)
                final_url = f"https://ace.tb.cn/t?smburl={encoded_deeplink}"
                print(f"最终拼接的 URL: {final_url}")
                return final_url 


        page_source = driver.page_source
        # print(f"页面源代码长度: {len(page_source)}") # 用于调试

        # 策略 2：查找 href 以 taobao:// 或 tbopen:// 开头的 <a> 标签
        try:
            deeplink_elements = driver.find_elements(By.XPATH, "//a[starts-with(@href, 'taobao://') or starts-with(@href, 'tbopen://')]")
            if deeplink_elements:
                deeplink = deeplink_elements[0].get_attribute("href")
                print(f"在 <a> 标签中找到的 deeplink: {deeplink}")
                # 对提取到的 Deeplink 进行 URL 编码并拼接
                encoded_deeplink = quote(deeplink)
                final_url = f"https://ace.tb.cn/t?smburl={encoded_deeplink}"
                print(f"最终拼接的 URL: {final_url}")
                return final_url 
        except Exception as e:
            print(f"注意: 查找 <a> 标签中的 deeplink 时出错（或未找到）: {e}")

        # 策略 3：查找 data-params 包含 taobao:// 或 tbopen:// 的元素
        try:
            data_param_elements = driver.find_elements(By.XPATH, "//*[contains(@data-params, 'taobao://') or contains(@data-params, 'tbopen://')]")
            if data_param_elements:
                data_params_str = data_param_elements[0].get_attribute("data-params")
                # 如果可能，尝试从类 JSON 字符串中提取
                match = re.search(r'(taobao://[^\s"\'\\}]+|tbopen://[^\s"\'\\}]+)', data_params_str)
                if match:
                    deeplink = match.group(0)
                    print(f"在 'data-params' 属性中找到的 deeplink: {deeplink}")
                    # 对提取到的 Deeplink 进行 URL 编码并拼接
                    encoded_deeplink = quote(deeplink)
                    final_url = f"https://ace.tb.cn/t?smburl={encoded_deeplink}"
                    print(f"最终拼接的 URL: {final_url}")
                    return final_url 
        except Exception as e:
            print(f"注意: 查找 'data-params' 中的 deeplink 时出错（或未找到）: {e}")
            
        # 策略 4：使用正则表达式在页面源代码中搜索各种 deeplink 模式
        # 这种方法更通用，但可能不太精确。
        # 适用于 taobao://, tbopen://, 和 URL编码版本的模式。
        patterns = [
            r'(taobao://[^\s"\'<>&]+)',  # 基本淘宝协议
            r'(tbopen://[^\s"\'<>&]+)',  # 基本 tbopen 协议
            r'["\'](https?://tbopen\.taobao\.com/tbopen/index\.html\?[^"\']+?)["\']', # 中间 tbopen URL
            r'tbopenurl=([^&"\']+)', # 内容中的 tbopenurl 参数
            r'scheme(?:%3A|=)(taobao(?:%253A%252F%252F|%3A%2F%2F|://)[^&"\']+)', # 编码的 scheme 参数
        ]

        for pattern in patterns:
            matches = re.findall(pattern, page_source, re.IGNORECASE)
            if matches:
                for match_item in matches:
                    # 如果正则表达式返回分组，match_item 可能是一个元组
                    potential_link = match_item if isinstance(match_item, str) else match_item[0]

                    potential_link = unquote(potential_link) # 始终尝试解码

                    if potential_link.lower().startswith("taobao://") or \
                       potential_link.lower().startswith("tbopen://") or \
                       "tbopen.taobao.com" in potential_link.lower():
                        deeplink = potential_link
                        print(f"使用正则表达式模式 '{pattern}' 找到的潜在 deeplink: {deeplink}")
                        # 优先处理直接的应用协议
                        if deeplink.lower().startswith("taobao://") or deeplink.lower().startswith("tbopen://"):
                            break # 退出当前循环，但不直接返回

            if deeplink: # 如果找到了任何 deeplink（即使尚未返回）
                break # 退出外层循环

        if deeplink:
            # 对提取到的 Deeplink 进行 URL 编码并拼接
            encoded_deeplink = quote(deeplink)
            final_url = f"https://ace.tb.cn/t?smburl={encoded_deeplink}"
            print(f"最终拼接的 URL: {final_url}")
            return final_url

    except Exception as e:
        print(f"提取deeplink过程中发生错误: {e}") # 函数内部日志保持
        # 如果是内部创建的 driver 且发生错误，可以考虑在这里关闭，但通常外部 finally 会处理
    finally:
        if internal_driver and driver is not None: # 只关闭内部创建的 driver
            print("关闭内部创建的浏览器实例。") # 函数内部日志保持
            driver.quit()

    # 如果未找到 Deeplink，返回 None
    return None
