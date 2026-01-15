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
from urllib.parse import unquote, parse_qs, urlparse, quote

# 从 src 模块导入 deeplink 提取函数
from src.extract_taobao_deeplink import get_taobao_deeplink, CHROME_DRIVER_PATH
from src.extract_xianyu_deeplink import get_xianyu_deeplink
from src.taobao_api import TaobaoAPI
from src.taobao_activity_report import TaobaoActivityReportAPI

# 淘宝客 API 配置
TAOBAO_APP_KEY = '35238422'
TAOBAO_APP_SECRET = '3e2c5266e7a3689ac909659a203ce301'  # 请替换为你的 AppSecret
ACTIVITY_MATERIAL_ID = '20150318020010092'  # 活动素材ID
DEFAULT_EVENT_ID = '3924553'  # CPA活动ID

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
    """渲染统一首页，包含淘宝和闲鱼两个标签页。"""
    return render_template('home.html')

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
            deeplink, h5Dp = get_taobao_deeplink(short_url, None, platform)  # 默认平台为 iOS
            if deeplink:
                results.append({'原始链接': short_url, 'Deeplink': deeplink, 'h5Dp': h5Dp, '状态': '成功'})
                print(f"Web Service: 提取成功: {results}")
            else:
                results.append({'原始链接': short_url, 'Deeplink': '未能提取到Deeplink', 'h5Dp': '无Deeplink', '状态': '失败'})
                print(f"Web Service: 提取失败")
        except Exception as e:
            error_message = f"提取过程中发生错误: {str(e)}"
            results.append({'原始链接': short_url, 'Deeplink': error_message, '状态': '错误'})
            print(f"Web Service: 提取异常: {error_message}")
            error = error_message

    # 返回 JSON 数据，包含 deeplink 和 h5Dp
    if results and results[0].get('Deeplink') and results[0]['Deeplink'] != '未能提取到Deeplink':
        return {
            'deeplink': results[0]['Deeplink'],
            'h5Dp': results[0].get('h5Dp', ''),
            'error': None
        }
    else:
        return {
            'deeplink': None,
            'h5Dp': None,
            'error': error or '提取失败，请检查链接是否正确'
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
                deeplink, h5Dp = get_taobao_deeplink(url, driver, platform)
                if deeplink:
                    result = {'原始链接': url, 'Deeplink': deeplink, 'h5Dp': h5Dp, '状态': '成功'}
                else:
                    result = {'原始链接': url, 'Deeplink': '未提取到', 'h5Dp': '无Deeplink', '状态': '失败'}
            except Exception as e:
                result = {'原始链接': url, 'Deeplink': str(e), '状态': '错误'}
            finally:
                driver_queue.put(driver)
            return (idx, result)

        with ThreadPoolExecutor(max_workers=2) as executor:
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

# ==================== 闲鱼转链功能 ====================


@app.route('/xianyu/extract', methods=['POST'])
def extract_xianyu_link():
    """处理单个闲鱼短链接的提取请求"""
    short_url = request.form.get('short_url')
    platform = request.form.get('platform', 'android').lower()

    if not short_url:
        return {
            'deeplink': None,
            'error': "请输入闲鱼短链接。"
        }
    
    print(f"Web Service: 收到闲鱼链接提取请求: {short_url}, 平台: {platform}")
    try:
        deeplink = get_xianyu_deeplink(short_url, None, platform)
        if deeplink:
            print(f"Web Service: 闲鱼转链成功")
            return {
                'deeplink': deeplink,
                'error': None
            }
        else:
            print(f"Web Service: 闲鱼转链失败")
            return {
                'deeplink': None,
                'error': "未能提取到Deeplink"
            }
    except Exception as e:
        error_message = f"提取过程中发生错误: {str(e)}"
        print(f"Web Service: 闲鱼转链异常: {error_message}")
        return {
            'deeplink': None,
            'error': error_message
        }

# 闲鱼批量转链
@app.route('/xianyu/upload', methods=['POST'])
def upload_and_extract_xianyu_file():
    """处理上传文件并批量提取闲鱼短链接，结果以Excel文件下载。"""
    if 'link_file' not in request.files:
        print("Web Service: 没有选择文件")
        return "没有选择文件", 400

    file = request.files['link_file']
    platform = request.form.get('platform', 'android').lower()

    if file.filename == '':
        print("Web Service: 文件名为空")
        return "没有选择文件", 400

    filepath = None
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"Web Service: 闲鱼文件已上传: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            short_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        results_list = [None] * len(short_urls)
        if not short_urls:
            print("Web Service: 上传的文件为空或不包含有效链接")
            return "上传的文件为空或不包含有效链接", 400

        print(f"Web Service: 开始处理 {len(short_urls)} 个闲鱼链接...")
        success_count = 0
        fail_count = 0

        def process_link(idx, url):
            try:
                deeplink = get_xianyu_deeplink(url, None, platform)
                if deeplink:
                    result = {'原始链接': url, 'Deeplink': deeplink, '状态': '成功'}
                else:
                    result = {'原始链接': url, 'Deeplink': '未提取到', '状态': '失败'}
            except Exception as e:
                result = {'原始链接': url, 'Deeplink': str(e), '状态': '错误'}
            return (idx, result)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_link, idx, url) for idx, url in enumerate(short_urls)]
            for future in as_completed(futures):
                idx, res = future.result()
                results_list[idx] = res
                if res['状态'] == '成功':
                    success_count += 1
                else:
                    fail_count += 1

        print("Web Service: 闲鱼链接处理完成，生成Excel...")
        df = pd.DataFrame(results_list)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        output_filename = f"xianyu_deeplink_results_{os.path.splitext(filename)[0]}.xlsx"
        print(f"Web Service: 准备发送文件: {output_filename}")
        response = make_response(send_file(
            excel_buffer,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
        response.set_cookie('batch_stats', f'success={success_count};fail={fail_count}', max_age=60)
        response.set_cookie('download_done', 'true', max_age=60, path='/')
        return response

    except Exception as e:
        print(f"Web Service: 闲鱼批量转链发生错误: {e}")
        return f"发生错误: {e}", 500
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Web Service: 已删除临时文件: {filepath}")

# ==================== 淘宝客活动短链批量获取 ====================

@app.route('/taobao/activity/batch', methods=['POST'])
def get_taobao_activity_batch():
    """
    批量获取淘宝客活动短链
    上传文件格式：每行一个 sub_pid (mm_xxx_xxx_xxx)
    """
    if 'link_file' not in request.files:
        print("Web Service: 没有选择文件")
        return "没有选择文件", 400

    file = request.files['link_file']
    
    # 获取活动素材ID参数，如果没有提供则使用默认值
    activity_material_id = request.form.get('activity_material_id', ACTIVITY_MATERIAL_ID).strip()
    
    if not activity_material_id:
        print("Web Service: 活动素材ID为空")
        return "活动素材ID不能为空", 400

    if file.filename == '':
        print("Web Service: 文件名为空")
        return "没有选择文件", 400

    filepath = None
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"Web Service: 文件已上传: {filepath}")
        print(f"Web Service: 使用活动素材ID: {activity_material_id}")

        # 读取文件中的 sub_pid 列表
        with open(filepath, 'r', encoding='utf-8') as f:
            sub_pids = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        if not sub_pids:
            print("Web Service: 上传的文件为空或不包含有效数据")
            return "上传的文件为空或不包含有效数据", 400

        print(f"Web Service: 开始处理 {len(sub_pids)} 个推广位...")
        
        # 创建淘宝客 API 实例
        api = TaobaoAPI(TAOBAO_APP_KEY, TAOBAO_APP_SECRET)
        
        results_list = [None] * len(sub_pids)
        success_count = 0
        fail_count = 0

        def process_sub_pid(idx, sub_pid):
            try:
                # 从 sub_pid (格式: mm_xxx_xxx_xxx) 中提取 adzone_id (最后一段)
                parts = sub_pid.split('_')
                if len(parts) < 4:
                    return (idx, {
                        '推广位': sub_pid,
                        '会场名称': '格式错误',
                        '推广长链': 'sub_pid格式不正确',
                        '推广短链': 'sub_pid格式不正确',
                        'Deeplink': '未获取',
                        'h5Dp': '未获取',
                        '状态': '失败'
                    })
                
                adzone_id = parts[-1]  # 取最后一个下划线分隔的部分
                
                # 1. 获取活动信息
                activity_info = api.get_activity_info(
                    activity_material_id=activity_material_id,
                    adzone_id=adzone_id,
                    sub_pid=sub_pid
                )
                
                if not activity_info:
                    return (idx, {
                        '推广位': sub_pid,
                        '会场名称': '获取失败',
                        '推广长链': '获取失败',
                        '推广短链': '获取失败',
                        'Deeplink': '未获取',
                        'h5Dp': '未获取',
                        '状态': '失败'
                    })
                
                # 2. 获取推广长链
                click_url = activity_info.get('click_url')
                page_name = activity_info.get('page_name', '未知活动')
                
                if not click_url:
                    return (idx, {
                        '推广位': sub_pid,
                        '会场名称': page_name,
                        '推广长链': '未获取到',
                        '推广短链': '未获取到',
                        'Deeplink': '未获取',
                        'h5Dp': '未获取',
                        '状态': '失败'
                    })
                
                # 3. 转换为短链
                short_result = api.convert_to_short_url(click_url)
                
                if short_result and len(short_result) > 0:
                    short_url = short_result[0].get('content', '转换失败')
                    err_msg = short_result[0].get('err_msg', '')
                    
                    if err_msg == 'OK':
                        # 4. 使用推广短链调用 get_taobao_deeplink 获取 deeplink 和 h5Dp
                        deeplink = ''
                        h5_dp = ''
                        try:
                            deeplink, h5_dp = get_taobao_deeplink(short_url, None, 'ios')
                            if not deeplink:
                                # 使用 short_url 构建默认的 deeplink
                                encoded_url = quote(short_url, safe='')
                                deeplink = "tbopen://m.taobao.com/tbopen/index.html?h5Url=" + encoded_url
                            if not h5_dp:
                                # 使用 deeplink 构建 h5_dp
                                encoded_deeplink = quote(deeplink, safe='')
                                h5_dp = 'https://ace.tb.cn/t?smburl=' + encoded_deeplink
                        except Exception as e:
                            print(f"调用 get_taobao_deeplink 失败: {e}")
                            # 异常时使用 short_url 构建默认值
                            encoded_url = quote(short_url, safe='')
                            deeplink = "tbopen://m.taobao.com/tbopen/index.html?h5Url=" + encoded_url
                            h5_dp = 'https://ace.tb.cn/t?smburl=' + quote(deeplink, safe='')
                        
                        return (idx, {
                            '推广位': sub_pid,
                            '会场名称': page_name,
                            '推广长链': click_url,
                            '推广短链': short_url,
                            'Deeplink': deeplink,
                            'h5Dp': h5_dp,
                            '状态': '成功'
                        })
                    else:
                        return (idx, {
                            '推广位': sub_pid,
                            '会场名称': page_name,
                            '推广长链': click_url,
                            '推广短链': f'转换失败: {err_msg}',
                            'Deeplink': '未获取',
                            'h5Dp': '未获取',
                            '状态': '失败'
                        })
                else:
                    return (idx, {
                        '推广位': sub_pid,
                        '会场名称': page_name,
                        '推广长链': click_url,
                        '推广短链': '转换失败',
                        'Deeplink': '未获取',
                        'h5Dp': '未获取',
                        '状态': '失败'
                    })
                    
            except Exception as e:
                return (idx, {
                    '推广位': sub_pid,
                    '会场名称': '处理异常',
                    '推广长链': str(e),
                    '推广短链': '处理异常',
                    'Deeplink': '处理异常',
                    'h5Dp': '处理异常',
                    '状态': '错误'
                })

        # 顺序处理每个推广位
        for idx, sub_pid in enumerate(sub_pids):
            idx, res = process_sub_pid(idx, sub_pid)
            results_list[idx] = res
            if res['状态'] == '成功':
                success_count += 1
            else:
                fail_count += 1
            print(f"Web Service: 处理进度 {success_count + fail_count}/{len(sub_pids)}")



        print("Web Service: 处理完成，生成Excel...")
        df = pd.DataFrame(results_list)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)

        output_filename = f"taobao_activity_shortlinks_{os.path.splitext(filename)[0]}.xlsx"
        print(f"Web Service: 准备发送文件: {output_filename}")
        response = make_response(send_file(
            excel_buffer,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
        response.set_cookie('batch_stats', f'success={success_count};fail={fail_count}', max_age=60)
        response.set_cookie('download_done', 'true', max_age=60, path='/')
        return response

    except Exception as e:
        print(f"Web Service: 淘宝客活动短链批量获取发生错误: {e}")
        return f"发生错误: {e}", 500
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Web Service: 已删除临时文件: {filepath}")

# ==================== 淘宝客活动报表批量查询 ====================

@app.route('/taobao/activity/report', methods=['POST'])
def get_taobao_activity_report():
    """
    批量查询淘宝客CPA活动报表
    上传Excel文件格式：必须包含 'pid' 列
    URL参数：
        - biz_date: 日期(yyyyMMdd)，必填
        - query_type: 查询类型，1-推广 2-拉新，默认1
        - event_id: CPA活动ID，默认3924553（福利购），可选3718079（超级红包）
    """
    # 获取URL参数
    biz_date = request.form.get('biz_date') or request.args.get('biz_date')
    query_type_str = request.form.get('query_type') or request.args.get('query_type', '1')
    event_id = request.form.get('event_id') or request.args.get('event_id', DEFAULT_EVENT_ID)
    
    if not biz_date:
        return "biz_date参数必填 (格式: yyyyMMdd)", 400
    
    try:
        query_type = int(query_type_str)
    except ValueError:
        query_type = 1
    
    # 检查上传文件
    if 'link_file' not in request.files:
        return "没有选择文件", 400
    
    file = request.files['link_file']
    if file.filename == '':
        return "没有选择文件", 400
    
    # 验证文件扩展名
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return "只支持.xlsx和.xls文件", 400
    
    filepath = None
    try:
        # 保存上传的文件
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        print(f"Web Service: 活动报表文件已上传: {filepath}")
        
        # 读取Excel文件
        df = pd.read_excel(filepath)
        
        # 检查是否有pid列
        if 'pid' not in df.columns:
            return "Excel文件必须包含 'pid' 列", 400
        
        # 提取pid列表
        pids = df['pid'].dropna().astype(str).tolist()
        
        if not pids:
            return "Excel文件中没有有效的pid数据", 400
        
        print(f"Web Service: 开始查询 {len(pids)} 个推广位的活动报表...")
        
        # 创建淘宝客活动报表API实例
        api = TaobaoActivityReportAPI(TAOBAO_APP_KEY, TAOBAO_APP_SECRET)
        
        # 准备结果数据
        results_list = []
        success_count = 0
        fail_count = 0
        
        # 计算前一天日期
        from datetime import datetime, timedelta
        current_date = datetime.strptime(biz_date, '%Y%m%d')
        previous_date = current_date - timedelta(days=1)
        previous_biz_date = previous_date.strftime('%Y%m%d')
        
        print(f"Web Service: 当前日期: {biz_date}, 前一天日期: {previous_biz_date}")
        
        # 顺序查询每个pid
        for idx, pid in enumerate(pids, 1):
            pid = pid.strip()
            if not pid:
                continue
            
            print(f"Web Service: 查询进度 {idx}/{len(pids)} - pid: {pid}")
            
            try:
                # 查询当前日期数据
                result_current = api.get_activity_report(
                    event_id=event_id,
                    biz_date=biz_date,
                    query_type=query_type,
                    pid=pid
                )
                
                # 查询前一天日期数据
                result_previous = api.get_activity_report(
                    event_id=event_id,
                    biz_date=previous_biz_date,
                    query_type=query_type,
                    pid=pid
                )
                
                # 提取数据
                current_data = None
                previous_data = None
                
                if result_current and result_current['data'] and len(result_current['data']) > 0:
                    current_data = result_current['data'][0]
                
                if result_previous and result_previous['data'] and len(result_previous['data']) > 0:
                    previous_data = result_previous['data'][0]
                
                # 定义安全减法函数
                def safe_subtract(current_val, previous_val):
                    """安全减法，处理各种数据类型"""
                    try:
                        if isinstance(current_val, str):
                            current_val = current_val.strip()
                            if not current_val or current_val == '':
                                current_val = 0
                            else:
                                current_val = float(current_val)
                        else:
                            current_val = float(current_val) if current_val else 0
                        
                        if isinstance(previous_val, str):
                            previous_val = previous_val.strip()
                            if not previous_val or previous_val == '':
                                previous_val = 0
                            else:
                                previous_val = float(previous_val)
                        else:
                            previous_val = float(previous_val) if previous_val else 0
                        
                        diff = current_val - previous_val
                        return int(diff) if diff == int(diff) else round(diff, 2)
                    except (ValueError, TypeError):
                        return current_val
                
                if current_data:
                    # 有当前日期数据
                    current_ext = current_data['ext_info_parsed']
                    previous_ext = previous_data['ext_info_parsed'] if previous_data else {}
                    
                    # 计算基础字段差值
                    union_30d_lx_uv_diff = safe_subtract(
                        current_data['union_30d_lx_uv'],
                        previous_data['union_30d_lx_uv'] if previous_data else 0
                    )
                    reward_amount_diff = safe_subtract(
                        current_data['reward_amount'],
                        previous_data['reward_amount'] if previous_data else 0
                    )
                    
                    # 根据活动类型处理不同的字段
                    if event_id == '3924553':
                        # 福利购活动
                        crowd1_diff = safe_subtract(
                            current_ext.get('crowd1_reward_uv', ''),
                            previous_ext.get('crowd1_reward_uv', '') if previous_data else 0
                        )
                        crowd2_diff = safe_subtract(
                            current_ext.get('crowd2_reward_uv', ''),
                            previous_ext.get('crowd2_reward_uv', '') if previous_data else 0
                        )
                        crowd3_diff = safe_subtract(
                            current_ext.get('crowd3_reward_uv', ''),
                            previous_ext.get('crowd3_reward_uv', '') if previous_data else 0
                        )
                        crowd4_diff = safe_subtract(
                            current_ext.get('crowd4_reward_uv', ''),
                            previous_ext.get('crowd4_reward_uv', '') if previous_data else 0
                        )
                        crowd5_diff = safe_subtract(
                            current_ext.get('crowd5_reward_uv', ''),
                            previous_ext.get('crowd5_reward_uv', '') if previous_data else 0
                        )
                        
                        # 根据 query_type 设置不同的列名
                        if query_type == 1:
                            results_list.append({
                                'pid': current_data['pid'],
                                'biz_date': current_data['biz_date'],
                                '符合奖励要求的累计用户数': union_30d_lx_uv_diff,
                                '奖励金额': reward_amount_diff,
                                '人群1预估奖励uv': crowd1_diff,
                                '人群2预估奖励uv': crowd2_diff,
                                '人群3预估奖励uv': crowd3_diff,
                                '人群4预估奖励uv': crowd4_diff,
                                '人群5预估奖励uv': crowd5_diff,
                                '账号总开奖率': current_ext.get('account_draw_rate', 0),
                                '开奖率': current_ext.get('draw_rate', 0),
                                '更新时间': current_ext.get('update_time', ''),
                                '状态': '成功'
                            })
                        else:
                            results_list.append({
                                'pid': current_data['pid'],
                                'biz_date': current_data['biz_date'],
                                '符合奖励要求的累计用户数': union_30d_lx_uv_diff,
                                '奖励金额': reward_amount_diff,
                                '人群1结算奖励uv': crowd1_diff,
                                '人群2结算奖励uv': crowd2_diff,
                                '人群3结算奖励uv': crowd3_diff,
                                '人群4结算奖励uv': crowd4_diff,
                                '人群5结算奖励uv': crowd5_diff,
                                '账号总开奖率': current_ext.get('account_draw_rate', 0),
                                '开奖率': current_ext.get('draw_rate', 0),
                                '更新时间': current_ext.get('update_time', ''),
                                '状态': '成功'
                            })
                    
                    elif event_id == '3718079':
                        # 超级红包活动
                        settlement_reward_uv_diff = safe_subtract(
                            current_ext.get('settlement_reward_uv', ''),
                            previous_ext.get('settlement_reward_uv', '') if previous_data else 0
                        )
                        if settlement_reward_uv_diff == 0:
                            settlement_reward_uv_diff = current_ext.get('settlement_reward_uv', 0)
                        if union_30d_lx_uv_diff == 0:
                            union_30d_lx_uv_diff = current_data.get('union_30d_lx_uv', 0)
                        
                        if query_type == 1:
                            results_list.append({
                                'pid': current_data['pid'],
                                'biz_date': current_data['biz_date'],
                                '符合奖励要求的累计用户数': union_30d_lx_uv_diff,
                                '用户质量等级': current_ext.get('user_quality_level', ''),
                                '预估奖励uv': settlement_reward_uv_diff,
                                '账号总开奖率': current_ext.get('account_draw_rate', 0),
                                '开奖率': current_ext.get('draw_rate', 0),
                                '更新时间': current_ext.get('update_time', ''),
                                '状态': '成功'
                            })
                        else:
                            results_list.append({
                                'pid': current_data['pid'],
                                'biz_date': current_data['biz_date'],
                                '符合奖励要求的累计用户数': union_30d_lx_uv_diff,
                                '用户质量等级': current_ext.get('user_quality_level', ''),
                                '结算奖励uv': settlement_reward_uv_diff,
                                '账号总开奖率': current_ext.get('account_draw_rate', 0),
                                '开奖率': current_ext.get('draw_rate', 0),
                                '更新时间': current_ext.get('update_time', ''),
                                '状态': '成功'
                            })
                    
                    success_count += 1
                else:
                    # 无数据
                    if event_id == '3924553':
                        # 福利购活动
                        if query_type == 1:
                            results_list.append({
                                'pid': pid,
                                'biz_date': biz_date,
                                '符合奖励要求的累计用户数': 'No data',
                                '奖励金额': '',
                                '人群1预估奖励uv': '',
                                '人群2预估奖励uv': '',
                                '人群3预估奖励uv': '',
                                '人群4预估奖励uv': '',
                                '人群5预估奖励uv': '',
                                '账号总开奖率': '',
                                '开奖率': '',
                                '更新时间': '',
                                '状态': '无数据'
                            })
                        else:
                            results_list.append({
                                'pid': pid,
                                'biz_date': biz_date,
                                '符合奖励要求的累计用户数': 'No data',
                                '奖励金额': '',
                                '人群1结算奖励uv': '',
                                '人群2结算奖励uv': '',
                                '人群3结算奖励uv': '',
                                '人群4结算奖励uv': '',
                                '人群5结算奖励uv': '',
                                '账号总开奖率': '',
                                '开奖率': '',
                                '更新时间': '',
                                '状态': '无数据'
                            })
                    elif event_id == '3718079':
                        # 超级红包活动
                        if query_type == 1:
                            results_list.append({
                                'pid': pid,
                                'biz_date': biz_date,
                                '符合奖励要求的累计用户数': 'No data',
                                '奖励金额': '',
                                '用户质量等级': '',
                                '预估奖励uv': '',
                                '账号总开奖率': '',
                                '开奖率': '',
                                '更新时间': '',
                                '状态': '无数据'
                            })
                        else:
                            results_list.append({
                                'pid': pid,
                                'biz_date': biz_date,
                                '符合奖励要求的累计用户数': 'No data',
                                '奖励金额': '',
                                '用户质量等级': '',
                                '结算奖励uv': '',
                                '账号总开奖率': '',
                                '开奖率': '',
                                '更新时间': '',
                                '状态': '无数据'
                            })
                    fail_count += 1
                    
            except Exception as e:
                # 查询失败
                print(f"Web Service: 查询pid {pid} 失败: {e}")
                if event_id == '3924553':
                    # 福利购活动
                    if query_type == 1:
                        results_list.append({
                            'pid': pid,
                            'biz_date': biz_date,
                            '符合奖励要求的累计用户数': f'Error: {str(e)}',
                            '奖励金额': '',
                            '人群1预估奖励uv': '',
                            '人群2预估奖励uv': '',
                            '人群3预估奖励uv': '',
                            '人群4预估奖励uv': '',
                            '人群5预估奖励uv': '',
                            '账号总开奖率': '',
                            '开奖率': '',
                            '更新时间': '',
                            '状态': '失败'
                        })
                    else:
                        results_list.append({
                            'pid': pid,
                            'biz_date': biz_date,
                            '符合奖励要求的累计用户数': f'Error: {str(e)}',
                            '奖励金额': '',
                            '人群1结算奖励uv': '',
                            '人群2结算奖励uv': '',
                            '人群3结算奖励uv': '',
                            '人群4结算奖励uv': '',
                            '人群5结算奖励uv': '',
                            '账号总开奖率': '',
                            '开奖率': '',
                            '更新时间': '',
                            '状态': '失败'
                        })
                elif event_id == '3718079':
                    # 超级红包活动
                    if query_type == 1:
                        results_list.append({
                            'pid': pid,
                            'biz_date': biz_date,
                            '符合奖励要求的累计用户数': f'Error: {str(e)}',
                            '奖励金额': '',
                            '用户质量等级': '',
                            '预估奖励uv': '',
                            '账号总开奖率': '',
                            '开奖率': '',
                            '更新时间': '',
                            '状态': '失败'
                        })  
                    else:
                        results_list.append({
                            'pid': pid,
                            'biz_date': biz_date,
                            '符合奖励要求的累计用户数': f'Error: {str(e)}',
                            '奖励金额': '',
                            '用户质量等级': '',
                            '结算奖励uv': '',
                            '账号总开奖率': '',
                            '开奖率': '',
                            '更新时间': '',
                            '状态': '失败'
                        })
                fail_count += 1
        
        print("Web Service: 查询完成，生成Excel...")
        
        # 生成Excel
        result_df = pd.DataFrame(results_list)
        excel_buffer = BytesIO()
        result_df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        
        output_filename = f"taobao_activity_report_{biz_date}.xlsx"
        print(f"Web Service: 准备发送文件: {output_filename}")
        
        response = make_response(send_file(
            excel_buffer,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
        response.set_cookie('batch_stats', f'success={success_count};fail={fail_count}', max_age=60)
        response.set_cookie('download_done', 'true', max_age=60, path='/')
        return response
        
    except Exception as e:
        print(f"Web Service: 淘宝客活动报表查询发生错误: {e}")
        import traceback
        traceback.print_exc()
        return f"发生错误: {e}", 500
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Web Service: 已删除临时文件: {filepath}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
