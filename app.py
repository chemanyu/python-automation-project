import os
from flask import Flask, render_template, request, url_for
from werkzeug.utils import secure_filename

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

    if not short_url:
        error = "请输入淘宝短链接。"
    else:
        print(f"Web Service: 收到单个链接提取请求: {short_url}")
        try:
            # 注意：get_taobao_deeplink 内部会处理 WebDriver 的创建和关闭
            deeplink = get_taobao_deeplink(short_url)
            if deeplink:
                results.append({'original': short_url, 'deeplink': deeplink, 'status': '成功'})
                print(f"Web Service: 提取成功: {deeplink}")
            else:
                results.append({'original': short_url, 'deeplink': '未能提取到Deeplink', 'status': '失败'})
                print(f"Web Service: 提取失败")
        except Exception as e:
            error_message = f"提取过程中发生错误: {str(e)}"
            results.append({'original': short_url, 'deeplink': error_message, 'status': '错误'})
            print(f"Web Service: 提取异常: {error_message}")
            error = error_message

    return render_template('result.html', results=results, error=error, source_type='single')

@app.route('/upload', methods=['POST'])
def upload_and_extract_file():
    """处理上传文件并提取其中所有短链接的请求。"""
    if 'link_file' not in request.files:
        return render_template('result.html', error="没有选择文件", source_type='file')

    file = request.files['link_file']
    if file.filename == '':
        return render_template('result.html', error="没有选择文件", source_type='file')

    results = []
    error = None
    filepath = None # 初始化 filepath

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(filepath)
            print(f"Web Service: 文件已上传: {filepath}")

            with open(filepath, 'r', encoding='utf-8') as f:
                short_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            if not short_urls:
                error = "上传的文件为空或不包含有效链接。"
            else:
                print(f"Web Service: 开始处理文件中的 {len(short_urls)} 个链接...")
                for i, short_url in enumerate(short_urls):
                    print(f"Web Service: 正在处理文件链接 {i+1}/{len(short_urls)}: {short_url}")
                    try:
                        # 注意：get_taobao_deeplink 内部会处理 WebDriver 的创建和关闭
                        deeplink = get_taobao_deeplink(short_url)
                        if deeplink:
                            results.append({'original': short_url, 'deeplink': deeplink, 'status': '成功'})
                            print(f"Web Service: 提取成功: {deeplink}")
                        else:
                            results.append({'original': short_url, 'deeplink': '未能提取到Deeplink', 'status': '失败'})
                            print(f"Web Service: 提取失败")
                    except Exception as e_link:
                        link_error_msg = f"提取链接 {short_url} 时出错: {str(e_link)}"
                        results.append({'original': short_url, 'deeplink': link_error_msg, 'status': '错误'})
                        print(f"Web Service: {link_error_msg}")
                        # error = "处理部分链接时发生错误，请查看详情。" # 可选：设置整体错误

        except Exception as e_file:
            error_message = f"处理文件时发生错误: {str(e_file)}"
            print(f"Web Service: {error_message}")
            error = error_message
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"Web Service: 已删除临时文件: {filepath}")
                except Exception as e_remove:
                    print(f"Web Service: 删除临时文件失败: {e_remove}")

    return render_template('result.html', results=results, error=error, source_type='file')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
