FROM python:3.11-slim

LABEL maintainer="GitHub Star Analyzer"
LABEL description="分析 GitHub 仓库的 Star 时间分布和地区分布"

# 设置工作目录
WORKDIR /app

# 安装依赖（使用阿里云镜像）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 复制应用代码
COPY github_star_analyzer.py .

# 创建输出目录
RUN mkdir -p /output

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 默认命令
ENTRYPOINT ["python", "github_star_analyzer.py"]

# 默认参数（可通过 docker run 覆盖）
CMD ["--help"]
