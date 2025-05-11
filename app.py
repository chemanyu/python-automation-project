import os
from flask import Flask, render_template, request, url_for, send_file # Added send_file
from werkzeug.utils import secure_filename
import concurrent.futures
import pandas as pd # Added pandas
from io import BytesIO # Added BytesIO

# 从 src 模块导入 deeplink 提取函数
from src.extract_taobao_deeplink import get_taobao_deeplink

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

    if not short_url:
        error = "请输入淘宝短链接。"
    else:
        print(f"Web Service: 收到单个链接提取请求: {short_url}")
        try:
            deeplink = get_taobao_deeplink(short_url)
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
    if file.filename == '':
        print("Web Service: 文件名为空")
        return "没有选择文件", 400

    results_list = []
    filepath = None

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"Web Service: 文件已上传: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            short_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        if not short_urls:
            print("Web Service: 上传的文件为空或不包含有效链接")
            return "上传的文件为空或不包含有效链接", 400

        print(f"Web Service: 开始处理 {len(short_urls)} 个链接...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(get_taobao_deeplink, url): url for url in short_urls}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    deeplink = future.result()
                    results_list.append({'原始链接': url, 'Deeplink': deeplink or '未提取到', '状态': '成功' if deeplink else '失败'})
                except Exception as e:
                    print(f"Web Service: 处理链接 {url} 时出错: {e}")
                    results_list.append({'原始链接': url, 'Deeplink': str(e), '状态': '错误'})

        print("Web Service: 链接处理完成，开始生成Excel文件...")
        df = pd.DataFrame(results_list)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        output_filename = f"deeplink_results_{os.path.splitext(filename)[0]}.xlsx"
        print(f"Web Service: 准备发送文件: {output_filename}")
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"Web Service: 发生错误: {e}")
        return f"发生错误: {e}", 500

    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Web Service: 已删除临时文件: {filepath}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
