# 服务器部署

这个版本按 Web 服务部署设计：用户通过网址访问前端，前端请求同域 `/api`，Nginx 把请求转发到 FastAPI，数据写入 PostgreSQL，上传文件和导出文件保存在服务端数据卷。

## 一键启动

服务器安装 Docker 和 Docker Compose 后，在项目根目录执行：

```bash
cp .env.example .env
docker compose up -d --build
```

默认访问地址：

```text
http://服务器IP:8080
```

如果要改端口，修改 `.env`：

```env
APP_PORT=80
```

## 域名和 HTTPS

生产环境建议在服务器外层再接一个 HTTPS 反向代理，例如 Nginx、宝塔、Caddy 或云厂商负载均衡，把域名转发到本机 `APP_PORT`。

`.env` 里的 `CORS_ORIGINS` 填真实访问域名：

```env
CORS_ORIGINS=https://qa-review.example.com
```

## 数据持久化

Docker Compose 会创建两个数据卷：

```text
postgres_data  数据库
qa_storage     上传的数据集、媒体文件、导出文件
```

升级代码时不要删除这两个 volume。

## 服务器版导入逻辑

服务器版默认关闭本地路径导入：

```env
ALLOW_SERVER_PATH_IMPORT=false
```

用户应该在网页里上传：

- JSON / JSONL / CSV 数据文件
- 图文问答数据集对应的 ZIP、图片文件或图片文件夹

如果管理员确实要让后端读取服务器磁盘上的文件，可以改成：

```env
ALLOW_SERVER_PATH_IMPORT=true
```

这个开关只表示“读取服务器自己的路径”，不是读取访问者电脑上的路径。

## 常用命令

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
docker compose up -d --build
```

## 健康检查

后端健康接口：

```text
http://服务器IP:8080/api/health
```
