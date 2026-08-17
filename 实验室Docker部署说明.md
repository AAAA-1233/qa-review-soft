# 实验室本地服务器 Docker 部署

## 1. 解压

把压缩包拷贝到服务器后解压：

```bash
unzip qa-review-soft-docker.zip
cd qa-review-soft
```

## 2. 配置

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env`，至少修改：

```env
APP_PORT=8080
POSTGRES_PASSWORD=改成一个数据库密码
AUTH_SECRET=改成一段很长的随机字符串
CORS_ORIGINS=http://服务器IP:8080
```

如果使用域名：

```env
CORS_ORIGINS=http://你的域名或服务器IP:8080
```

## 3. 启动

```bash
docker compose up -d --build
```

访问：

```text
http://服务器IP:8080
```

## 4. 查看状态

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

## 5. 数据保存位置

Docker 会创建两个 volume：

```text
postgres_data  数据库
qa_storage     上传文件、媒体资源、导出文件
```

不要删除这两个 volume，否则数据会丢。

## 6. 更新版本

以后替换代码后重新构建：

```bash
docker compose up -d --build
```
