# Render 后端部署

这个项目可以用 Render 免费 Web Service 部署后端，前端继续放 Cloudflare Pages，数据库使用 Neon PostgreSQL。

## 结构

```text
Cloudflare Pages  前端
Render            FastAPI 后端
Neon              PostgreSQL 数据库
```

## 1. 准备 Neon 数据库

在 Neon 新建数据库，复制连接串，格式类似：

```text
postgresql://user:password@xxx.neon.tech/dbname?sslmode=require
```

## 2. 部署 Render 后端

Render 里选择：

```text
New + -> Blueprint
```

连接 GitHub 仓库：

```text
AAAA-1233/qa-review-soft
```

Render 会读取根目录的 `render.yaml`，创建 `qa-review-backend` 服务。

需要在 Render 填环境变量：

```env
DATABASE_URL=你的 Neon 数据库连接串
CORS_ORIGINS=https://你的前端.pages.dev
AUTH_SECRET=一段随机长字符串
EMAIL_FROM=你的发件邮箱或 Resend 发件人
RESEND_API_KEY=你的 Resend API Key
```

第一次还没有前端地址时，可以先临时填：

```env
CORS_ORIGINS=http://localhost:5173
```

后端部署成功后，Render 会给一个地址：

```text
https://qa-review-backend.onrender.com
```

健康检查：

```text
https://qa-review-backend.onrender.com/health
```

应该返回：

```json
{"ok": true}
```

## 3. 邮箱验证码

系统现在按邮箱验证码登录，每个邮箱只会看到自己的项目、样本、审核状态和导出文件。

免费发信可以先用 Resend 或 Brevo：

- Resend：后端填 `RESEND_API_KEY` 和 `EMAIL_FROM`。
- Brevo：后端填 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`、`EMAIL_FROM`。

如果只是本地开发，可以临时开启：

```env
AUTH_CODE_DEV_MODE=true
```

这时接口会直接返回测试验证码，不会真的发邮件。线上不要开启。

## 4. 部署 Cloudflare 前端

Cloudflare Workers / Pages 连接同一个 GitHub 仓库：

```text
AAAA-1233/qa-review-soft
```

设置：

```text
Root directory: frontend
Build command: npm run build
Deploy command: npx wrangler deploy
```

环境变量：

```env
VITE_API_BASE=https://qa-review-backend.onrender.com
```

部署成功后，Cloudflare 会给一个地址：

```text
https://qa-review-soft.pages.dev
```

## 5. 回 Render 更新 CORS

把 Render 的环境变量改成真实前端地址：

```env
CORS_ORIGINS=https://qa-review-soft.pages.dev
```

然后重新部署后端。

## 免费方案限制

Render 免费服务适合演示和测试，但本地磁盘不是长期文件存储。这个版本里上传的数据文件、图片压缩包会进入 Render 临时目录：

```env
QA_DATA_DIR=/tmp/qa-review-data
```

数据库里的项目、审核状态、AI 审核结果会保存在 Neon；但上传的图片文件如果 Render 实例重启，可能会丢。

长期版本建议下一步把媒体文件改到 Supabase Storage 或 Cloudflare R2。
