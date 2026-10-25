# Aurora Cigars 网站

迪拜古巴雪茄询价型网站：WordPress + WooCommerce（只当产品库用），所有成交都走 WhatsApp。

- 站点：https://wordpress-1627597-6431471.cloudwaysapps.com（Cloudways）
- 公司：Aurora Global Tobacco Trading FZCO（JAFZA, Dubai）
- WhatsApp：+971 585598868

## 目录

| 路径 | 作用 |
|---|---|
| `plugin/aurora-core/` | 网站功能插件（见下文） |
| `dist/aurora-core.zip` | 打包好的插件，直接上传到 WP 后台 |
| `scripts/aurora_setup.py` | 一键配置 WooCommerce、导入产品、创建页面和导航 |
| `content/brands.json` | 10 个品牌的中英文介绍（顺序 = 首页品牌宫格顺序） |
| `content/pages/*.html` | 首页、关于、防伪查验、常见问题、批发合作、配送与条款 |
| `scripts/build_zip.sh` | 修改插件后重新打包 |
| `tests/` | 测试（模拟环境渲染、浏览器交互、模拟 WooCommerce API） |

## aurora-core 插件做了什么

- **目录模式**：产品不可购买，购物车和结账页跳回商店，列表页按钮改成「查看详情 · 询价」，去掉头部购物车图标
- **产品详情页**：手机首屏顺序为 图片 → 品牌 → 名称 → 现货 / 防伪 / 限量标签 → 价格 → 盒数选择 → WhatsApp 一键询价 → 加入询价清单；规格表和配送说明放到下方标签页
- **WhatsApp 询价消息**
  - 普通款：`您好，我想询价：{产品名} {规格}，USD {价格}/盒，请确认库存。` 后面带上「数量：N 盒」
  - 限量版：`您好，我对 {产品名} 感兴趣，请确认库存与价格。`
- **询价清单**：客户可以挑多款、改盒数，然后整单一次发到 WhatsApp，消息里带参考合计。清单存在客户自己的浏览器里，所以不再需要 YITH Wishlist
- **悬浮 WhatsApp 按钮**：右下角，#25D366，48×48px，所以也不需要 Click to Chat 插件
- **年龄验证**：21 岁，记住 30 天，弹窗里写明不发货地区
- **设计**：黑白金配色；标题用 Bodoni Moda，正文用 EB Garamond，按钮用 Jost
- **商店列表**：卡片显示品牌和规格，顶部有品牌筛选条，没有产品图时用统一的品牌占位图
- **页脚**：公司信息、联系方式、服务链接、年龄和发货限制（Astra 主题自动显示）
- **短代码**（可放进 Elementor 的「短代码」小部件）：
  - `[aurora_brands limit="6"]` 品牌宫格
  - `[aurora_whatsapp text="WhatsApp 咨询" message="您好"]` WhatsApp 按钮
  - `[aurora_shipping]` 配送说明
  - `[aurora_products limit="8" brand="cohiba"]` 精选产品
  - `[aurora_brand_nav]` 品牌筛选条
  - `[aurora_footer]` 页脚（不用 Astra 时）
- **后台设置**：WooCommerce → Aurora 设置，可以改 WhatsApp 号码、年龄、不发货地区、物流文案

## 上线步骤

1. **生成新的 Application Password**：WP 后台 → 用户 → 个人资料 → 拉到底部的 Application Passwords。旧的那个请删掉。同时记下页面顶部的「用户名」（不是显示名称）
2. **安装插件**：插件 → 安装插件 → 上传插件，选择 `dist/aurora-core.zip`，然后启用
3. **在 Mac 终端运行**：

```bash
cd aurora-cigars/scripts
export AURORA_USER='后台登录用户名'
export AURORA_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx'

python3 aurora_setup.py check                                   # 测试连接
python3 aurora_setup.py configure                               # 设置 USD、迪拜，关闭配送
python3 aurora_setup.py import ~/路径/aurora_products_full.csv --dry-run   # 先看字段映射对不对
python3 aurora_setup.py import ~/路径/aurora_products_full.csv             # 正式导入（按 SKU 去重，可以重复跑）
python3 aurora_setup.py pages                                   # 创建 6 个页面，并设首页
python3 aurora_setup.py menu                                    # 创建主导航
python3 aurora_setup.py cleanup                                 # 停用 YITH、Click to Chat、PayPal
```

品牌分类会自动对上 `brands.json` 里的介绍。CSV 里的品牌写「Cohiba」「高希霸」或「cohiba」都可以，有没有重音（Partagás / Partagas）也都能识别。

如果 CSV 的列名没有被自动识别，用 `--map` 手动指定，例如：`--map price=零售价USD --map name_cn=产品中文名`。运行 `--dry-run` 时会列出所有可用字段。

4. **停用不再需要的插件**：运行 `cleanup` 即可，这些插件随时可以在后台重新启用

## 还没做的

- 多语言（English / عربي）：需要先选定翻译插件（Polylang 或 TranslatePress）
- n8n 自动化：把询价记录到表格或 CRM
- 用你自己的产品图替换占位图（不能用竞品的照片）

## 产品 CSV 能识别的列

中英文列名都可以，大小写和空格都不影响：

SKU / 编号 · 中文名 · English Name · 品牌 · 价格（可以写成 "USD 1,280"）· 每盒支数 · 型号 · 长度 · 环径 · 浓度 · 茄衣 · 产地 · 限量（是 / yes）· 防伪 · 库存（数字，或「现货 / 缺货」）· 图片（URL，多张用 `|` 分隔）· 品鉴描述 · 简介 · 分类

## 测试

```bash
php tests/build_preview.php > /tmp/preview.html     # 整站静态预览（示例产品）
php tests/render_harness.php > /tmp/normal.html && php tests/render_harness.php limited > /tmp/limited.html
node tests/browser_test.js /tmp/normal.html /tmp/limited.html /tmp      # 需要 playwright
python3 tests/mock_wc_server.py 8765 &                                   # 模拟 WooCommerce API
AURORA_SITE=http://127.0.0.1:8765 AURORA_USER=tester AURORA_APP_PASSWORD='abcd efgh ijkl' \
  python3 scripts/aurora_setup.py all tests/sample_products.csv
```
