import os
from flask import Flask, render_template, request, url_for, send_file # Added send_file
from werkzeug.utils import secure_filename
import concurrent.futures
import pandas as pd # Added pandas
from io import BytesIO # Added BytesIO
from flask import make_response
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# 从 src 模块导入 deeplink 提取函数
from src.extract_taobao_deeplink import get_taobao_deeplink, CHROME_DRIVER_PATH

app = Flask(__name__)

# --- 配置 ---
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB 文件大小限制

# 确保上传文件夹存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# !! 重要：针对 Windows 虚拟机部署的 ChromeDriver 路径 !!
# 1. 确保 Windows 虚拟机上已安装 Chrome 浏览器。
# 2. 下载对应 Chrome 版本的 ChromeDriver.exe。
# 3. 修改 src/extract_taobao_deeplink.py 中的 CHROME_DRIVER_PATH 指向 Windows 上的 chromedriver.exe,
#    例如: CHROME_DRIVER_PATH = "C:\\path\\to\\chromedriver.exe"
#    或者，更好的方式是确保 chromedriver.exe 所在目录已添加到 Windows 的系统 PATH 环境变量中，
#    这样 Selenium 应该能自动找到它，此时 CHROME_DRIVER_PATH 可以为空字符串或脚本中的备用逻辑会生效。

@app.route('/', methods=['GET'])
def index():
    """渲染主页面，包含输入表单。"""
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_single_link():
    """处理单个短链接的提取请求。"""
    short_url = request.form.get('short_url')
    results = []
    error = None

    platform = request.form.get('platform', 'ios').lower()  # 获取平台参数，默认为 iOS

    if not short_url:
        error = "请输入淘宝短链接。"
    else:
        print(f"Web Service: 收到单个链接提取请求: {short_url}")
        try:
            deeplink = get_taobao_deeplink(short_url, None, platform)  # 默认平台为 iOS
            if deeplink:
                results.append({'原始链接': short_url, 'Deeplink': deeplink, '状态': '成功'})
                print(f"Web Service: 提取成功: {deeplink}")
            else:
                results.append({'原始链接': short_url, 'Deeplink': '未能提取到Deeplink', '状态': '失败'})
                print(f"Web Service: 提取失败")
        except Exception as e:
            error_message = f"提取过程中发生错误: {str(e)}"
            results.append({'原始链接': short_url, 'Deeplink': error_message, '状态': '错误'})
            print(f"Web Service: 提取异常: {error_message}")
            error = error_message

    # 返回 JSON 数据
    return {
        'results': results,
        'error': error
    }


@app.route('/upload', methods=['POST'])
def upload_and_extract_file():
    """处理上传文件并提取其中所有短链接的请求, 结果以Excel文件形式下载。"""
    if 'link_file' not in request.files:
        print("Web Service: 没有选择文件")
        return "没有选择文件", 400

    file = request.files['link_file']
    platform = request.form.get('platform', 'ios').lower()  # 获取平台参数，默认为 iOS

    if file.filename == '':
        print("Web Service: 文件名为空")
        return "没有选择文件", 400

    filepath = None
    drivers = []
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"Web Service: 文件已上传: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            short_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        results_list = [None] * len(short_urls)

        if not short_urls:
            print("Web Service: 上传的文件为空或不包含有效链接")
            return "上传的文件为空或不包含有效链接", 400

        print(f"Web Service: 开始处理 {len(short_urls)} 个链接...")
        success_count = 0
        fail_count = 0

        # 1. 创建 driver 池
        driver_num = min(3, len(short_urls))
        driver_queue = queue.Queue()
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
        for _ in range(driver_num):
            try:
                service = Service(CHROME_DRIVER_PATH)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception:
                driver = webdriver.Chrome(options=chrome_options)
            drivers.append(driver)
            driver_queue.put(driver)

        def process_link(idx, url):
            driver = driver_queue.get()
            print(f"idx: {idx}")
            try:
                deeplink = get_taobao_deeplink(url, driver, platform)
                if deeplink:
                    result = {'原始链接': url, 'Deeplink': deeplink, '状态': '成功'}
                else:
                    result = {'原始链接': url, 'Deeplink': '未提取到', '状态': '失败'}
            except Exception as e:
                result = {'原始链接': url, 'Deeplink': str(e), '状态': '错误'}
            finally:
                driver_queue.put(driver)
            return (idx, result)

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(process_link, idx, url) for idx, url in enumerate(short_urls)]
            for future in as_completed(futures):
                idx, res = future.result()
                results_list[idx] = res
                if res['状态'] == '成功':
                    success_count += 1
                else:
                    fail_count += 1

        print("Web Service: 链接处理完成，开始生成Excel文件...")
        df = pd.DataFrame(results_list)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        output_filename = f"deeplink_results_{os.path.splitext(filename)[0]}.xlsx"
        print(f"Web Service: 准备发送文件: {output_filename}")
        response = make_response(send_file(
            excel_buffer,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))

        # 设置统计数据到 cookie
        print(f"Web Service: 成功提取 {success_count} 个链接，失败 {fail_count} 个链接")
        response.set_cookie('batch_stats', f'success={success_count};fail={fail_count}', max_age=60)
        response.set_cookie('download_done', 'true', max_age=60, path='/')

        return response

    except Exception as e:
        print(f"Web Service: 发生错误: {e}")
        return f"发生错误: {e}", 500

    finally:
        if drivers:
            for d in drivers:
                d.quit()
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Web Service: 已删除临时文件: {filepath}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
