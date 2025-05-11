import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json

# 配置 ChromeDriver 路径
CHROME_DRIVER_PATH = "/opt/homebrew/bin/chromedriver"  # 替换为您的 ChromeDriver 路径

# 初始化 WebDriver
service = Service(CHROME_DRIVER_PATH)

# 启用网络拦截功能
caps = DesiredCapabilities.CHROME
caps['goog:loggingPrefs'] = {'performance': 'ALL'}
driver = webdriver.Chrome(service=service, desired_capabilities=caps)

try:
    # 新增逻辑：通过设置 Cookies 跳过登录
    try:
        # 打开目标页面
        url = "https://item.jd.com/100050512164.html"  # 替换为您的目标链接
        driver.get(url)

        # 设置 Referer 头
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"Referer": "https://item.jd.com/"}})
        print("Referer header added successfully.")

        # 禁用自动重定向
        driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
            "headers": {
                "Referer": "https://item.jd.com/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9"
            }
        })
        print("Custom HTTP headers added successfully.")

        # 设置完整的 HTTP Headers，包括请求参数
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
            "headers": {
                "Referer": "https://item.jd.com/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Request-URL": "https://knicks.jd.com/log/server?t=rec_common_exp&v=type=rec.902029$src=rec$action=0$reqsig=fc3d3bd1ed9343fdc358b970dcf3e0f6cd40e408$enb=1$csku=100071927962,100117439608,100032473409,100002715470,100058086132,100060163817,100051839246,100106442082,100133275330,100034510105,100091052421,100112843388,100022156544,100112815920,714878$st=0,0,0,0,0,0,0,0,0,0,0,0,0,0,0$sku=100050512164$p=902029$pin=jd_778c9c130e0cf$enp=5D%2FxoWeApokRJfY5QDzROlaeHcNB96sq$uuid=Inky97OtNaB45ODZE0ZEWg%2Fy4wR8CLxh$expid=$mexpid=$gm=$rt=0,0,0,0,0,0,0,0,0,0,0,0,0,0,0$rid=3113632741248426663$ver=1$sig=3920f4a9e61be649914f06d20c88dd8f23a473e3&m=UA-J2011-1&ref=https%3A%2F%2Fpassport.jd.com%2F&random=0.7058533837662098Thu%20Apr%2017%202025%2019:39:37%20GMT+0800%20(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)",
                "Request-Method": "GET",
                "Referrer-Policy": "strict-origin-when-cross-origin"
            }
        })
        print("Custom HTTP headers with additional parameters added successfully.")

        # 添加监听器以处理重定向
        def handle_intercepted_request(request):
            if request.responseHeaders.get("Location"):
                print(f"Redirect detected to: {request.responseHeaders['Location']}")
                request.abort()
            else:
                request.continue_()

        driver.request_interceptor = handle_intercepted_request

        # 使用已经打开的窗口
        driver.switch_to.window(driver.window_handles[-1])
        print("Switched to the last opened window.")

        # 设置 Cookies 和 Headers
        cookies = [
            {"name": "__jdu", "value": "1740564634752297692458"},
            {"name": "shshshfpa", "value": "1f665855-d40d-4573-911e-1817e2ec065a-1740564636"},
            {"name": "shshshfpx", "value": "1f665855-d40d-4573-911e-1817e2ec065a-1740564636"},
            {"name": "unpl", "value": "JF8EAJ5nNSttDBgBUEsHSBpAT1gDW1QPHkRWOmQBBgkNGQRXH1USRxF7XlVdWRRKEh9vYRRUWVNJVQ4aBisSEHtdVV9eDkIQAmthNWRVUCVXSBtsGHwQBhAZbl4IexcCX2cDUVxcTFECGQcdFhNIVVJZVQtOEwpfZjVUW2h7ZAQrAysTIAAzVRNdDk4WB2hiAlZYXk9XBhMEHBoTTlldblw4SA"},
            {"name": "__jdv", "value": "76161171|direct|-|none|-|1744875006157"},
            {"name": "areaId", "value": "1"},
            {"name": "PCSYCityID", "value": "CN_110000_110100_0"},
            {"name": "pinId", "value": "D1fDWbQaWw-0rdLffkFE2bV9-x-f3wj7"},
            {"name": "pin", "value": "jd_778c9c130e0cf"},
            {"name": "unick", "value": "%E8%BD%A6%E6%BB%A1%E9%92%B0"},
            {"name": "_tp", "value": "9Jhm6mqVrxIHjsD55tZkYCd%2BG1mxD0FF%2FmF%2BPy03LGk%3D"},
            {"name": "_pst", "value": "jd_778c9c130e0cf"},
            {"name": "source", "value": "PC"},
            {"name": "platform", "value": "pc"},
            {"name": "jsavif", "value": "1"},
            {"name": "mba_muid", "value": "1740564634752297692458"},
            {"name": "ceshi3.com", "value": "000"},
            {"name": "ipLoc-djd", "value": "6-368-377-14220.2086571142"},
            {"name": "ipLocation", "value": "%u5c71%u897f"},
            {"name": "wlfstk_smdl", "value": "dc5gnnqjn9wk46simwrw6i5muw8x3krh"},
            {"name": "3AB9D23F7A4B3C9B", "value": "BZGES66BKGLDCNSLHTOXJZ7MJQDWBY6YJS3ECPTGI4IMWM6ICIG4W7GVCSKVRUQQ5IUIXAMLW3EECRVYLFESMNVRII"},
            {"name": "TrackID", "value": "1lCJcvLgdJFRn9fDSm4vhEompIa8vvR1vTZaClyhbaLSr1fvyrhDPBHIv6zwzQnJORpVljqnOGbLjE3R-DUIGHmPmQrnRxGp7pMsxhq-oUwh3YjsStN0HAGhWpqM-iTye"},
            {"name": "thor", "value": "D8407318319E86849574238400C971540FA98097A5470821058558EF89BF8567E5366038DC053FC19F6B14F6E38CEBEA4CA99D358F33EEE1E2478978E2E0FB7DC4C6D908E337016FFE540A39E4F042F97BDAF5B72CA986C71EB6F48C8969A6AFB27B8CF1409EE52263E88D4FD1F530E4E9AFDBF91746C4DC4D877D420FF543CABADAE4AA04868C000FF77466917D3E2C24040AB3CCE75B01DD014AA78586B3EC"},
            {"name": "light_key", "value": "AASBKE7rOxgWQziEhC_QY6ya61Wl0vdMkqnRA1cgiltqa7lIbpRspLNwf4xsIQiPUmN_dKue"},
            {"name": "__jda", "value": "181111935.1740564634752297692458.1740564634.1744882227.1744885296.6"},
            {"name": "__jdc", "value": "181111935"},
            {"name": "flash", "value": "3_48gxcUAeCXyBb7qcG3IyZWmFFmgsLXHqBG8ijj76g2W0r2mOW6ru6j5ELNO45M3S9xp3SGz9WT-rn4B4eR3zIyVObY2kT6CmKWuJ0NUCT5IlSOfkM4FGjlE7HPYYDcIsBGxQE28vXbSX7Xiy4qUzUXm2VKg4_jI1EbfXY8nGYf0Wr7_J10cQ2q**"},
            {"name": "token", "value": "9ba5e3feaf345d1d178fda85d7221b59,3,969383"},
            {"name": "3AB9D23F7A4B3CSS", "value": "jdd03BZGES66BKGLDCNSLHTOXJZ7MJQDWBY6YJS3ECPTGI4IMWM6ICIG4W7GVCSKVRUQQ5IUIXAMLW3EECRVYLFESMNVRIIAAAAMWIOGBRAQAAAAACV4DG3F2GMVFAQX"},
            {"name": "_gia_d", "value": "1"},
            {"name": "__jdb", "value": "181111935.20.1740564634752297692458|6.1744885296"},
            {"name": "shshshfpb", "value": "BApXSrI-EQPNAkPZFJkqrxyPXcWBZKreABgIXQRlp9xJ1MiDTo4G2"},
            {"name": "sdtoken", "value": "AAbEsBpEIOVjqTAKCQtvQu17KipEFIArwvM2XxyDVcBaUf13tW0WAlNueaFVoE46QB15bH8yGCZuRi2c9PJLrfZ60Rupn73IG-0WFktbbH6BWBeU41Fz6rbapQunE46AT8pZ8JeqSJQ"}
        ]

        driver.delete_all_cookies()
        for cookie in cookies:
            driver.add_cookie(cookie)

        print("Cookies added successfully to the current window.")

        # 刷新当前页面以应用 Cookies
        driver.get(driver.current_url)
        print("Page refreshed with applied cookies in the current window.")

        # 停留在页面，保持浏览器打开
        print("Page loaded. Keeping the browser open.")
        while True:
            time.sleep(1)  # 每秒检查一次，保持页面停留

        # 跳过登录，直接执行后续操作
        # 等待页面加载并找到“立即购买”按钮
        try:
            buy_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a#InitTradeUrl.btn-special1")))  # 替换为“立即购买”按钮的实际选择器
            buy_button.click()
            print("Clicked the 'Buy Now' button!")
        except Exception as e:
            print(f"An error occurred while trying to click the 'Buy Now' button: {e}")
            # 打印页面 HTML 以便调试
            print(driver.page_source)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # 关闭浏览器
        # driver.quit()
        print("Browser closed.")

finally:
    # 关闭浏览器
    # driver.quit()
    print("Browser closed.")

# 添加监听器以处理重定向
def handle_redirect_logs():
    logs = driver.get_log('performance')
    for entry in logs:
        log = json.loads(entry['message'])
        if log['message']['method'] == 'Network.responseReceived':
            response = log['message']['params']['response']
            if 'Location' in response['headers']:
                print(f"Redirect detected to: {response['headers']['Location']}")
                # 阻止重定向逻辑可以在这里实现

# 在主循环中调用 handle_redirect_logs
while True:
    handle_redirect_logs()
    time.sleep(1)  # 每秒检查一次日志