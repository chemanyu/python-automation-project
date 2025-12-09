"""
淘宝客活动报表 API 调用模块
用于调用淘宝客CPA活动报表查询接口 (taobao.tbk.dg.cpa.activity.report)
"""
import hashlib
import time
import requests
import json
from typing import Dict, List, Optional


class TaobaoActivityReportAPI:
    """淘宝客活动报表 API 调用类"""
    
    def __init__(self, app_key: str, app_secret: str):
        """
        初始化淘宝客活动报表 API
        
        Args:
            app_key: TOP分配给应用的AppKey
            app_secret: TOP分配给应用的AppSecret（用于签名）
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.api_url = "http://gw.api.taobao.com/router/rest"
    
    def generate_sign(self, params: Dict[str, str]) -> str:
        """
        生成淘宝API签名（MD5算法）
        
        签名步骤：
        1. 对所有API请求参数（包括公共参数和业务参数，但除去sign参数），根据参数名称的ASCII码表的顺序排序
        2. 将排序好的参数名和参数值拼接在一起
        3. 把拼接好的字符串采用utf-8编码，使用签名算法对编码后的字节流进行摘要
        4. 将摘要得到的字节流结果使用十六进制大写表示
        
        Args:
            params: 请求参数字典
            
        Returns:
            签名字符串（大写）
        """
        # 1. 按ASCII顺序排序参数（去掉sign参数）
        sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])
        
        # 2. 拼接参数名与参数值（前后加上app_secret）
        sign_string = self.app_secret
        for key, value in sorted_params:
            sign_string += str(key) + str(value)
        sign_string += self.app_secret
        
        # 3. 使用md5加密
        md5_hash = hashlib.md5()
        md5_hash.update(sign_string.encode('utf-8'))
        
        # 4. 转换为大写
        sign = md5_hash.hexdigest().upper()
        
        return sign
    
    def get_activity_report(
        self,
        event_id: str,
        biz_date: str,
        query_type: int,
        pid: Optional[str] = None,
        page_no: int = 1,
        page_size: int = 10
    ) -> Optional[Dict]:
        """
        获取淘宝客CPA活动报表数据
        
        Args:
            event_id: CPA活动id，必填 (3654363-福利购, 3718079-超级红包)
            biz_date: 日期(yyyyMMdd)，必填
            query_type: 查询类型，1-推广 2-拉新，必填
            pid: 推广位id，可选
            page_no: 分页页码，从1开始，默认1
            page_size: 分页大小，默认10
            
        Returns:
            返回结果字典，包含报表数据列表，失败返回 None
            福利购 (3654363):
            {
                'request_id': '请求ID',
                'event_id': '活动ID',
                'data': [
                    {
                        'pid': '推广位id',
                        'biz_date': '统计日期',
                        'union_30d_lx_uv': '近30天拉新奖励计算用户量',
                        'reward_amount': '奖励金额',
                        'query_type': '查询类型',
                        'ext_info': '活动扩展信息(JSON字符串)',
                        'ext_info_parsed': {
                            'crowd1_reward_uv': '人群1结算奖励uv',
                            'crowd2_reward_uv': '人群2结算奖励uv',
                            'crowd3_reward_uv': '人群3结算奖励uv',
                            'crowd4_reward_uv': '人群4结算奖励uv',
                            'crowd5_reward_uv': '人群5结算奖励uv',
                            'account_draw_rate': '账号总开奖率',
                            'draw_rate': '开奖率',
                            'update_time': '更新时间'
                        }
                    }
                ]
            }
            超级红包 (3718079):
            {
                'request_id': '请求ID',
                'event_id': '活动ID',
                'data': [
                    {
                        'pid': '推广位id',
                        'biz_date': '统计日期',
                        'union_30d_lx_uv': '近30天拉新奖励计算用户量',
                        'reward_amount': '奖励金额',
                        'query_type': '查询类型',
                        'ext_info': '活动扩展信息(JSON字符串)',
                        'ext_info_parsed': {
                            'user_quality_level': '用户质量等级',
                            'account_draw_rate': '账号总开奖率',
                            'settlement_reward_uv': '结算奖励uv',
                            'draw_rate': '开奖率',
                            'update_time': '更新时间'
                        }
                    }
                ]
            }
        """
        # 构建公共参数
        params = {
            'method': 'taobao.tbk.dg.cpa.activity.report',
            'app_key': self.app_key,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'format': 'json',
            'v': '2.0',
            'sign_method': 'md5',
            'partner_id': 'top-apitools',
        }
        
        # 添加业务参数
        params['event_id'] = str(event_id)
        params['biz_date'] = str(biz_date)
        params['query_type'] = str(query_type)
        params['page_no'] = str(page_no)
        params['page_size'] = str(page_size)
        
        if pid:
            params['pid'] = str(pid)
        
        # 生成签名
        sign = self.generate_sign(params)
        params['sign'] = sign
        
        # 打印请求URL（调试用）
        print(f"请求URL: {self.api_url}?{self._build_query_string(params)}")
        
        try:
            # 发送GET请求
            response = requests.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            # 检查是否有错误
            if 'error_response' in result:
                error = result['error_response']
                print(f"API错误: code={error.get('code')}, msg={error.get('msg')}, sub_code={error.get('sub_code')}, sub_msg={error.get('sub_msg')}")
                return None
            
            # 提取报表数据
            if 'tbk_dg_cpa_activity_report_response' not in result:
                print(f"响应格式错误: {result}")
                return None
            
            response_data = result['tbk_dg_cpa_activity_report_response']
            request_id = response_data.get('request_id', '')
            
            # 提取数据列表
            data_list = []
            if 'result' in response_data and 'data' in response_data['result']:
                results = response_data['result']['data'].get('results', {})
                dto_list = results.get('vegas_cpa_report_d_t_o', [])
                
                for dto in dto_list:
                    item = {
                        'pid': dto.get('pid', ''),
                        'biz_date': dto.get('biz_date', ''),
                        'union_30d_lx_uv': dto.get('union_30d_lx_uv', 0),
                        'reward_amount': dto.get('reward_amount', '0'),
                        'query_type': dto.get('query_type', 0),
                        'relation_id': dto.get('relation_id', 0),
                        'ext_info': dto.get('ext_info', ''),
                    }
                    
                    # 解析ext_info，传入event_id以便识别活动类型
                    item['ext_info_parsed'] = self._parse_ext_info(item['ext_info'], event_id)
                    
                    data_list.append(item)
            
            return {
                'request_id': request_id,
                'event_id': event_id,
                'data': data_list
            }
            
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return None
        except Exception as e:
            print(f"处理响应时出错: {e}")
            return None
    
    def _parse_ext_info(self, ext_info_str: str, event_id: str = '3654363') -> Dict:
        """
        解析ext_info JSON字符串
        支持不同活动类型：
        - 3654363: 福利购 (预估数据和结算数据)
        - 3718079: 超级红包 (新字段结构)
        
        Args:
            ext_info_str: ext_info JSON字符串
            event_id: 活动ID，用于判断解析逻辑
            
        Returns:
            解析后的字典
        """
        # 福利购活动 (3654363)
        if event_id == '3654363':
            result = {
                'crowd1_reward_uv': '',
                'crowd2_reward_uv': '',
                'crowd3_reward_uv': '',
                'crowd4_reward_uv': '',
                'crowd5_reward_uv': '',
                'account_draw_rate': 0.0,
                'draw_rate': 0.0,
                'update_time': ''
            }
            
            if not ext_info_str:
                return result
            
            try:
                ext_data = json.loads(ext_info_str)
                
                # 提取各个字段 - 兼容预估和结算两种格式
                # 预估数据使用"人群X预估奖励uv"，结算数据使用"人群X结算奖励uv"
                result['crowd1_reward_uv'] = ext_data.get('人群1结算奖励uv') or ext_data.get('人群1预估奖励uv', '')
                result['crowd2_reward_uv'] = ext_data.get('人群2结算奖励uv') or ext_data.get('人群2预估奖励uv', '')
                result['crowd3_reward_uv'] = ext_data.get('人群3结算奖励uv') or ext_data.get('人群3预估奖励uv', '')
                result['crowd4_reward_uv'] = ext_data.get('人群4结算奖励uv') or ext_data.get('人群4预估奖励uv', '')
                result['crowd5_reward_uv'] = ext_data.get('人群5结算奖励uv') or ext_data.get('人群5预估奖励uv', '')
                result['account_draw_rate'] = ext_data.get('账号总开奖率（奖励计算用)', 0.0)
                result['draw_rate'] = ext_data.get('开奖率', 0.0)
                result['update_time'] = ext_data.get('更新时间', '')
                
            except json.JSONDecodeError as e:
                print(f"解析ext_info失败: {e}")
            
            return result
        
        # 超级红包活动 (3718079)
        elif event_id == '3718079':
            result = {
                'user_quality_level': '',
                'account_draw_rate': 0.0,
                'settlement_reward_uv': '',
                'draw_rate': 0.0,
                'update_time': ''
            }
            
            if not ext_info_str:
                return result
            
            try:
                ext_data = json.loads(ext_info_str)
                
                # 超级红包的字段结构
                result['user_quality_level'] = ext_data.get('用户质量等级', '')
                result['account_draw_rate'] = ext_data.get('账号总开奖率（奖励计算用)', 0.0)
                result['settlement_reward_uv'] = ext_data.get('结算奖励uv') or ext_data.get('预估奖励uv', '')
                result['draw_rate'] = ext_data.get('开奖率', 0.0)
                result['update_time'] = ext_data.get('更新时间', '')
                
            except json.JSONDecodeError as e:
                print(f"解析ext_info失败: {e}")
            
            return result
        
        # 默认返回空字典（未知活动类型）
        else:
            return {}
    
    def _build_query_string(self, params: Dict[str, str]) -> str:
        """构建查询字符串（用于调试）"""
        from urllib.parse import urlencode
        return urlencode(params)


# 使用示例
if __name__ == '__main__':
    # 配置信息
    APP_KEY = '35238422'
    APP_SECRET = '3e2c5266e7a3689ac909659a203ce301'
    
    # 创建API实例
    api = TaobaoActivityReportAPI(APP_KEY, APP_SECRET)
    
    # 查询参数
    event_id = '3654363'  # CPA活动ID
    biz_date = '20241201'  # 日期 yyyyMMdd
    query_type = 1  # 1-推广 2-拉新
    pid = 'mm_874030133_3340450211_116193900321'  # 推广位ID（可选）
    
    # 调用API
    result = api.get_activity_report(
        event_id=event_id,
        biz_date=biz_date,
        query_type=query_type,
        pid=pid
    )
    
    # 打印结果
    if result:
        print(f"\n请求ID: {result['request_id']}")
        print(f"数据条数: {len(result['data'])}")
        
        for item in result['data']:
            print(f"\n推广位: {item['pid']}")
            print(f"统计日期: {item['biz_date']}")
            print(f"符合奖励要求的累计用户数: {item['union_30d_lx_uv']}")
            print(f"奖励金额: {item['reward_amount']}")
            
            ext = item['ext_info_parsed']
            print(f"人群1结算奖励uv: {ext['crowd1_reward_uv']}")
            print(f"人群2结算奖励uv: {ext['crowd2_reward_uv']}")
            print(f"人群3结算奖励uv: {ext['crowd3_reward_uv']}")
            print(f"人群4结算奖励uv: {ext['crowd4_reward_uv']}")
            print(f"人群5结算奖励uv: {ext['crowd5_reward_uv']}")
            print(f"账号总开奖率: {ext['account_draw_rate']}")
            print(f"开奖率: {ext['draw_rate']}")
            print(f"更新时间: {ext['update_time']}")
    else:
        print("查询失败")
