from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# 配置 ChromeDriver 路径
CHROME_DRIVER_PATH = "/opt/homebrew/bin/chromedriver"  # 替换为您的 ChromeDriver 路径

# 初始化 WebDriver
service = Service(CHROME_DRIVER_PATH)
driver = webdriver.Chrome(service=service)

try:
    # 打开目标页面
    url = "https://item.jd.com/100050512164.html"  # 替换为您的目标链接
    driver.get(url)

    # 等待页面加载
    wait = WebDriverWait(driver, 10)  # 10 是超时时间，可以根据需要调整

    # 下滑页面以确保“去登录”按钮可见并点击
    for _ in range(3):  # 下滑三次，确保按钮可见
        driver.execute_script("window.scrollBy(0, 500);")  # 每次下滑 500 像素
        time.sleep(1)  # 等待页面加载
        try:
            login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.login-btn")))  # 替换为“去登录”按钮的实际选择器
            login_button.click()
            print("Clicked the 'Go to Login' button!")
            break  # 如果成功点击，退出循环
        except:
            print("Login button not found, scrolling further...")

    # 添加异常处理和调试信息
    try:
        # 等待跳转到登录页面
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#loginname")))  # 确保页面加载完成
        print("Login page loaded successfully.")

        # 输入用户名和密码
        username_field = driver.find_element(By.CSS_SELECTOR, "input#loginname")  # 替换为用户名输入框的实际选择器
        password_field = driver.find_element(By.CSS_SELECTOR, "input#nloginpwd")  # 替换为密码输入框的实际选择器

        username_field.send_keys("15834238533")  # 输入账号
        print("Username entered.")
        password_field.send_keys("cmy15834238533")  # 输入密码
        print("Password entered.")

        # 提交登录
        submit_button = driver.find_element(By.CSS_SELECTOR, "a#loginsubmit")  # 替换为登录提交按钮的实际选择器

        # 移除禁用属性并模拟点击登录按钮
        try:
            # 使用 JavaScript 移除禁用属性
            driver.execute_script("document.querySelector('a#loginsubmit').parentElement.style.pointerEvents = 'auto';")
            driver.execute_script("document.querySelector('a#loginsubmit').parentElement.classList.remove('submit-btn-disable');")
            print("Disabled attributes removed from the login button.")

            # 模拟点击登录按钮
            login_button = driver.find_element(By.CSS_SELECTOR, "a#loginsubmit")
            driver.execute_script("arguments[0].click();", login_button)
            print("Login button clicked via JavaScript.")

        except Exception as e:
            print(f"An error occurred while handling the login button: {e}")
            raise

       
    except Exception as e:
        print(f"An error occurred: {e}")
        # 暂时不关闭浏览器以便调试
        # driver.quit()
        raise

    print("Logged in successfully!")

    # 等待页面加载并找到“立即购买”按钮
    try:
        buy_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a#InitTradeUrl.btn-special1")))  # 替换为“立即购买”按钮的实际选择器
        buy_button.click()
        print("Clicked the 'Buy Now' button!")
    except Exception as e:
        print(f"An error occurred while trying to click the 'Buy Now' button: {e}")
        # 打印页面 HTML 以便调试
        print(driver.page_source)

finally:
    # 关闭浏览器
    # driver.quit()
    print("Browser closed.")