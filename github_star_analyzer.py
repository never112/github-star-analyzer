#!/usr/bin/env python3
"""
GitHub Star Analyzer - 分析 GitHub 仓库的 Star 时间分布和地区分布
"""

import os
import json
import argparse
from datetime import datetime
from collections import Counter
from pathlib import Path

import requests
from jinja2 import Template


class GitHubStarAnalyzer:
    def __init__(self, repo: str, token: str = None):
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        
        self.stargazers = []
        self.hourly_cn = [0] * 24
        self.hourly_utc = [0] * 24
        self.daily_counts = Counter()
        self.location_counts = Counter()
        
    def fetch_stargazers(self) -> list:
        """获取所有 stargazers 数据（分页）"""
        print(f"📡 正在获取 {self.repo} 的 stargazers...")
        
        star_headers = {"Accept": "application/vnd.github.v3.star+json"}
        if self.token:
            star_headers["Authorization"] = f"token {self.token}"
        
        url = f"https://api.github.com/repos/{self.repo}/stargazers"
        params = {"per_page": 100}
        all_stargazers = []
        page = 1
        
        while True:
            params["page"] = page
            response = requests.get(url, headers=star_headers, params=params)
            
            if response.status_code == 403:
                raise Exception("API 速率限制，请设置 GITHUB_TOKEN 环境变量")
            
            if response.status_code != 200:
                raise Exception(f"API 错误: {response.status_code} - {response.text}")
            
            data = response.json()
            if not data:
                break
            
            all_stargazers.extend(data)
            print(f"  已获取 {len(all_stargazers)} 条记录...")
            
            if len(data) < 100:
                break
            page += 1
        
        self.stargazers = all_stargazers
        print(f"✅ 共获取 {len(all_stargazers)} 个 stars")
        return all_stargazers
    
    def analyze_time_distribution(self):
        """分析时间分布（24小时）"""
        print("📊 分析时间分布...")
        
        for sg in self.stargazers:
            starred_at = sg.get("starred_at", "")
            if not starred_at:
                continue
            
            try:
                dt = datetime.fromisoformat(starred_at.replace("Z", "+00:00"))
                
                hour_utc = dt.hour
                self.hourly_utc[hour_utc] += 1
                
                hour_cn = (dt.hour + 8) % 24
                self.hourly_cn[hour_cn] += 1
                
                date_str = dt.strftime("%Y-%m-%d")
                self.daily_counts[date_str] += 1
                
            except Exception as e:
                print(f"  警告: 解析时间失败 {starred_at}: {e}")
    
    def _normalize_location(self, location: str) -> str:
        """标准化地区名称"""
        location_lower = location.lower().strip()
        
        if any(kw in location_lower for kw in ["shanghai", "上海"]):
            return "🇨🇳 上海"
        if any(kw in location_lower for kw in ["beijing", "北京"]):
            return "🇨🇳 北京"
        if any(kw in location_lower for kw in ["shenzhen", "深圳"]):
            return "🇨🇳 深圳"
        if any(kw in location_lower for kw in ["guangzhou", "广州"]):
            return "🇨🇳 广州"
        if any(kw in location_lower for kw in ["hangzhou", "杭州"]):
            return "🇨🇳 杭州"
        if any(kw in location_lower for kw in ["chengdu", "成都"]):
            return "🇨🇳 成都"
        if any(kw in location_lower for kw in ["changsha", "长沙"]):
            return "🇨🇳 长沙"
        if any(kw in location_lower for kw in ["nanjing", "南京"]):
            return "🇨🇳 南京"
        if any(kw in location_lower for kw in ["wuhan", "武汉"]):
            return "🇨🇳 武汉"
        if any(kw in location_lower for kw in ["usa", "united states", "america", "us", "美国"]):
            return "🇺🇸 美国"
        if any(kw in location_lower for kw in ["japan", "tokyo", "日本", "东京"]):
            return "🇯🇵 日本"
        if any(kw in location_lower for kw in ["korea", "seoul", "韩国", "首尔"]):
            return "🇰🇷 韩国"
        if any(kw in location_lower for kw in ["thailand", "bangkok", "泰国"]):
            return "🇹🇭 泰国"
        if any(kw in location_lower for kw in ["singapore", "新加坡"]):
            return "🇸🇬 新加坡"
        if "china" in location_lower or "中国" in location:
            return f"🇨🇳 {location}"
        
        return location
    
    def _fetch_user_details(self, logins: list) -> dict:
        """批量获取用户详情（包含 location），带速率限制处理"""
        import time
        user_details = {}
        failed_logins = []
        print(f"  📥 正在获取 {len(logins)} 个用户的详细信息...")
        
        for i, login in enumerate(logins):
            try:
                resp = requests.get(
                    f"https://api.github.com/users/{login}",
                    headers=self.headers,
                    timeout=15
                )
                
                if resp.status_code == 200:
                    user_data = resp.json()
                    user_details[login] = user_data.get("location", "")
                elif resp.status_code == 403:
                    # 速率限制，等待后重试
                    try:
                        reset_time = int(resp.headers.get('X-RateLimit-Reset', 0))
                        wait_time = max(reset_time - time.time(), 1)
                        if wait_time < 60:
                            print(f"\n  ⚠️ API 限流，等待 {int(wait_time)} 秒...")
                            time.sleep(min(wait_time + 1, 60))
                            # 重试一次
                            resp = requests.get(
                                f"https://api.github.com/users/{login}",
                                headers=self.headers,
                                timeout=15
                            )
                            if resp.status_code == 200:
                                user_data = resp.json()
                                user_details[login] = user_data.get("location", "")
                            else:
                                failed_logins.append(login)
                                user_details[login] = ""
                        else:
                            print(f"\n  ⚠️ 速率限制需等待 {int(wait_time/60)} 分钟，跳过...")
                            failed_logins.append(login)
                            user_details[login] = ""
                    except:
                        failed_logins.append(login)
                        user_details[login] = ""
                else:
                    user_details[login] = ""
                    
                # 每 10 个请求加一点延迟，避免太快触发限流
                if (i + 1) % 10 == 0:
                    time.sleep(0.5)
                
                if (i + 1) % 50 == 0:
                    print(f"  已获取 {i + 1}/{len(logins)} 个用户详情...")
                    
            except Exception as e:
                user_details[login] = ""
        
        if failed_logins:
            print(f"  ⚠️ {len(failed_logins)} 个用户获取失败")
        
        return user_details
    
    def analyze_location_distribution(self):
        """分析地区分布"""
        print("🌍 分析地区分布...")
        
        logins = []
        for sg in self.stargazers:
            user_data = sg.get("user", sg)
            login = user_data.get("login")
            if login and login not in logins:
                logins.append(login)
        
        user_details = self._fetch_user_details(logins)
        
        for login in logins:
            location = user_details.get(login, "")
            if location:
                normalized = self._normalize_location(location)
                self.location_counts[normalized] += 1
            else:
                self.location_counts["❓ 未知地区"] += 1
        
        known = {k: v for k, v in self.location_counts.items() if k != "❓ 未知地区"}
        if known:
            print(f"  已知地区: {dict(sorted(known.items(), key=lambda x: x[1], reverse=True))}")
    
    def generate_report(self, output_path: str = "star-analysis.html"):
        """生成 HTML 报告"""
        print(f"📝 生成报告: {output_path}")
        
        total = len(self.stargazers)
        hours = [f"{i:02d}:00" for i in range(24)]
        
        # 每日数据
        sorted_dates = sorted(self.daily_counts.keys())
        daily_dates = [d[5:] for d in sorted_dates]
        daily_stars = [self.daily_counts[d] for d in sorted_dates]
        
        # 累计数据
        cumulative = []
        total_cum = 0
        for d in sorted_dates:
            total_cum += self.daily_counts[d]
            cumulative.append(total_cum)
        
        # 地区数据
        location_items = sorted(self.location_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 统计计算
        known_count = sum(v for k, v in self.location_counts.items() if k != "❓ 未知地区")
        unknown_count = self.location_counts.get("❓ 未知地区", 0)
        active_days = len(self.daily_counts)
        daily_avg = round(total / active_days, 1) if active_days > 0 else 0
        
        # 高峰分析
        max_hour_cn = self.hourly_cn.index(max(self.hourly_cn))
        max_hour_utc = self.hourly_utc.index(max(self.hourly_utc))
        max_hour_cn_val = max(self.hourly_cn)
        max_hour_utc_val = max(self.hourly_utc)
        
        # 北京时间高峰时段（连续3小时）
        peak_3h = []
        for i in range(24):
            total_3h = sum(self.hourly_cn[(i+j) % 24] for j in range(3))
            peak_3h.append((total_3h, i))
        peak_3h.sort(reverse=True)
        peak_window_start = peak_3h[0][1]
        peak_window_pct = round(peak_3h[0][0] / total * 100, 1) if total > 0 else 0
        
        # 最大单日
        max_daily = max(self.daily_counts.values()) if self.daily_counts else 0
        max_daily_date = [k for k, v in self.daily_counts.items() if v == max_daily]
        max_daily_date_str = max_daily_date[0][5:] if max_daily_date else "N/A"
        
        # 地区百分比
        known_pct = round(known_count / total * 100, 1) if total > 0 else 0
        
        # Top地区
        top_locations = location_items[:3] if len(location_items) > 3 else location_items
        top_location_str = "、".join([f"{k}({v}人)" for k, v in top_locations if k != "❓ 未知地区"])
        
        # 渲染模板
        html_content = self._render_template(
            repo=self.repo,
            total_stars=total,
            known_count=known_count,
            unknown_count=unknown_count,
            known_pct=known_pct,
            active_days=active_days,
            daily_avg=daily_avg,
            hours=hours,
            hourly_cn=self.hourly_cn,
            hourly_utc=self.hourly_utc,
            max_hour_cn=max_hour_cn,
            max_hour_utc=max_hour_utc,
            max_hour_cn_val=max_hour_cn_val,
            max_hour_utc_val=max_hour_utc_val,
            peak_window_start=peak_window_start,
            peak_window_pct=peak_window_pct,
            daily_dates=daily_dates,
            daily_stars=daily_stars,
            cumulative=cumulative,
            max_daily=max_daily,
            max_daily_date=max_daily_date_str,
            location_items=location_items,
            top_location_str=top_location_str
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"✅ 报告已生成: {output_path}")
        return output_path
    
    def _render_template(self, **data) -> str:
        """渲染 HTML 模板"""
        template = Template('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ repo }} Star 分析</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            padding: 20px;
            color: #fff;
        }
        .header {
            text-align: center;
            padding: 30px 0;
        }
        .header h1 {
            font-size: 2.2em;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }
        .header p {
            color: #a0a0a0;
            font-size: 1.1em;
        }
        .stats-row {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 25px 40px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .stat-card .number {
            font-size: 2.5em;
            font-weight: bold;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-card .label {
            color: #888;
            margin-top: 5px;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        @media (max-width: 1000px) {
            .charts-grid { grid-template-columns: 1fr; }
        }
        .chart-container {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        .chart-title {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .chart-title .icon {
            font-size: 1.4em;
        }
        .chart { height: 400px; }
        .full-width { grid-column: 1 / -1; }
        .insights {
            max-width: 1400px;
            margin: 30px auto;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            padding: 25px 30px;
        }
        .insights h3 {
            color: #00d4ff;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        .insights ul {
            list-style: none;
            line-height: 2;
        }
        .insights li {
            color: #c0c0c0;
            padding-left: 25px;
            position: relative;
        }
        .insights li::before {
            content: "→";
            position: absolute;
            left: 0;
            color: #7b2cbf;
        }
        .highlight { color: #00d4ff; font-weight: 600; }
        .highlight-pink { color: #ff6b9d; font-weight: 600; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 {{ repo }}</h1>
        <p>GitHub Star 时间与地区分布分析</p>
    </div>
    
    <div class="stats-row">
        <div class="stat-card">
            <div class="number">{{ total_stars }}</div>
            <div class="label">⭐ 总 Stars</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ known_count }}</div>
            <div class="label">📍 已知地区用户</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ active_days }}</div>
            <div class="label">📅 项目天数</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ daily_avg }}</div>
            <div class="label">📈 日均 Stars</div>
        </div>
    </div>
    
    <div class="charts-grid">
        <div class="chart-container full-width">
            <div class="chart-title"><span class="icon">📈</span> 每日 Star 趋势</div>
            <div id="chart-daily" class="chart"></div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title"><span class="icon">🕐</span> 24小时 Star 分布（北京时间）</div>
            <div id="chart-hourly-cn" class="chart"></div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title"><span class="icon">🌍</span> 24小时 Star 分布（UTC）</div>
            <div id="chart-hourly-utc" class="chart"></div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title"><span class="icon">📍</span> 用户地区分布</div>
            <div id="chart-location" class="chart"></div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title"><span class="icon">🗺️</span> 地区占比</div>
            <div id="chart-location-pie" class="chart"></div>
        </div>
    </div>
    
    <div class="insights">
        <h3>💡 关键洞察</h3>
        <ul>
            <li><span class="highlight">高峰时段（北京时间）</span>：{{ "%02d:00" | format(max_hour_cn) }}-{{ "%02d:00" | format((max_hour_cn + 1) % 24) }}，占单小时最高 <span class="highlight-pink">{{ max_hour_cn_val }} stars</span></li>
            <li><span class="highlight">主要用户群体</span>：{{ top_location_str if top_location_str else "数据较少" }}，占已知地区用户的 <span class="highlight-pink">{{ known_pct }}%</span></li>
            <li><span class="highlight">国际用户</span>：国际化程度{{ "有提升空间" if known_pct < 30 else "一般" }}</li>
            <li><span class="highlight">建议推广时间</span>：北京时间 {{ "%02d:00" | format(peak_window_start) }}-{{ "%02d:00" | format((peak_window_start + 3) % 24) }} 发布内容可获得最佳曝光</li>
            <li><span class="highlight">数据说明</span>：{{ unknown_count }}/{{ total_stars }}（{{ "%.1f" | format(unknown_count / total_stars * 100) }}%）用户未设置公开地区信息，实际分布可能更广</li>
        </ul>
    </div>

    <script>
        // 24小时数据（北京时间）
        const hourlyCN = {{ hourly_cn | tojson }};
        const hourlyUTC = {{ hourly_utc | tojson }};
        const hours = {{ hours | tojson }};
        
        // 每日 Star 数据
        const dailyDates = {{ daily_dates | tojson }};
        const dailyStars = {{ daily_stars | tojson }};
        const cumulativeStars = {{ cumulative | tojson }};
        
        // 地区数据
        const locationData = {{ location_items | tojson }};
        
        // 通用主题色
        const colors = ['#00d4ff', '#7b2cbf', '#ff6b9d', '#00f5d4', '#9b5de5', '#f15bb5', '#555555'];
        
        // 图表0：每日 Star 趋势
        const chart0 = echarts.init(document.getElementById('chart-daily'));
        chart0.setOption({
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(0,0,0,0.8)',
                borderColor: '#00d4ff',
                textStyle: { color: '#fff' },
                formatter: function(params) {
                    const date = params[0].axisValue;
                    const daily = params[0].value;
                    const cumul = params[1].value;
                    return date + '<br/>📅 当日: ' + daily + ' stars<br/>📊 累计: ' + cumul + ' stars';
                }
            },
            legend: {
                data: ['每日新增', '累计 Stars'],
                textStyle: { color: '#888' },
                top: 0
            },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
            xAxis: {
                type: 'category',
                data: dailyDates,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
                axisLabel: { color: '#888', fontSize: 10, rotate: 45 }
            },
            yAxis: [
                {
                    type: 'value',
                    name: '每日新增',
                    axisLine: { show: false },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                    axisLabel: { color: '#00d4ff' }
                },
                {
                    type: 'value',
                    name: '累计',
                    axisLine: { show: false },
                    splitLine: { show: false },
                    axisLabel: { color: '#ff6b9d' }
                }
            ],
            series: [
                {
                    name: '每日新增',
                    type: 'bar',
                    data: dailyStars,
                    itemStyle: {
                        borderRadius: [4, 4, 0, 0],
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#00d4ff' },
                            { offset: 1, color: '#7b2cbf' }
                        ])
                    }
                },
                {
                    name: '累计 Stars',
                    type: 'line',
                    yAxisIndex: 1,
                    data: cumulativeStars,
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    lineStyle: { color: '#ff6b9d', width: 3 },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(255,107,157,0.3)' },
                            { offset: 1, color: 'rgba(255,107,157,0)' }
                        ])
                    },
                    itemStyle: { color: '#ff6b9d' }
                }
            ]
        });
        
        // 图表1：北京时间24小时分布
        const chart1 = echarts.init(document.getElementById('chart-hourly-cn'));
        chart1.setOption({
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(0,0,0,0.8)',
                borderColor: '#00d4ff',
                textStyle: { color: '#fff' },
                formatter: params => params[0].name + '<br/>⭐ ' + params[0].value + ' stars'
            },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
            xAxis: {
                type: 'category',
                data: hours,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
                axisLabel: { color: '#888', fontSize: 10, interval: 2 }
            },
            yAxis: {
                type: 'value',
                axisLine: { show: false },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#888' }
            },
            series: [{
                type: 'bar',
                data: hourlyCN,
                itemStyle: {
                    borderRadius: [4, 4, 0, 0],
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#00d4ff' },
                        { offset: 1, color: '#7b2cbf' }
                    ])
                },
                emphasis: {
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#ff6b9d' },
                            { offset: 1, color: '#00d4ff' }
                        ])
                    }
                },
                markLine: {
                    silent: true,
                    data: [{ type: 'average', name: '平均' }],
                    lineStyle: { color: '#ff6b9d', type: 'dashed' },
                    label: { color: '#ff6b9d' }
                }
            }]
        });
        
        // 图表2：UTC 24小时分布
        const chart2 = echarts.init(document.getElementById('chart-hourly-utc'));
        chart2.setOption({
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(0,0,0,0.8)',
                borderColor: '#7b2cbf',
                textStyle: { color: '#fff' },
                formatter: params => params[0].name + ' UTC<br/>⭐ ' + params[0].value + ' stars'
            },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
            xAxis: {
                type: 'category',
                data: hours,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
                axisLabel: { color: '#888', fontSize: 10, interval: 2 }
            },
            yAxis: {
                type: 'value',
                axisLine: { show: false },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#888' }
            },
            series: [{
                type: 'bar',
                data: hourlyUTC,
                itemStyle: {
                    borderRadius: [4, 4, 0, 0],
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#7b2cbf' },
                        { offset: 1, color: '#00d4ff' }
                    ])
                },
                emphasis: {
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#ff6b9d' },
                            { offset: 1, color: '#7b2cbf' }
                        ])
                    }
                }
            }]
        });
        
        // 图表3：地区分布柱状图
        const chart3 = echarts.init(document.getElementById('chart-location'));
        chart3.setOption({
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(0,0,0,0.8)',
                borderColor: '#00f5d4',
                textStyle: { color: '#fff' }
            },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
            xAxis: {
                type: 'category',
                data: locationData.map(item => item[0]),
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
                axisLabel: { color: '#888', fontSize: 12 }
            },
            yAxis: {
                type: 'value',
                axisLine: { show: false },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#888' }
            },
            series: [{
                type: 'bar',
                data: locationData.map((item, i) => ({
                    value: item[1],
                    itemStyle: {
                        borderRadius: [4, 4, 0, 0],
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: colors[i % colors.length] },
                            { offset: 1, color: colors[(i + 1) % colors.length] }
                        ])
                    }
                }))
            }]
        });
        
        // 图表4：地区饼图
        const chart4 = echarts.init(document.getElementById('chart-location-pie'));
        chart4.setOption({
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(0,0,0,0.8)',
                borderColor: '#ff6b9d',
                textStyle: { color: '#fff' },
                formatter: '{b}: {c}人 ({d}%)'
            },
            legend: {
                orient: 'vertical',
                right: '5%',
                top: 'center',
                textStyle: { color: '#888' }
            },
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['40%', '50%'],
                avoidLabelOverlap: false,
                itemStyle: {
                    borderRadius: 10,
                    borderColor: 'rgba(0,0,0,0.3)',
                    borderWidth: 2
                },
                label: {
                    show: false,
                    position: 'center'
                },
                emphasis: {
                    label: {
                        show: true,
                        fontSize: 18,
                        fontWeight: 'bold',
                        color: '#fff'
                    }
                },
                labelLine: { show: false },
                data: locationData.map((item, i) => ({ 
                    name: item[0], 
                    value: item[1], 
                    itemStyle: { color: colors[i % colors.length] } 
                }))
            }]
        });
        
        // 响应式
        window.addEventListener('resize', () => {
            chart0.resize();
            chart1.resize();
            chart2.resize();
            chart3.resize();
            chart4.resize();
        });
    </script>
</body>
</html>
''')
        
        return template.render(**data)


def main():
    parser = argparse.ArgumentParser(description="GitHub Star 分析工具")
    parser.add_argument("repo", help="仓库名称，格式: owner/repo")
    parser.add_argument("--token", help="GitHub Personal Access Token", default=None)
    parser.add_argument("--output", "-o", help="输出文件路径", default="star-analysis.html")
    
    args = parser.parse_args()
    
    analyzer = GitHubStarAnalyzer(args.repo, args.token)
    analyzer.fetch_stargazers()
    analyzer.analyze_time_distribution()
    analyzer.analyze_location_distribution()
    analyzer.generate_report(args.output)


if __name__ == "__main__":
    main()
