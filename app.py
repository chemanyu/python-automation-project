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
    results = [] # Use a different name than the flask.results global
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
            error = error_message # Assign error to be displayed on the page

    # For single link, always render result.html to show the result or error
    return render_template('result.html', results=results, error=error, source_type='single')


@app.route('/upload', methods=['POST'])
def upload_and_extract_file():
    """处理上传文件并提取其中所有短链接的请求, 结果以Excel文件形式下载。"""
    if 'link_file' not in request.files:
        return render_template('result.html', error="没有选择文件", source_type='file_excel_error')

    file = request.files['link_file']
    if file.filename == '':
        return render_template('result.html', error="没有选择文件", source_type='file_excel_error')

    results_list = [] # Renamed to avoid confusion
    error = None
    filepath = None

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
                print(f"Web Service: 开始并发处理文件中的 {len(short_urls)} 个链接...")
                MAX_WORKERS = 10
                print(f"Web Service: 使用 ThreadPoolExecutor (max_workers={MAX_WORKERS})")

                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures_in_order = [executor.submit(get_taobao_deeplink, url) for url in short_urls]
                    for i, future in enumerate(futures_in_order):
                        original_url = short_urls[i]
                        try:
                            deeplink = future.result()
                            if deeplink:
                                results_list.append({'原始链接': original_url, 'Deeplink': deeplink, '状态': '成功'})
                                print(f"Web Service (Thread): 提取成功: {deeplink} for {original_url}")
                            else:
                                results_list.append({'原始链接': original_url, 'Deeplink': '未能提取到Deeplink', '状态': '失败'})
                                print(f"Web Service (Thread): 提取失败 for {original_url}")
                        except Exception as e_link:
                            link_error_msg = f"提取链接 {original_url} 时线程内出错: {str(e_link)}"
                            results_list.append({'原始链接': original_url, 'Deeplink': link_error_msg, '状态': '错误'})
                            print(f"Web Service (Thread): {link_error_msg}")
                
                print(f"Web Service: 文件中所有链接处理完毕。")

                if results_list: # 只有在有结果时才创建并发送 Excel 文件
                    try:
                        df = pd.DataFrame(results_list)
                        excel_buffer = BytesIO()
                        df.to_excel(excel_buffer, index=False, engine='openpyxl')
                        excel_buffer.seek(0)
                        
                        output_filename = f"deeplink_results_{os.path.splitext(filename)[0]}.xlsx"
                        print(f"Web Service: 准备发送Excel文件: {output_filename}")
                        
                        return send_file(
                            excel_buffer,
                            as_attachment=True,
                            download_name=output_filename, 
                            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            conditional=False # Added to simplify response handling
                        )
                    except Exception as e_excel:
                        excel_error_msg = f"生成Excel文件时出错: {str(e_excel)}"
                        print(f"Web Service: {excel_error_msg}")
                        error = excel_error_msg 
                elif not error: # 如果没有结果列表，并且之前没有其他错误
                     error = "没有提取到任何结果可以生成Excel文件。"

        except Exception as e_file:
            error_message_file = f"处理文件时发生错误: {str(e_file)}"
            print(f"Web Service: {error_message_file}")
            error = error_message_file
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"Web Service: 已删除临时文件: {filepath}")
                except Exception as e_remove:
                    print(f"Web Service: 删除临时文件失败: {e_remove}")
        
        # 如果有任何错误（文件处理错误、Excel生成错误、或无结果的错误），则渲染错误页面
        if error:
            return render_template('result.html', error=error, source_type='file_excel_error')
        elif not results_list: # 再次检查，确保如果列表为空且无错误，也显示信息
             return render_template('result.html', error="没有提取到任何结果。", source_type='file_excel_error')

    # Fallback if 'file' was not in request.files or filename was empty, handled at the top
    # but as a very last resort, if something unexpected happens with the 'if file:' block
    return render_template('result.html', error="发生未知文件处理错误。", source_type='file_excel_error')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
